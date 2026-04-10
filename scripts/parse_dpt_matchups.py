#!/usr/bin/env python3
"""Parse Dota2ProTracker matchups/synergies tables from saved HTML."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

try:
    from lxml import html
except ModuleNotFoundError as error:  # pragma: no cover - import guard for local envs
    raise SystemExit(
        "Missing dependency 'lxml'. Use the repo virtualenv:\n"
        "  source .venv/bin/activate\n"
        "  python scripts/import_dpt_exports.py ...\n"
        "or run:\n"
        "  .venv/bin/python scripts/import_dpt_exports.py ..."
    ) from error


ROLE_BY_POS = {
    "1": "Carry",
    "2": "Mid",
    "3": "Offlane",
    "4": "Support",
    "5": "Hard Support",
}
POS_BY_ROLE = {label: key for key, label in ROLE_BY_POS.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Dota2ProTracker matchup and synergy rows from saved HTML."
    )
    parser.add_argument("input", help="Path to saved D2PT HTML/body markup.")
    parser.add_argument(
        "--output",
        help="Optional output JSON path. Defaults to <input stem>_parsed.json.",
    )
    parser.add_argument(
        "--library-output",
        help=(
            "Optional aggregate JSON file to update with the parsed hero role data. "
            "This is the format intended to scale to all heroes."
        ),
    )
    return parser.parse_args()


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_role_from_src(src: str | None) -> str | None:
    if not src:
        return None
    match = re.search(r"pos_(\d)\.(?:png|svg)", src)
    if not match:
        return None
    return ROLE_BY_POS.get(match.group(1), match.group(1))


def parse_number(value: str) -> int | None:
    value = value.replace(",", "").strip()
    if not value or value == "-":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_percent(value: str) -> float | None:
    value = value.strip().replace("%", "")
    if not value or value == "-":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_rows(table_node) -> list[dict]:
    rows = []
    row_nodes = table_node.xpath(
        ".//div[contains(@class, 'tbody')]"
        "/div[contains(@class, 'border-d2pt-gray-5')]"
    )

    for row in row_nodes:
        cell_nodes = row.xpath("./div")
        if len(cell_nodes) < 5:
            continue

        hero_img = cell_nodes[0].xpath(".//img[@alt or @title]")
        hero_name = None
        if hero_img:
            hero_name = clean_text(hero_img[0].get("alt") or hero_img[0].get("title"))
        if not hero_name:
            continue

        role_img = cell_nodes[4].xpath(".//img[@src]")
        role = parse_role_from_src(role_img[0].get("src")) if role_img else None

        rows.append(
            {
                "hero": hero_name,
                "winrate": parse_percent(clean_text("".join(cell_nodes[1].itertext()))),
                "laneAdvantage": parse_percent(
                    clean_text("".join(cell_nodes[2].itertext()))
                ),
                "matches": parse_number(clean_text("".join(cell_nodes[3].itertext()))),
                "role": role,
            }
        )

    return rows


def parse_tables(document) -> dict:
    container_nodes = document.xpath('//*[@data-track-view="hero-matchups"]')
    if not container_nodes:
        raise ValueError("Could not find D2PT hero-matchups block in the input file.")

    container = container_nodes[0]
    table_nodes = container.xpath(".//div[contains(@class, 'matchup-table')]")

    matchups = []
    synergies = []
    for table_node in table_nodes:
        title_nodes = table_node.xpath("./div[1]")
        title = clean_text("".join(title_nodes[0].itertext())) if title_nodes else ""
        rows = parse_rows(table_node)
        if title.startswith("Matchups"):
            matchups = rows
        elif title.startswith("Synergies"):
            synergies = rows

    return {
        "matchups": matchups,
        "synergies": synergies,
    }


def detect_hero(document) -> str | None:
    heading = document.xpath("//div[contains(@class, 'text-[32px]')][1]")
    if heading:
        return clean_text("".join(heading[0].itertext()))
    title = document.xpath("//title/text()")
    if title:
        text = clean_text(title[0])
        if text:
            return text.split(":")[0].strip()
    return None


def detect_source_role(document) -> tuple[str | None, str | None]:
    heading_nodes = document.xpath('//*[@data-track-view="hero-role-stats"]//h2')
    if not heading_nodes:
        return None, None

    heading = heading_nodes[0]
    role_img = heading.xpath('.//img[contains(@src, "/static/pos/pos_")]')
    if role_img:
        src = role_img[0].get("src")
        role_label = parse_role_from_src(src)
        role_key_match = re.search(r"pos_(\d)\.(?:png|svg)", src or "")
        role_key = role_key_match.group(1) if role_key_match else POS_BY_ROLE.get(role_label)
        return role_key, role_label

    text = clean_text(" ".join(heading.itertext()))
    for role_label, role_key in POS_BY_ROLE.items():
        if text.endswith(role_label):
            return role_key, role_label
    return None, None


def build_library_role_record(parsed: dict, input_path: Path) -> dict:
    return {
        "role": parsed["sourceRole"],
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "site": "dota2protracker",
            "path": str(input_path),
            "windowDaysMax": 14,
        },
        "matchups": parsed["matchups"],
        "synergies": parsed["synergies"],
    }


def update_library_file(path: Path, parsed: dict, input_path: Path) -> None:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {
            "source": "dota2protracker",
            "heroes": {},
        }

    heroes = payload.setdefault("heroes", {})
    hero_record = heroes.setdefault(
        parsed["hero"],
        {
            "hero": parsed["hero"],
            "roles": {},
        },
    )
    roles = hero_record.setdefault("roles", {})
    role_key = parsed["sourceRoleKey"] or "unknown"
    roles[role_key] = build_library_role_record(parsed, input_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_input_file(input_path: Path) -> dict:
    document = html.fromstring(input_path.read_text(encoding="utf-8", errors="ignore"))
    parsed = parse_tables(document)
    parsed["hero"] = detect_hero(document)
    parsed["sourceRoleKey"], parsed["sourceRole"] = detect_source_role(document)
    parsed["source"] = str(input_path)
    return parsed


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_parsed.json")
    )

    parsed = parse_input_file(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    if args.library_output:
        update_library_file(Path(args.library_output), parsed, input_path)

    print(
        f"Saved {len(parsed['matchups'])} matchups and "
        f"{len(parsed['synergies'])} synergies to {output_path}"
    )
    if args.library_output:
        print(f"Updated aggregate library at {Path(args.library_output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
