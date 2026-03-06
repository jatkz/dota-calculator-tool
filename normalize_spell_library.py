#!/usr/bin/env python3
"""Normalize spell library entries to canonical effects-first schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spell_schema import migrate_spell_dict_to_sparse


def _normalize_upgrade(upgrade):
    if not isinstance(upgrade, dict):
        return None
    out = {}
    if "id" in upgrade:
        out["id"] = str(upgrade.get("id", "")).strip()
    if "label" in upgrade:
        out["label"] = str(upgrade.get("label", "")).strip()
    effects = upgrade.get("effects", {})
    if isinstance(effects, dict):
        normalized = {}
        for key, value in effects.items():
            name = str(key).strip()
            if not name:
                continue
            normalized[name] = str(value).strip()
        out["effects"] = dict(sorted(normalized.items(), key=lambda kv: kv[0].lower()))
    if not out.get("effects"):
        out.pop("effects", None)
    return out if out else None


def _normalize_spell(spell):
    migrated, _ = migrate_spell_dict_to_sparse(spell)
    if migrated is None:
        return None

    out = {}
    for key in ("name", "hero_key", "tags", "max_level", "notes", "base_level", "level_overrides", "toggleable_upgrades"):
        if key in migrated:
            out[key] = migrated[key]

    tags = out.get("tags", [])
    if isinstance(tags, list):
        cleaned_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        if cleaned_tags:
            out["tags"] = cleaned_tags
        else:
            out.pop("tags", None)

    base_effects = out.get("base_level", {}).get("effects", {})
    if isinstance(base_effects, dict):
        out["base_level"]["effects"] = dict(sorted(base_effects.items(), key=lambda kv: kv[0].lower()))

    overrides = out.get("level_overrides", [])
    normalized_overrides = []
    if isinstance(overrides, list):
        for override in overrides:
            if not isinstance(override, dict):
                normalized_overrides.append({})
                continue
            effects = override.get("effects", {})
            if isinstance(effects, dict) and effects:
                normalized_overrides.append({
                    "effects": dict(sorted(
                        ((str(k).strip(), str(v).strip()) for k, v in effects.items() if str(k).strip()),
                        key=lambda kv: kv[0].lower()
                    ))
                })
            else:
                normalized_overrides.append({})
    out["level_overrides"] = normalized_overrides

    upgrades = out.get("toggleable_upgrades", [])
    if isinstance(upgrades, list):
        normalized_upgrades = []
        for upgrade in upgrades:
            normalized = _normalize_upgrade(upgrade)
            if normalized is not None:
                normalized_upgrades.append(normalized)
        if normalized_upgrades:
            out["toggleable_upgrades"] = normalized_upgrades
        else:
            out.pop("toggleable_upgrades", None)

    return out


def normalize_library(path: Path, in_place: bool) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    spells = payload.get("spells", [])
    if not isinstance(spells, list):
        raise ValueError("Invalid spell library: 'spells' must be a list.")

    normalized = []
    for spell in spells:
        entry = _normalize_spell(spell)
        if entry is not None:
            normalized.append(entry)

    out_payload = {"version": 2, "spells": normalized}
    output = json.dumps(out_payload, indent=2) + "\n"

    if in_place:
        path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return len(normalized)


def main():
    parser = argparse.ArgumentParser(description="Normalize spell_library.json to canonical effects schema.")
    parser.add_argument("path", nargs="?", default="spell_library.json", help="Path to spell library JSON.")
    parser.add_argument("--in-place", action="store_true", help="Write normalized output back to file.")
    args = parser.parse_args()

    count = normalize_library(Path(args.path), in_place=args.in_place)
    mode = "updated" if args.in_place else "generated"
    print(f"\n{mode} {count} spells", end="")


if __name__ == "__main__":
    main()
