"""Shared helpers for hero implementations."""

import json
import re


def normalize_key(value):
    """Normalize labels/names for key-based matching."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def deep_copy(value):
    """Deep copy JSON-compatible structures."""
    return json.loads(json.dumps(value))


def build_talents_payload(raw_talents):
    """Normalize incoming talent data with stable defaults."""
    raw_talents = raw_talents if isinstance(raw_talents, dict) else {}
    payload = {
        "version": int(raw_talents.get("version", 1)),
        "attribute_bonus": deep_copy(raw_talents.get("attribute_bonus", {})),
        "tiers": [],
    }

    tiers = raw_talents.get("tiers", [])
    if not isinstance(tiers, list):
        tiers = []

    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        left_payload = deep_copy(tier.get("left", {}))
        right_payload = deep_copy(tier.get("right", {}))

        selected_side = tier.get("selected_side")
        if selected_side not in ("left", "right", None):
            selected_side = None

        # Backward/forward compatibility:
        # if selected_side is missing, derive from side boolean flags when possible.
        if selected_side is None:
            left_selected = bool(left_payload.get("selected", False))
            right_selected = bool(right_payload.get("selected", False))
            if left_selected and not right_selected:
                selected_side = "left"
            elif right_selected and not left_selected:
                selected_side = "right"

        left_payload["selected"] = selected_side == "left"
        right_payload["selected"] = selected_side == "right"

        payload["tiers"].append({
            "level": tier.get("level"),
            "left": left_payload,
            "right": right_payload,
            "selected_side": selected_side,
        })

    payload["applied_effects"] = []
    return payload


def make_effect(effect_id, tier_level, side, label, target, field, operation, value, simulated, note=""):
    """Build a consistent talent effect payload."""
    return {
        "id": effect_id,
        "tier_level": tier_level,
        "side": side,
        "label": label,
        "target": target,
        "field": field,
        "operation": operation,
        "value": value,
        "simulated": bool(simulated),
        "note": note,
    }
