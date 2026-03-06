# Spell Schema Guide

This project uses an effects-first sparse schema for spell entries in `spell_library.json`.

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
      "id": "unique_upgrade_id",
      "label": "Talent/Shard/Scepter/Facet Label",
      "effects": {
        "Effect Name": "Value"
      }
    }
  ]
}
```

## Rules

1. Keep always-on values in `base_level.effects`.
2. Put only changed values in each `level_overrides[i].effects`.
3. Use `toggleable_upgrades` for conditional mechanics (talents/shard/scepter/facet/mode), not `base_level`.
4. Avoid fixed per-level fields (`damage`, `cooldown`, `mana`, etc.) in saved payloads.
5. Omit `current_level` and `spell_id` from library payloads.
6. Keep effect names stable and human-readable (for example `Cooldown`, `Mana Cost`, `Damage`).

## Level Override Semantics

- `level_overrides[0]` corresponds to level 2 changes.
- `level_overrides[1]` corresponds to level 3 changes.
- `level_overrides[2]` corresponds to level 4 changes.
- Empty override object means full inheritance from previous level.

## Recommended Naming

- `Cooldown`
- `Mana Cost`
- `Damage`
- `Damage Type`
- `Cast Range`
- `Cast Animation`
- `Stun Duration`

## Upgrade Modeling

Prefer explicit toggles:

```json
{
  "id": "talent_ice_shards_cd",
  "label": "Talent (Level 20): Ice Shards Cooldown Reduction",
  "effects": {
    "Cooldown Reduction": "6"
  }
}
```

Do not store talent-alternate values inline in base effects when the value is conditional.
