# Spell Schema Guide

This is the canonical standard for converting spell screenshots into
`spell_library.json` entries.

## Canonical Spell Shape

```json
{
  "name": "Spell Name",
  "hero_key": "optional_hero_key",
  "tags": ["Tag A", "Tag B"],
  "max_level": 4,
  "notes": "optional notes",
  "base_level": {
    "effects": {
      "Effect Name": "Value"
    }
  },
  "level_overrides": [
    { "effects": { "Effect Name": "Changed Value" } },
    {},
    {}
  ],
  "toggleable_upgrades": [
    {
      "id": "upgrade_id",
      "label": "Talent (Level 20): Example",
      "effects": {
        "Some Effect Bonus": "Value"
      }
    }
  ]
}
```

## Required Rules

1. Store spell data in `effects` only.
2. Do not store legacy core fields (`damage`, `mana`, `cooldown`, `cast`, `stun`, `hits`, `modifiers`).
3. Do not store `spell_id` or `current_level`.
4. Keep always-on spell behavior in `base_level.effects`.
5. Keep only changed values in `level_overrides[i].effects`.
6. Use `toggleable_upgrades` only for true conditionals (talent, shard, scepter, facet, mode toggle).
7. If a mechanic is always active for the spell, keep it in base effects, not as a toggle.
8. If no value exists for a stat, omit it. Do not write placeholders like `0`, `none`, or empty strings.

## Sparse Level Semantics

- `base_level` is level 1.
- `level_overrides[0]` is level 2 changes.
- `level_overrides[1]` is level 3 changes.
- `level_overrides[2]` is level 4 changes.
- Missing keys inherit from the previous effective level.
- Use `{}` for levels with no changes.

## Effect Naming Standard

Use stable, human-readable labels. Reuse exact labels once chosen.

Preferred examples:
- `Damage`
- `Damage Type`
- `Mana Cost`
- `Cooldown`
- `Cast Range`
- `Cast Animation`
- `Stun Duration`
- `Move Speed Slow`
- `Aura Linger Duration`

For conditional bonuses, include scope in the name:
- `Move Speed Slow Bonus (0 Mana Target)`
- `Cooldown Reduction`
- `Damage Bonus per Kill`

## Upgrade Standard

Each toggleable upgrade should include:
- `id`: snake_case, stable, short, no level suffix unless needed for disambiguation.
- `label`: player-facing source and level/type.
- `effects`: only the conditional values it adds/changes.

Example:

```json
{
  "id": "talent_snowball_cd",
  "label": "Talent (Level 25): Snowball Cooldown Reduction",
  "effects": {
    "Cooldown Reduction": "6"
  }
}
```

## Image-to-JSON Workflow

1. Read spell header: name, type, targets, damage type.
2. Read base mechanics and all numeric lines.
3. Extract per-level values and put only deltas in overrides.
4. Detect conditional sections:
   - talent rows (leaf icon),
   - shard/scepter blocks,
   - facet-only behavior,
   - alt-cast / mode toggles.
5. Classify each conditional:
   - always part of spell -> base effects;
   - optional/conditional -> `toggleable_upgrades`.
6. Build final JSON with consistent effect names.

## Reviewer Checklist (Before Save)

- No legacy fields present.
- No `spell_id` / `current_level`.
- No duplicated per-level values in overrides.
- No always-on behavior modeled as toggleable.
- Talent levels are explicitly encoded in upgrade labels.
- Effect labels are consistent with existing library naming.
