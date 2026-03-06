"""Shared helper utilities for hero implementations."""

from __future__ import annotations

import copy
import re


_TALENT_TIER_DEFAULTS = {
    10: ("-2s Stifling Dagger Cooldown", "+0.6s Phantom Strike Duration"),
    15: ("+15% Stifling Dagger Instant Attack Damage", "+20% Immaterial Evasion"),
    20: ("+60 Phantom Strike Attack Speed", "+200 Phantom Strike Cast Range"),
    25: ("Triple Stifling Dagger Strikes", "+10% Coup de Grace Chance, -1 Methodical Required Attacks"),
}


def deep_copy(value):
    """Return a deep copy for plain Python payloads."""
    return copy.deepcopy(value)


def normalize_key(value):
    """Normalize labels/names for stable dictionary keys."""
    text = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _normalize_tier(level, tier):
    """Normalize one tier to the canonical left/right shape."""
    defaults = _TALENT_TIER_DEFAULTS.get(int(level), ("Left", "Right"))
    raw_left = tier.get("left", {}) if isinstance(tier, dict) else {}
    raw_right = tier.get("right", {}) if isinstance(tier, dict) else {}

    selected_side = None
    if isinstance(tier, dict):
        selected_side = tier.get("selected_side")
        if selected_side not in ("left", "right"):
            selected_side = None

    left = {
        "id": f"level_{int(level)}_left",
        "label": str(raw_left.get("label", defaults[0])),
        "selected": selected_side == "left",
    }
    right = {
        "id": f"level_{int(level)}_right",
        "label": str(raw_right.get("label", defaults[1])),
        "selected": selected_side == "right",
    }

    # Preserve explicit ids when provided.
    if isinstance(raw_left, dict) and raw_left.get("id"):
        left["id"] = str(raw_left.get("id"))
    if isinstance(raw_right, dict) and raw_right.get("id"):
        right["id"] = str(raw_right.get("id"))

    return {
        "level": int(level),
        "left": left,
        "right": right,
        "selected_side": selected_side,
    }


def build_talents_payload(raw):
    """Build canonical tiered talents payload used by UI and implementations."""
    payload = deep_copy(raw) if isinstance(raw, dict) else {}
    tiers_in = payload.get("tiers", []) if isinstance(payload.get("tiers", []), list) else []

    # Support legacy flat list payloads if encountered.
    if not tiers_in and isinstance(payload.get("talents"), list):
        tiers_map = {}
        for talent in payload.get("talents", []):
            if not isinstance(talent, dict):
                continue
            lvl = int(talent.get("level", 0) or 0)
            side = str(talent.get("side", "")).strip().lower()
            if lvl not in _TALENT_TIER_DEFAULTS or side not in ("left", "right"):
                continue
            tiers_map.setdefault(lvl, {})[side] = {
                "label": str(talent.get("label") or _TALENT_TIER_DEFAULTS[lvl][0 if side == "left" else 1]),
                "selected": bool(talent.get("selected")),
            }
        tiers_in = []
        for level in sorted(_TALENT_TIER_DEFAULTS):
            data = tiers_map.get(level, {})
            selected_side = None
            if data.get("left", {}).get("selected"):
                selected_side = "left"
            elif data.get("right", {}).get("selected"):
                selected_side = "right"
            tiers_in.append({
                "level": level,
                "left": data.get("left", {}),
                "right": data.get("right", {}),
                "selected_side": selected_side,
            })

    tiers_by_level = {}
    for tier in tiers_in:
        if not isinstance(tier, dict):
            continue
        level = int(tier.get("level", 0) or 0)
        if level <= 0:
            continue
        tiers_by_level[level] = _normalize_tier(level, tier)

    normalized_tiers = []
    for level in sorted(_TALENT_TIER_DEFAULTS):
        normalized_tiers.append(tiers_by_level.get(level, _normalize_tier(level, {"level": level})))

    return {
        "version": 1,
        "tiers": normalized_tiers,
        "applied_effects": deep_copy(payload.get("applied_effects", [])),
    }
