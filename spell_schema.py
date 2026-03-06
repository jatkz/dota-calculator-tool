"""Spell schema helpers for sparse per-level effects-only storage and migration."""

from __future__ import annotations

import json

LEVEL_KEYS = ("effects",)
DEFAULT_LEVEL = {"effects": {}}

LEGACY_FIELD_TO_EFFECT = (
    ("damage", "Damage"),
    ("damage_type", "Damage Type"),
    ("hits", "Hits"),
    ("cast", "Cast"),
    ("stun", "Stun"),
    ("mana", "Mana"),
    ("cooldown", "Cooldown"),
)


def _deep_copy(value):
    return json.loads(json.dumps(value))


def default_level_data():
    """Return a fresh default level dictionary."""
    return _deep_copy(DEFAULT_LEVEL)


def _normalize_effects_map(raw_effects):
    effects = {}
    if not isinstance(raw_effects, dict):
        return effects
    for key, value in raw_effects.items():
        name = str(key).strip()
        if not name:
            continue
        effects[name] = str(value).strip()
    return effects


def _legacy_value_is_present(value):
    text = str(value).strip()
    return text not in ("", "0", "0.0", "0.00")


def _extract_effects_from_legacy_level(src):
    effects = {}
    effect_name = str(src.get("effect_name", "")).strip()
    effect_value = str(src.get("effect_value", "")).strip()
    if effect_name and effect_value:
        effects[effect_name] = effect_value

    for field_key, effect_label in LEGACY_FIELD_TO_EFFECT:
        if field_key not in src:
            continue
        value = src.get(field_key)
        if _legacy_value_is_present(value):
            effects[effect_label] = str(value).strip()

    modifiers = src.get("modifiers", [])
    if isinstance(modifiers, list):
        for modifier in modifiers:
            if not isinstance(modifier, dict):
                continue
            values = modifier.get("values", {})
            values = values if isinstance(values, dict) else {}
            effect_name = str(values.get("label_var", "") or modifier.get("type", "")).strip()
            effect_value = str(values.get("value_var", "")).strip()
            if effect_name and effect_value:
                effects[effect_name] = effect_value
    return effects


def normalize_level_data(level_data, damage_types=None, default_level=None):
    """Normalize one level dictionary to effects-only shape."""
    src = level_data if isinstance(level_data, dict) else {}
    out = _deep_copy(default_level if isinstance(default_level, dict) else DEFAULT_LEVEL)
    out["effects"] = _normalize_effects_map(src.get("effects", {}))
    legacy_effects = _extract_effects_from_legacy_level(src)
    for key, value in legacy_effects.items():
        out["effects"].setdefault(key, value)
    return out


def apply_level_override(parent_level, override_level, damage_types=None, default_level=None):
    """Apply sparse override fields onto a parent effective level."""
    parent = normalize_level_data(parent_level, damage_types, default_level=default_level)
    if not isinstance(override_level, dict):
        return parent

    out = _deep_copy(parent)
    override_effects = _normalize_effects_map(override_level.get("effects", {}))
    legacy_override_effects = _extract_effects_from_legacy_level(override_level)
    for key, value in legacy_override_effects.items():
        override_effects.setdefault(key, value)
    for key, value in override_effects.items():
        if value == "":
            out["effects"].pop(key, None)
        else:
            out["effects"][key] = value
    return out


def materialize_effective_levels(base_level, level_overrides, max_level, damage_types=None, default_level=None):
    """Build effective per-level list from sparse schema."""
    max_level = max(1, min(10, int(max_level)))
    levels = []
    effective = normalize_level_data(base_level, damage_types, default_level=default_level)
    levels.append(effective)
    overrides = level_overrides if isinstance(level_overrides, list) else []
    for idx in range(1, max_level):
        override = overrides[idx - 1] if idx - 1 < len(overrides) else {}
        effective = apply_level_override(effective, override, damage_types, default_level=default_level)
        levels.append(effective)
    return levels


def _diff_effects(parent_effects, current_effects):
    diff = {}
    all_keys = set(parent_effects.keys()) | set(current_effects.keys())
    for key in sorted(all_keys):
        parent_value = parent_effects.get(key, None)
        current_value = current_effects.get(key, None)
        if current_value == parent_value:
            continue
        diff[key] = "" if current_value is None else current_value
    return diff


def build_sparse_model_from_effective_levels(levels, max_level, damage_types=None, default_level=None):
    """Convert effective per-level values into sparse schema."""
    if not isinstance(levels, list) or not levels:
        levels = [default_level_data()]
    max_level = max(1, min(10, int(max_level)))
    normalized = [
        normalize_level_data(level, damage_types, default_level=default_level)
        for level in levels[:max_level]
    ]
    while len(normalized) < max_level:
        normalized.append(_deep_copy(normalized[-1]))

    base_level = _deep_copy(normalized[0])
    overrides = []
    parent = base_level
    for level in normalized[1:]:
        override = {}
        effect_diff = _diff_effects(parent.get("effects", {}), level.get("effects", {}))
        if effect_diff:
            override["effects"] = effect_diff
        overrides.append(override)
        parent = level
    return base_level, overrides


def migrate_spell_dict_to_sparse(spell_data, damage_types=None, default_level=None):
    """Migrate one spell dict from legacy levels[] to sparse format."""
    if not isinstance(spell_data, dict):
        return None, False

    if isinstance(spell_data.get("base_level"), dict):
        # Already sparse, but rebuild through materialize+diff so legacy keys inside
        # overrides are converted to effects-only deltas.
        max_level = int(spell_data.get("max_level", 1) or 1)
        max_level = max(1, min(10, max_level))
        effective_levels = materialize_effective_levels(
            base_level=spell_data.get("base_level", {}),
            level_overrides=spell_data.get("level_overrides", []),
            max_level=max_level,
            damage_types=damage_types,
            default_level=default_level,
        )
        base_level, normalized_overrides = build_sparse_model_from_effective_levels(
            effective_levels,
            max_level=max_level,
            damage_types=damage_types,
            default_level=default_level,
        )
        out = _deep_copy(spell_data)
        out["max_level"] = max_level
        out["base_level"] = base_level
        out["level_overrides"] = normalized_overrides
        out.pop("levels", None)
        out.pop("current_level", None)
        out.pop("spell_id", None)
        return out, out != spell_data

    legacy_levels = spell_data.get("levels")
    if not isinstance(legacy_levels, list) or not legacy_levels:
        # No valid source to migrate from.
        return None, False

    max_level = int(spell_data.get("max_level", len(legacy_levels)) or len(legacy_levels))
    max_level = max(1, min(10, max_level))
    normalized_levels = [
        normalize_level_data(level, damage_types, default_level=default_level)
        for level in legacy_levels[:max_level]
    ]
    while len(normalized_levels) < max_level:
        normalized_levels.append(_deep_copy(normalized_levels[-1]))

    base_level, level_overrides = build_sparse_model_from_effective_levels(
        normalized_levels,
        max_level=max_level,
        damage_types=damage_types,
        default_level=default_level,
    )

    out = _deep_copy(spell_data)
    out["max_level"] = max_level
    out["base_level"] = base_level
    out["level_overrides"] = level_overrides
    out.pop("levels", None)
    out.pop("current_level", None)
    out.pop("spell_id", None)
    return out, True
