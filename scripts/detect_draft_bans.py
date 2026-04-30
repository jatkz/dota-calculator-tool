#!/usr/bin/env python3
"""Detect banned heroes from a Dota 2 draft screenshot.

This script is intentionally dependency-free so it can run in the current
project without Pillow or NumPy. It detects the red ban overlays in the draft
screenshot, maps those card positions onto the same hero ordering used by the
repo's draft mode, and returns the banned hero names.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import zlib
from dataclasses import dataclass


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SAMPLE_COLS = 8
SAMPLE_ROWS = 12
ATTRIBUTE_ORDER = [
    ("str", "strength"),
    ("agi", "agility"),
    ("int", "intelligence"),
    ("uni", "universal"),
]
DRAFT_GRID_COLUMNS_BY_ATTRIBUTE = {
    "str": 6,
    "agi": 6,
    "int": 6,
    "uni": 4,
}
# These horizontal positions are sampled from the same Dota client draft screen
# layout shown in the reference screenshots. We combine them with the repo's
# existing draft-mode hero ordering to resolve each banned slot by position.
DRAFT_CLIENT_SECTION_START_RATIOS = {
    "str": 18 / 1204,
    "agi": 338 / 1204,
    "int": 660 / 1204,
    # The universal block starts slightly farther left than the initial sample
    # estimate suggested. This lines the slot windows up with the actual client
    # portraits used in the draft screenshots.
    "uni": 976.5 / 1204,
}
DRAFT_CLIENT_COLUMN_PITCH_RATIO = 51 / 1204
MAX_SLOT_DISTANCE = 0.60
DARK_BAN_BRIGHTNESS_THRESHOLD = 90.0
STRONG_BAN_DARK_RATIO = 0.97
STRONG_BAN_RED_RATIO = 0.18
COMPONENT_ASSIST_DARK_RATIO = 0.85
COMPONENT_ASSIST_RED_RATIO = 0.45
DARK_SCORE_BAN_DARK_RATIO = 0.97
DARK_SCORE_BAN_THRESHOLD = 0.42
ATTRIBUTE_SHIFT_MIN_PIXELS = 12.0
ATTRIBUTE_SHIFT_MIN_SAMPLE_COUNT = 3
ATTRIBUTE_SHIFT_MIN_SIGN_RATIO = 0.75
ATTRIBUTE_SHIFT_MAX_COLUMN_RATIO = 0.60
FALLBACK_ROW_CENTER_RATIOS = [
    0.1360,
    0.28695,
    0.4318,
    0.57985,
    0.7363,
    0.87885,
]


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def x1(self) -> int:
        return self.x + self.width

    @property
    def y1(self) -> int:
        return self.y + self.height


class SimpleImage:
    def __init__(self, width: int, height: int, rgba: bytearray):
        self.width = int(width)
        self.height = int(height)
        self.rgba = rgba

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        x = max(0, min(self.width - 1, int(x)))
        y = max(0, min(self.height - 1, int(y)))
        index = ((y * self.width) + x) * 4
        return (
            self.rgba[index],
            self.rgba[index + 1],
            self.rgba[index + 2],
            self.rgba[index + 3],
        )

    def sample(self, x: float, y: float) -> tuple[float, float, float, float]:
        if self.width <= 1 or self.height <= 1:
            red, green, blue, alpha = self.pixel(0, 0)
            return float(red), float(green), float(blue), float(alpha)

        x = max(0.0, min(float(self.width - 1), float(x)))
        y = max(0.0, min(float(self.height - 1), float(y)))
        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        x1 = min(self.width - 1, x0 + 1)
        y1 = min(self.height - 1, y0 + 1)
        tx = x - x0
        ty = y - y0

        p00 = self.pixel(x0, y0)
        p10 = self.pixel(x1, y0)
        p01 = self.pixel(x0, y1)
        p11 = self.pixel(x1, y1)

        def blend(channel_index: int) -> float:
            top = (p00[channel_index] * (1.0 - tx)) + (p10[channel_index] * tx)
            bottom = (p01[channel_index] * (1.0 - tx)) + (p11[channel_index] * tx)
            return (top * (1.0 - ty)) + (bottom * ty)

        return blend(0), blend(1), blend(2), blend(3)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_attribute(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"strength", "str"}:
        return "str"
    if text in {"agility", "agi"}:
        return "agi"
    if text in {"intelligence", "int"}:
        return "int"
    if text in {"universal", "uni"}:
        return "uni"
    return "uni"


def resolve_hero_attribute(hero_record: dict) -> str:
    if not isinstance(hero_record, dict):
        return "uni"

    general = hero_record.get("general", {})
    if isinstance(general, dict):
        primary = general.get("primary_attribute")
        normalized = normalize_attribute(primary)
        if normalized != "uni" or str(primary or "").strip().lower() == "universal":
            return normalized

    for key in ("primary_attribute", "primaryAttribute", "attribute_type"):
        value = hero_record.get(key)
        normalized = normalize_attribute(value)
        if normalized != "uni" or str(value or "").strip().lower() == "universal":
            return normalized

    return "uni"


def load_draft_heroes_by_attribute(dataset_path: str) -> dict[str, list[str]]:
    payload = load_json(dataset_path)
    heroes = payload.get("heroes") or payload.get("heroesCore") or {}
    hero_names = sorted(heroes.keys())
    hero_attributes = {
        hero_name: resolve_hero_attribute(heroes.get(hero_name, {}))
        for hero_name in hero_names
    }

    return {
        attribute_key: sorted(
            [
                hero_name
                for hero_name in hero_names
                if hero_name != "Spirit Bear" and hero_attributes.get(hero_name) == attribute_key
            ]
        )
        for attribute_key, _attribute_label in ATTRIBUTE_ORDER
    }


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    p = left + above - upper_left
    pa = abs(p - left)
    pb = abs(p - above)
    pc = abs(p - upper_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return above
    return upper_left


def load_png(path: str) -> SimpleImage:
    with open(path, "rb") as handle:
        payload = handle.read()

    if not payload.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG file")

    offset = len(PNG_SIGNATURE)
    width = None
    height = None
    bit_depth = None
    color_type = None
    interlace = None
    palette = None
    transparency = None
    compressed = bytearray()

    while offset < len(payload):
        chunk_length = struct.unpack(">I", payload[offset : offset + 4])[0]
        offset += 4
        chunk_type = payload[offset : offset + 4]
        offset += 4
        chunk_data = payload[offset : offset + chunk_length]
        offset += chunk_length
        offset += 4

        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(
                ">IIBBBBB",
                chunk_data,
            )
        elif chunk_type == b"PLTE":
            palette = [tuple(chunk_data[index : index + 3]) for index in range(0, len(chunk_data), 3)]
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None:
        raise ValueError(f"{path} is missing IHDR metadata")
    if int(bit_depth) != 8:
        raise ValueError(f"{path} uses unsupported bit depth {bit_depth}")
    if int(interlace) != 0:
        raise ValueError(f"{path} uses unsupported interlace mode {interlace}")

    if color_type == 6:
        channels = 4
        bytes_per_pixel = 4
    elif color_type == 2:
        channels = 3
        bytes_per_pixel = 3
    elif color_type == 3:
        channels = 1
        bytes_per_pixel = 1
        if palette is None:
            raise ValueError(f"{path} uses indexed color without a palette")
    else:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}")

    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    expected_size = (stride + 1) * height
    if len(raw) != expected_size:
        raise ValueError(
            f"{path} has unexpected decompressed size: {len(raw)} vs {expected_size}",
        )

    unfiltered = bytearray(width * height * channels)
    prev_row = bytearray(stride)
    raw_offset = 0
    out_offset = 0

    for _row_index in range(height):
        filter_type = raw[raw_offset]
        raw_offset += 1
        row = bytearray(raw[raw_offset : raw_offset + stride])
        raw_offset += stride
        current = bytearray(stride)

        for index in range(stride):
            left = current[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = prev_row[index]
            upper_left = prev_row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            value = row[index]

            if filter_type == 0:
                current[index] = value
            elif filter_type == 1:
                current[index] = (value + left) & 0xFF
            elif filter_type == 2:
                current[index] = (value + above) & 0xFF
            elif filter_type == 3:
                current[index] = (value + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                current[index] = (value + _paeth_predictor(left, above, upper_left)) & 0xFF
            else:
                raise ValueError(f"{path} uses unsupported PNG filter type {filter_type}")

        unfiltered[out_offset : out_offset + stride] = current
        out_offset += stride
        prev_row = current

    rgba = bytearray(width * height * 4)
    if color_type == 6:
        for pixel_index in range(width * height):
            source = pixel_index * 4
            target = pixel_index * 4
            rgba[target : target + 4] = unfiltered[source : source + 4]
    elif color_type == 2:
        for pixel_index in range(width * height):
            source = pixel_index * 3
            target = pixel_index * 4
            rgba[target] = unfiltered[source]
            rgba[target + 1] = unfiltered[source + 1]
            rgba[target + 2] = unfiltered[source + 2]
            rgba[target + 3] = 255
    else:
        for pixel_index in range(width * height):
            target = pixel_index * 4
            palette_index = unfiltered[pixel_index]
            red, green, blue = palette[palette_index]
            alpha = 255
            if transparency is not None and palette_index < len(transparency):
                alpha = transparency[palette_index]
            rgba[target] = red
            rgba[target + 1] = green
            rgba[target + 2] = blue
            rgba[target + 3] = alpha

    return SimpleImage(width, height, rgba)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def estimate_background(image: SimpleImage) -> tuple[float, float, float]:
    sample_points = []
    padding = 12
    for x in (padding, image.width - 1 - padding):
        for y in (padding, image.height - 1 - padding):
            sample_points.append(image.pixel(x, y))
    return (
        mean([point[0] for point in sample_points]),
        mean([point[1] for point in sample_points]),
        mean([point[2] for point in sample_points]),
    )


def color_distance(rgb: tuple[float, float, float], other: tuple[float, float, float]) -> float:
    return (
        abs(float(rgb[0]) - float(other[0]))
        + abs(float(rgb[1]) - float(other[1]))
        + abs(float(rgb[2]) - float(other[2]))
    )


def is_foreground_pixel(pixel: tuple[int, int, int, int], background_rgb: tuple[float, float, float]) -> bool:
    if pixel[3] < 48:
        return False
    return color_distance((pixel[0], pixel[1], pixel[2]), background_rgb) >= 42.0


def smooth_counts(values: list[int], radius: int) -> list[float]:
    smoothed = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        smoothed.append(sum(values[start:end]) / max(1, end - start))
    return smoothed


def find_runs(values: list[float], threshold: float, min_length: int) -> list[tuple[int, int]]:
    runs = []
    start = None
    for index, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_length:
                runs.append((start, index))
            start = None
    if start is not None and len(values) - start >= min_length:
        runs.append((start, len(values)))
    return runs


def median_int(values: list[int], fallback: int) -> int:
    if not values:
        return int(fallback)
    ordered = sorted(int(value) for value in values)
    return ordered[len(ordered) // 2]


def median_float(values: list[float], fallback: float = 0.0) -> float:
    if not values:
        return float(fallback)
    ordered = sorted(float(value) for value in values)
    return ordered[len(ordered) // 2]


def find_prominent_minima(
    values: list[float],
    window: int,
    start_threshold: float,
    drop_threshold: float,
    min_spacing: int,
) -> tuple[int, int, list[int]]:
    active_indexes = [index for index, value in enumerate(values) if value >= start_threshold]
    if not active_indexes:
        raise ValueError("Could not find an active image region")

    start = active_indexes[0]
    end = active_indexes[-1] + 1
    candidates = []
    for index in range(max(window, start), min(end - window, len(values) - window)):
        local_window = values[index - window : index + window + 1]
        local_value = values[index]
        if local_value != min(local_window):
            continue
        if (max(local_window) - local_value) < drop_threshold:
            continue
        candidates.append(index)

    minima = []
    for index in candidates:
        if minima and index - minima[-1] < min_spacing:
            if values[index] < values[minima[-1]]:
                minima[-1] = index
            continue
        minima.append(index)
    return start, end, minima


def detect_card_grid(image: SimpleImage) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    background_rgb = estimate_background(image)
    row_activity = []
    for y in range(image.height):
        count = 0
        for x in range(image.width):
            if is_foreground_pixel(image.pixel(x, y), background_rgb):
                count += 1
        row_activity.append(count)

    smoothed_rows = smooth_counts(row_activity, radius=3)
    row_start, row_end, row_minima = find_prominent_minima(
        smoothed_rows,
        window=max(20, image.height // 26),
        start_threshold=max(smoothed_rows) * 0.55,
        drop_threshold=max(55.0, max(smoothed_rows) * 0.08),
        min_spacing=max(40, image.height // 12),
    )
    row_bounds = [row_start] + row_minima + [row_end]
    row_runs = []
    for index in range(len(row_bounds) - 1):
        y0 = row_bounds[index]
        y1 = row_bounds[index + 1]
        if (y1 - y0) < max(36, image.height // 15):
            continue
        row_runs.append((y0, y1))

    if len(row_runs) < 5:
        raise ValueError(f"Could not detect enough hero rows: found {len(row_runs)}")

    grid_y0 = row_runs[0][0]
    grid_y1 = row_runs[-1][1]
    col_activity = []
    for x in range(image.width):
        count = 0
        for y in range(grid_y0, grid_y1):
            if is_foreground_pixel(image.pixel(x, y), background_rgb):
                count += 1
        col_activity.append(count)

    smoothed_cols = smooth_counts(col_activity, radius=2)
    col_start, col_end, col_minima = find_prominent_minima(
        smoothed_cols,
        window=max(10, image.width // 110),
        start_threshold=max(smoothed_cols) * 0.55,
        drop_threshold=max(30.0, max(smoothed_cols) * 0.07),
        min_spacing=max(22, image.width // 55),
    )
    col_bounds = [col_start] + col_minima + [col_end]
    col_runs = []
    for index in range(len(col_bounds) - 1):
        x0 = col_bounds[index]
        x1 = col_bounds[index + 1]
        if (x1 - x0) < max(22, image.width // 55):
            continue
        col_runs.append((x0, x1))

    if len(col_runs) < 18:
        raise ValueError(f"Could not detect enough hero columns: found {len(col_runs)}")

    return row_runs, col_runs


def detect_card_rows(image: SimpleImage) -> list[tuple[int, int]]:
    row_runs, _col_runs = detect_card_grid(image)
    return row_runs


def row_runs_look_valid(image: SimpleImage, row_runs: list[tuple[int, int]]) -> bool:
    if len(row_runs) != 6:
        return False

    heights = [y1 - y0 for y0, y1 in row_runs]
    if any(height < 55 or height > 105 for height in heights):
        return False

    centers = [(y0 + y1) / 2.0 for y0, y1 in row_runs]
    pitches = [centers[index + 1] - centers[index] for index in range(len(centers) - 1)]
    median_pitch = median_float(pitches, fallback=0.0)
    if median_pitch <= 1.0:
        return False

    if any(abs(pitch - median_pitch) > (median_pitch * 0.22) for pitch in pitches):
        return False

    if centers[0] < (image.height * 0.09) or centers[-1] > (image.height * 0.92):
        return False

    return True


def fallback_card_rows(image: SimpleImage) -> list[tuple[int, int]]:
    row_centers = [image.height * ratio for ratio in FALLBACK_ROW_CENTER_RATIOS]
    row_pitch = median_float(
        [row_centers[index + 1] - row_centers[index] for index in range(len(row_centers) - 1)],
        fallback=max(1.0, image.height / 6.0),
    )
    row_height = max(60.0, min(90.0, row_pitch * 0.88))
    half_height = row_height / 2.0

    row_runs = []
    for center in row_centers:
        y0 = max(0, int(round(center - half_height)))
        y1 = min(image.height, int(round(center + half_height)))
        row_runs.append((y0, y1))
    return row_runs


def detect_card_rows_robust(image: SimpleImage) -> list[tuple[int, int]]:
    try:
        row_runs = detect_card_rows(image)
    except Exception:
        row_runs = []

    if row_runs_look_valid(image, row_runs):
        return row_runs
    return fallback_card_rows(image)


def is_red_overlay_pixel(red: float, green: float, blue: float) -> bool:
    return red >= 56.0 and red >= (green * 1.16) and red >= (blue * 1.18) and (red - green) >= 14.0


def screenshot_descriptor(image: SimpleImage, rect: Rect) -> dict:
    diag_red = 0
    diag_total = 0
    red_total = 0
    sample_total = 0

    for row_index in range(SAMPLE_ROWS):
        y_norm = (row_index + 0.5) / SAMPLE_ROWS
        y = rect.y + (rect.height * (0.08 + (0.84 * y_norm)))
        for col_index in range(SAMPLE_COLS):
            x_norm = (col_index + 0.5) / SAMPLE_COLS
            x = rect.x + (rect.width * (0.16 + (0.68 * x_norm)))
            red, green, blue, _alpha = image.sample(x, y)
            sample_total += 1

            red_overlay = is_red_overlay_pixel(red, green, blue)
            if red_overlay:
                red_total += 1
            diagonal_distance = abs(x_norm - y_norm)
            if diagonal_distance <= 0.20:
                diag_total += 1
                if red_overlay:
                    diag_red += 1

    red_ratio = red_total / max(1, sample_total)
    diag_red_ratio = diag_red / max(1, diag_total)
    ban_score = (0.45 * red_ratio) + (0.55 * diag_red_ratio)

    return {
        "banScore": ban_score,
        "redRatio": red_ratio,
        "diagRedRatio": diag_red_ratio,
    }


def is_relaxed_red_overlay_pixel(red: float, green: float, blue: float) -> bool:
    return red >= 28.0 and red > green and red > blue and ((red - green) + (red - blue)) >= 10.0


def slot_overlay_metrics(image: SimpleImage, x_center: float, y_center: float) -> dict:
    width = 44
    height = 78
    left = int(round(x_center - (width / 2.0)))
    top = int(round(y_center - (height / 2.0)))

    total = 0
    relaxed_red_count = 0
    dark_count = 0
    diag_total = 0
    diag_relaxed_red = 0
    offdiag_total = 0
    offdiag_relaxed_red = 0
    desaturated_count = 0
    bright_count = 0

    for offset_y in range(height):
        sample_y = top + offset_y
        if sample_y < 0 or sample_y >= image.height:
            continue
        y_norm = (offset_y + 0.5) / height
        for offset_x in range(width):
            sample_x = left + offset_x
            if sample_x < 0 or sample_x >= image.width:
                continue
            red, green, blue, _alpha = image.pixel(sample_x, sample_y)
            total += 1

            relaxed_red = is_relaxed_red_overlay_pixel(red, green, blue)
            if relaxed_red:
                relaxed_red_count += 1

            x_norm = (offset_x + 0.5) / width
            diagonal_distance = abs(x_norm - y_norm)
            if diagonal_distance <= 0.16:
                diag_total += 1
                if relaxed_red:
                    diag_relaxed_red += 1
            elif diagonal_distance >= 0.30:
                offdiag_total += 1
                if relaxed_red:
                    offdiag_relaxed_red += 1

            if ((red + green + blue) / 3.0) < DARK_BAN_BRIGHTNESS_THRESHOLD:
                dark_count += 1
            if (max(red, green, blue) - min(red, green, blue)) < 20.0:
                desaturated_count += 1
            if max(red, green, blue) > 145.0 and (max(red, green, blue) - min(red, green, blue)) > 45.0:
                bright_count += 1

    relaxed_red_ratio = relaxed_red_count / max(1, total)
    dark_ratio = dark_count / max(1, total)
    diag_relaxed_red_ratio = diag_relaxed_red / max(1, diag_total)
    offdiag_relaxed_red_ratio = offdiag_relaxed_red / max(1, offdiag_total)
    desaturated_ratio = desaturated_count / max(1, total)
    bright_ratio = bright_count / max(1, total)

    return {
        "relaxedRedRatio": relaxed_red_ratio,
        "darkRatio": dark_ratio,
        "diagRelaxedRedRatio": diag_relaxed_red_ratio,
        "offdiagRelaxedRedRatio": offdiag_relaxed_red_ratio,
        "desaturatedRatio": desaturated_ratio,
        "brightRatio": bright_ratio,
        "slotBanScore": (
            (diag_relaxed_red_ratio * 0.45)
            + (dark_ratio * 0.30)
            + (desaturated_ratio * 0.20)
            + (max(0.0, diag_relaxed_red_ratio - offdiag_relaxed_red_ratio) * 0.25)
            - (bright_ratio * 0.35)
        ),
        "strongDarkBan": dark_ratio >= STRONG_BAN_DARK_RATIO and relaxed_red_ratio >= STRONG_BAN_RED_RATIO,
    }


def detect_red_ban_components(image: SimpleImage) -> list[dict]:
    visited = bytearray(image.width * image.height)
    components = []

    for y in range(image.height):
        for x in range(image.width):
            index = (y * image.width) + x
            if visited[index]:
                continue

            red, green, blue, alpha = image.pixel(x, y)
            if alpha < 48 or not is_red_overlay_pixel(red, green, blue):
                visited[index] = 1
                continue

            stack = [(x, y)]
            visited[index] = 1
            area = 0
            x0 = x1 = x
            y0 = y1 = y
            while stack:
                current_x, current_y = stack.pop()
                area += 1
                x0 = min(x0, current_x)
                x1 = max(x1, current_x)
                y0 = min(y0, current_y)
                y1 = max(y1, current_y)

                for next_y in range(max(0, current_y - 1), min(image.height, current_y + 2)):
                    base = next_y * image.width
                    for next_x in range(max(0, current_x - 1), min(image.width, current_x + 2)):
                        next_index = base + next_x
                        if visited[next_index]:
                            continue
                        next_red, next_green, next_blue, next_alpha = image.pixel(next_x, next_y)
                        if next_alpha >= 48 and is_red_overlay_pixel(next_red, next_green, next_blue):
                            visited[next_index] = 1
                            stack.append((next_x, next_y))
                        else:
                            visited[next_index] = 1

            width = (x1 - x0) + 1
            height = (y1 - y0) + 1
            fill_ratio = area / max(1, width * height)
            if area < 900:
                continue
            if width < 35 or width > 50:
                continue
            if height < 45 or height > 90:
                continue
            if fill_ratio < 0.25:
                continue
            components.append(
                {
                    "rect": Rect(x0, y0, width, height),
                    "area": area,
                    "fillRatio": fill_ratio,
                }
            )

    return sorted(
        components,
        key=lambda component: (component["rect"].y, component["rect"].x),
    )


def build_position_slots(
    image: SimpleImage,
    row_runs: list[tuple[int, int]],
    draft_heroes_by_attribute: dict[str, list[str]],
) -> tuple[list[dict], float, float]:
    row_centers = [
        (float(y0) + float(y1)) / 2.0
        for y0, y1 in row_runs
    ]
    row_pitch = median_float(
        [row_centers[index + 1] - row_centers[index] for index in range(len(row_centers) - 1)],
        fallback=max(1.0, image.height / 6.0),
    )
    column_pitch = max(1.0, float(image.width) * DRAFT_CLIENT_COLUMN_PITCH_RATIO)

    slots = []
    for attribute_key, _attribute_label in ATTRIBUTE_ORDER:
        heroes = draft_heroes_by_attribute.get(attribute_key, [])
        columns = DRAFT_GRID_COLUMNS_BY_ATTRIBUTE[attribute_key]
        section_start = float(image.width) * DRAFT_CLIENT_SECTION_START_RATIOS[attribute_key]
        for hero_index, hero_name in enumerate(heroes):
            row_index = hero_index // columns
            column_index = hero_index % columns
            if row_index >= len(row_centers):
                continue
            x_center = section_start + (column_index * column_pitch) + (column_pitch / 2.0)
            y_center = row_centers[row_index]
            slots.append(
                {
                    "hero": hero_name,
                    "attribute": attribute_key,
                    "rowIndex": row_index,
                    "columnIndex": column_index,
                    "xCenter": x_center,
                    "yCenter": y_center,
                }
            )

    return slots, column_pitch, row_pitch


def calibrate_slot_positions(slots: list[dict], components: list[dict], column_pitch: float) -> list[dict]:
    deltas_by_attribute = {attribute_key: [] for attribute_key, _attribute_label in ATTRIBUTE_ORDER}
    for component in components:
        component_center_x = component["rect"].x + (component["rect"].width / 2.0)
        nearest_slot = min(
            slots,
            key=lambda slot: abs(slot["xCenter"] - component_center_x),
        )
        deltas_by_attribute[nearest_slot["attribute"]].append(component_center_x - nearest_slot["xCenter"])

    horizontal_shifts = {}
    for attribute_key, _attribute_label in ATTRIBUTE_ORDER:
        values = deltas_by_attribute.get(attribute_key, [])
        if len(values) < ATTRIBUTE_SHIFT_MIN_SAMPLE_COUNT:
            horizontal_shifts[attribute_key] = 0.0
            continue

        shift = median_float(values, fallback=0.0)
        same_sign_count = len(
            [
                value
                for value in values
                if (value >= 0.0 and shift >= 0.0) or (value <= 0.0 and shift <= 0.0)
            ]
        )
        same_sign_ratio = same_sign_count / max(1, len(values))
        if abs(shift) < ATTRIBUTE_SHIFT_MIN_PIXELS or same_sign_ratio < ATTRIBUTE_SHIFT_MIN_SIGN_RATIO:
            shift = 0.0
        if abs(shift) > (column_pitch * ATTRIBUTE_SHIFT_MAX_COLUMN_RATIO):
            shift = 0.0
        horizontal_shifts[attribute_key] = shift

    adjusted = []
    for slot in slots:
        adjusted.append(
            {
                **slot,
                "xCenter": slot["xCenter"] + horizontal_shifts.get(slot["attribute"], 0.0),
            }
        )
    return adjusted


def nearest_slot_for_component(
    component: dict,
    slots: list[dict],
    column_pitch: float,
    row_pitch: float,
) -> tuple[dict, float]:
    component_center_x = component["rect"].x + (component["rect"].width / 2.0)
    component_center_y = component["rect"].y + (component["rect"].height / 2.0)
    best_slot = None
    best_distance = float("inf")

    for slot in slots:
        dx = (component_center_x - slot["xCenter"]) / max(1.0, column_pitch)
        dy = (component_center_y - slot["yCenter"]) / max(1.0, row_pitch)
        distance = math.sqrt((dx * dx) + (dy * dy))
        if distance < best_distance:
            best_distance = distance
            best_slot = slot

    if best_slot is None:
        raise ValueError("Could not match a banned card component to a hero slot")
    return best_slot, best_distance


def detect_banned_heroes(screenshot_path: str, dataset_path: str) -> dict:
    screenshot = load_png(screenshot_path)
    components = detect_red_ban_components(screenshot)
    row_runs = detect_card_rows_robust(screenshot)
    draft_heroes_by_attribute = load_draft_heroes_by_attribute(dataset_path)
    slots, column_pitch, row_pitch = build_position_slots(screenshot, row_runs, draft_heroes_by_attribute)
    slots = calibrate_slot_positions(slots, components, column_pitch)
    component_matches = {}
    for component in components:
        slot, slot_distance = nearest_slot_for_component(
            component,
            slots,
            column_pitch,
            row_pitch,
        )
        if slot_distance > MAX_SLOT_DISTANCE:
            continue
        slot_key = (slot["attribute"], slot["rowIndex"], slot["columnIndex"], slot["hero"])
        descriptor = screenshot_descriptor(screenshot, component["rect"])
        previous = component_matches.get(slot_key)
        if previous is not None and previous["slotDistance"] <= slot_distance:
            continue
        component_matches[slot_key] = {
            "slotDistance": slot_distance,
            "componentRect": component["rect"],
            "descriptor": descriptor,
        }

    banned_detections = []
    for slot in slots:
        slot_key = (slot["attribute"], slot["rowIndex"], slot["columnIndex"], slot["hero"])
        overlay = slot_overlay_metrics(screenshot, slot["xCenter"], slot["yCenter"])
        component_match = component_matches.get(slot_key)
        component_assisted_ban = (
            component_match is not None
            and overlay["darkRatio"] >= COMPONENT_ASSIST_DARK_RATIO
            and overlay["relaxedRedRatio"] >= COMPONENT_ASSIST_RED_RATIO
        )
        dark_score_ban = (
            overlay["darkRatio"] >= DARK_SCORE_BAN_DARK_RATIO
            and overlay["slotBanScore"] >= DARK_SCORE_BAN_THRESHOLD
        )
        if not overlay["strongDarkBan"] and not component_assisted_ban and not dark_score_ban:
            continue

        component_rect = component_match["componentRect"] if component_match is not None else None
        descriptor = component_match["descriptor"] if component_match is not None else None
        detection_mode = "slot-dark"
        if component_assisted_ban and not overlay["strongDarkBan"] and not dark_score_ban:
            detection_mode = "component-assisted"
        elif dark_score_ban and not overlay["strongDarkBan"]:
            detection_mode = "slot-dark-score"
        banned_detections.append(
            {
                "hero": slot["hero"],
                "attribute": slot["attribute"],
                "rowIndex": slot["rowIndex"],
                "columnIndex": slot["columnIndex"],
                "slotDistance": component_match["slotDistance"] if component_match is not None else None,
                "banScore": descriptor["banScore"] if descriptor is not None else None,
                "redRatio": descriptor["redRatio"] if descriptor is not None else None,
                "diagRedRatio": descriptor["diagRedRatio"] if descriptor is not None else None,
                "relaxedRedRatio": overlay["relaxedRedRatio"],
                "darkRatio": overlay["darkRatio"],
                "diagRelaxedRedRatio": overlay["diagRelaxedRedRatio"],
                "offdiagRelaxedRedRatio": overlay["offdiagRelaxedRedRatio"],
                "desaturatedRatio": overlay["desaturatedRatio"],
                "brightRatio": overlay["brightRatio"],
                "slotBanScore": overlay["slotBanScore"],
                "banDetectionMode": detection_mode,
                "componentRect": (
                    {
                        "x": component_rect.x,
                        "y": component_rect.y,
                        "width": component_rect.width,
                        "height": component_rect.height,
                    }
                    if component_rect is not None
                    else None
                ),
                "slotCenter": {
                    "x": round(slot["xCenter"], 2),
                    "y": round(slot["yCenter"], 2),
                },
            }
        )

    banned_detections.sort(
        key=lambda detection: (
            detection["rowIndex"],
            detection["attribute"],
            detection["columnIndex"],
            detection["hero"],
        )
    )

    return {
        "screenshot": os.path.abspath(screenshot_path),
        "detectedBanCount": len(banned_detections),
        "bannedHeroes": [detection["hero"] for detection in banned_detections],
        "bannedDetections": banned_detections,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshot", help="Path to the draft screenshot PNG")
    parser.add_argument(
        "--dataset",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "dataset.json"),
        help="Path to dataset.json so hero ordering matches draft mode",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = detect_banned_heroes(args.screenshot, args.dataset)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
