#!/usr/bin/env python3
"""Download Liquipedia Dota 2 hero icons into this project.

The script can work from either:
- a saved category page HTML file such as heroicons.txt, or
- the live category URL on Liquipedia.

By default it reads heroicons.txt from the project root when available, which
lets you test parsing without making any network requests. Downloads are saved
directly into assets/hero-icons under the project root.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATEGORY_URL = "https://liquipedia.net/commons/Category:Dota_2_hero_icons"
DEFAULT_SOURCE_HTML = PROJECT_ROOT / "heroicons.txt"
DEFAULT_DATASET_PATH = PROJECT_ROOT / "dataset.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "assets" / "hero-icons"
REQUEST_HEADERS = {
    "User-Agent": "dota-calculator-tool/1.0 (hero icon downloader)",
}
ICON_SUFFIX = "_icon_dota2_gameasset.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Liquipedia Dota 2 hero icons into this project.",
    )
    parser.add_argument(
        "--category-url",
        default=DEFAULT_CATEGORY_URL,
        help=f"Category URL to crawl. Default: {DEFAULT_CATEGORY_URL}",
    )
    parser.add_argument(
        "--source-html",
        default=str(DEFAULT_SOURCE_HTML),
        help="Optional saved category HTML/text file to parse first. Default: heroicons.txt in the project root.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Where to save icons. Default: assets/hero-icons in the project root.",
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Optional dataset.json path used by --project-only.",
    )
    parser.add_argument(
        "--fetch-live",
        action="store_true",
        help="Ignore the saved HTML file and fetch the category page from Liquipedia.",
    )
    parser.add_argument(
        "--project-only",
        action="store_true",
        help="Only keep icons whose names match heroes in dataset.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files that already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print what would be downloaded without downloading files.",
    )
    return parser.parse_args()


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def download_binary(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request) as response:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".part")
        with temp_path.open("wb") as handle:
            handle.write(response.read())
        temp_path.replace(destination)


def read_source_html(source_path: Path) -> str:
    return source_path.read_text(encoding="utf-8")


def strip_source_prefix(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("url:"):
        return "\n".join(lines[1:]).lstrip()
    return text


def parse_icon_filenames(html_text: str) -> list[str]:
    filenames: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'href="/commons/File:([^"#?]+)"', html_text):
        filename = urllib.parse.unquote(match.group(1))
        if not filename.endswith(ICON_SUFFIX):
            continue
        if filename in seen:
            continue
        seen.add(filename)
        filenames.append(filename)
    return filenames


def parse_next_page_url(html_text: str, current_url: str) -> str | None:
    match = re.search(r'href="([^"]+)"[^>]*>\s*next page\s*</a>', html_text, re.IGNORECASE)
    if not match:
        return None
    return urllib.parse.urljoin(current_url, urllib.parse.unquote(match.group(1)))


def crawl_category_pages(category_url: str) -> list[str]:
    filenames: list[str] = []
    seen_files: set[str] = set()
    visited_pages: set[str] = set()
    next_url: str | None = category_url

    while next_url and next_url not in visited_pages:
        visited_pages.add(next_url)
        html_text = fetch_text(next_url)
        page_filenames = parse_icon_filenames(html_text)
        for filename in page_filenames:
            if filename in seen_files:
                continue
            seen_files.add(filename)
            filenames.append(filename)
        next_url = parse_next_page_url(html_text, next_url)

    return filenames


def icon_display_name(filename: str) -> str:
    if not filename.endswith(ICON_SUFFIX):
        return filename
    return filename[: -len(ICON_SUFFIX)].replace("_", " ")


def load_project_hero_names(dataset_path: Path) -> set[str]:
    if not dataset_path.exists():
        return set()

    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    heroes = payload.get("heroes") or payload.get("heroesCore") or {}
    if not isinstance(heroes, dict):
        return set()
    return {str(hero_name) for hero_name in heroes}


def build_download_url(filename: str) -> str:
    encoded = urllib.parse.quote(filename, safe="")
    return f"https://liquipedia.net/commons/Special:Redirect/file/{encoded}"


def filter_project_icons(filenames: list[str], project_hero_names: set[str]) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    matched_names: set[str] = set()
    for filename in filenames:
        hero_name = icon_display_name(filename)
        if hero_name in project_hero_names:
            kept.append(filename)
            matched_names.add(hero_name)

    missing = sorted(project_hero_names - matched_names)
    return kept, missing


def main() -> int:
    args = parse_args()

    source_html_path = Path(args.source_html).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    dataset_path = Path(args.dataset).expanduser()

    if args.fetch_live:
        filenames = crawl_category_pages(args.category_url)
        source_label = args.category_url
    else:
        if not source_html_path.exists():
            raise SystemExit(
                f"Source HTML file not found: {source_html_path}\n"
                "Pass --fetch-live to crawl the site directly."
            )
        html_text = strip_source_prefix(read_source_html(source_html_path))
        filenames = parse_icon_filenames(html_text)
        source_label = str(source_html_path)

    if not filenames:
        raise SystemExit(f"No hero icon files found in {source_label}")

    print(f"Found {len(filenames)} icon files from {source_label}")

    if args.project_only:
        project_hero_names = load_project_hero_names(dataset_path)
        if not project_hero_names:
            raise SystemExit(f"No hero names found in dataset: {dataset_path}")
        filenames, missing_heroes = filter_project_icons(filenames, project_hero_names)
        print(f"Keeping {len(filenames)} icons that match heroes in {dataset_path}")
        if missing_heroes:
            print("Project heroes without matching site icons:")
            for hero_name in missing_heroes:
                print(f"  - {hero_name}")

    if args.dry_run:
        print("Dry run only. Planned files:")
        for filename in filenames:
            print(f"  - {filename}")
        print(f"Output directory: {output_dir}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    for index, filename in enumerate(filenames, start=1):
        destination = output_dir / filename
        if destination.exists() and not args.force:
            skipped += 1
            print(f"[{index}/{len(filenames)}] Skipping existing {filename}")
            continue

        download_url = build_download_url(filename)
        print(f"[{index}/{len(filenames)}] Downloading {filename}")
        try:
            download_binary(download_url, destination)
            downloaded += 1
        except Exception as exc:
            print(f"Failed to download {filename}: {exc}", file=sys.stderr)

    print("")
    print(f"Saved icons to {output_dir}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
