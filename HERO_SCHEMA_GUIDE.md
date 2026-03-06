# Hero Schema Guide

This is the canonical standard for `hero_library.json`.

## Canonical Hero Shape

```json
{
  "version": 1,
  "heroes": [
    {
      "fields": {
        "name": "Hero Name",
        "hero_key": "hero_key",
        "primary_attr": "str|agi|int|universal",
        "innate": "optional innate summary"
      },
      "talents": {
        "tiers": [
          {
            "level": 10,
            "choices": [
              { "label": "Talent A", "selected": false },
              { "label": "Talent B", "selected": false }
            ]
          },
          {
            "level": 15,
            "choices": [
              { "label": "Talent A", "selected": false },
              { "label": "Talent B", "selected": false }
            ]
          },
          {
            "level": 20,
            "choices": [
              { "label": "Talent A", "selected": false },
              { "label": "Talent B", "selected": false }
            ]
          },
          {
            "level": 25,
            "choices": [
              { "label": "Talent A", "selected": false },
              { "label": "Talent B", "selected": false }
            ]
          }
        ]
      }
    }
  ]
}
```

## Required Rules

1. Keep hero identity in `fields`.
2. Store talents only in `talents.tiers[].choices[]`.
3. `choices` is an array; do not use `left` / `right`.
4. Do not use `selected_side`.
5. Do not use hero-level `modifiers`.
6. Do not use hero-level `spells`.
7. Do not use hero-level `items`.
8. Do not use `hero_id`.
9. Do not use `talents.version` or `attribute_bonus`.

## Talent Rules

- Keep exactly four tiers: `10`, `15`, `20`, `25`.
- Each tier normally has two choices.
- `selected` is optional unless current build state must be persisted.
- Labels should be plain player-facing talent text.

## Naming Rules

- `hero_key` should be lowercase snake case (example: `phantom_assassin`).
- `name` should match in-game display name.
- Keep talent labels stable once entered to avoid lookup drift.

## Image-to-JSON Workflow

1. Read hero name and map to `hero_key`.
2. Fill base `fields`.
3. Read talent screen and capture each tier at levels `10/15/20/25`.
4. Put both tier options into `choices`.
5. Leave `selected` false unless the specific build selection is known.

## Reviewer Checklist (Before Save)

- No deprecated keys (`hero_id`, `modifiers`, `spells`, `items`).
- No deprecated talent keys (`left`, `right`, `selected_side`, `version`, `attribute_bonus`).
- All four talent tiers present and correctly leveled.
- JSON remains valid.
