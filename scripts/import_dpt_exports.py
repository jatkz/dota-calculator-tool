#!/usr/bin/env python3
"""Import downloaded D2PT HTML exports into the aggregate JSON library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from parse_dpt_matchups import parse_input_file, update_library_file


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY_OUTPUT = REPO_ROOT / "dpt_matchups_synergies.json"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "outputs" / "dpt_import_summary.json"
DEFAULT_PATTERN = "dpt_*.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan one or more directories for downloaded D2PT HTML exports and merge "
            "them into the aggregate JSON library."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help=(
            "Optional file or directory paths to scan. If omitted, the script will "
            "auto-detect likely Downloads folders."
        ),
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Filename glob to import when scanning directories. Default: {DEFAULT_PATTERN}",
    )
    parser.add_argument(
        "--library-output",
        default=str(DEFAULT_LIBRARY_OUTPUT),
        help=(
            "Aggregate JSON library file to update. "
            f"Default: {DEFAULT_LIBRARY_OUTPUT}"
        ),
    )
    parser.add_argument(
        "--summary-output",
        default=str(DEFAULT_SUMMARY_OUTPUT),
        help=(
            "Optional JSON summary file of what was imported. "
            f"Default: {DEFAULT_SUMMARY_OUTPUT}"
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories when scanning directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be imported without updating the library.",
    )
    return parser.parse_args()


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        normalized = path.resolve() if path.exists() else path
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(path)
    return unique


def guess_download_dirs() -> list[Path]:
    candidates = [Path.home() / "Downloads"]
    windows_users = Path("/mnt/c/Users")
    if windows_users.exists():
        for user_dir in sorted(windows_users.iterdir()):
            candidates.append(user_dir / "Downloads")
    return [path for path in unique_paths(candidates) if path.is_dir()]


def expand_inputs(inputs: list[str], pattern: str, recursive: bool) -> list[Path]:
    candidates = [Path(value).expanduser() for value in inputs] if inputs else guess_download_dirs()
    matches: list[Path] = []
    glob_method = "rglob" if recursive else "glob"

    for candidate in candidates:
        if candidate.is_file():
            matches.append(candidate)
            continue

        if not candidate.is_dir():
            continue

        matches.extend(sorted(getattr(candidate, glob_method)(pattern)))

    html_matches = [
        path for path in unique_paths(matches) if path.is_file() and path.suffix.lower() in {".html", ".htm"}
    ]
    return sorted(html_matches, key=lambda path: (path.stat().st_mtime, path.name))


def main() -> int:
    args = parse_args()
    files = expand_inputs(args.inputs, args.pattern, args.recursive)

    if not files:
        searched = [str(path) for path in (args.inputs or [str(path) for path in guess_download_dirs()])]
        print("No matching DPT export files found.")
        print("Searched:")
        for path in searched:
            print(f"  - {path}")
        return 1

    library_output = Path(args.library_output)
    summary_output = Path(args.summary_output) if args.summary_output else None

    imported = []
    failures = []
    for input_path in files:
        try:
            parsed = parse_input_file(input_path)
            record = {
                "file": str(input_path),
                "hero": parsed.get("hero"),
                "roleKey": parsed.get("sourceRoleKey"),
                "role": parsed.get("sourceRole"),
                "matchups": len(parsed.get("matchups", [])),
                "synergies": len(parsed.get("synergies", [])),
            }
            imported.append(record)

            if not args.dry_run:
                update_library_file(library_output, parsed, input_path)
        except Exception as error:  # pragma: no cover - defensive batch import path
            failures.append(
                {
                    "file": str(input_path),
                    "error": str(error),
                }
            )

    summary = {
        "libraryOutput": str(library_output),
        "filesImported": len(imported),
        "filesFailed": len(failures),
        "dryRun": bool(args.dry_run),
        "imports": imported,
        "failures": failures,
    }

    if summary_output:
        summary_output.parent.mkdir(parents=True, exist_ok=True)
        summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    action = "Would import" if args.dry_run else "Imported"
    print(f"{action} {len(imported)} DPT export file(s).")
    for record in imported:
        print(
            f"- {record['hero']} {record['role']} "
            f"(matchups={record['matchups']}, synergies={record['synergies']}) "
            f"from {record['file']}"
        )
    for failure in failures:
        print(f"- FAILED {failure['file']}: {failure['error']}")
    if summary_output:
        print(f"Saved import summary to {summary_output}")
    if not args.dry_run:
        print(f"Updated aggregate library at {library_output}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
