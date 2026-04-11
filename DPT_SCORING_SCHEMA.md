# DPT Scoring Schema

This document proposes a derived dataset, `dpt_scores.json`, built from:

- [dpt_matchups_synergies.json](/home/jaredt/projects/dota-calculator-tool/dpt_matchups_synergies.json)

The goal is to support draft-mode scoring and clean UI display without having to
recompute everything on every click.

## Why a second dataset

The raw D2PT export is good for pair rows, but draft mode wants:

- precomputed baseline scores per hero-role
- normalized pairwise scores for enemies and allies
- confidence-aware scores that account for match count
- a clean runtime scoring path for bans, enemy picks, and team picks

That points to a derived file rather than trying to score directly from raw
rows in the UI.

## Unit of scoring

The core unit should be `hero-role`, not just hero.

Example:

- `Tidehunter Offlane`
- `Invoker Mid`
- `Rubick Support`

That matches your D2PT data and also fits draft mode better.

## Important data note

`laneAdvantage` exists much more often for matchups than synergies.

Current rough coverage in your imported data:

- matchup rows with lane advantage: about 36%
- synergy rows with lane advantage: about 19%

So lane-based synergy scores should be supported, but treated as lower-confidence.

## Proposed output file

Suggested file:

- `dpt_scores.json`

Top-level shape:

```json
{
  "source": "dota2protracker",
  "version": 1,
  "generatedAt": "2026-04-11T12:00:00",
  "config": {
    "minRowMatches": 150,
    "reliabilityK": 400,
    "laneMissingPenalty": 0.65,
    "overallWeights": {
      "matchupWin": 0.5,
      "synergyWin": 0.5
    },
    "draftWeights": {
      "enemy": 1.0,
      "ally": 0.8,
      "banRelief": 0.35,
      "winVsLaneBlend": {
        "win": 0.65,
        "lane": 0.35
      }
    }
  },
  "heroes": {}
}
```

## Hero-role schema

Each hero contains roles, and each role contains both overall scores and
pairwise scores.

```json
{
  "heroes": {
    "Tidehunter": {
      "hero": "Tidehunter",
      "roles": {
        "3": {
          "role": "Offlane",
          "overall": {},
          "pairs": {
            "vs": {},
            "with": {}
          }
        }
      }
    }
  }
}
```

## The 5 overall scores

These are the five overall scores you described.

For each `hero-role`, store:

```json
{
  "overall": {
    "matchupWin": {},
    "synergyWin": {},
    "compositeWin": {},
    "matchupLane": {},
    "synergyLane": {}
  }
}
```

Recommended shape for each score object:

```json
{
  "raw": 1.83,
  "normalized": 74.2,
  "confidence": 0.81,
  "rowCount": 481,
  "coveredRowCount": 481,
  "totalMatches": 356214,
  "notes": "Weighted by winrate edge and match reliability"
}
```

Meaning:

- `raw`: unbounded internal score used for real math
- `normalized`: UI-friendly score, ideally `0-100`
- `confidence`: `0-1` confidence signal
- `rowCount`: total number of rows seen
- `coveredRowCount`: rows actually used for this score
- `totalMatches`: total row matches contributing to the score

## Pairwise scores

These are the precomputed pair signals draft mode will actually use.

Each hero-role gets:

```json
{
  "pairs": {
    "vs": {
      "Slark": {
        "roles": {
          "1": {
            "role": "Carry",
            "win": {},
            "lane": {},
            "row": {
              "winrate": 43.4,
              "laneAdvantage": -5.1,
              "matches": 2393
            }
          }
        }
      }
    },
    "with": {
      "Invoker": {
        "roles": {
          "2": {
            "role": "Mid",
            "win": {},
            "lane": {},
            "row": {
              "winrate": 52.5,
              "laneAdvantage": null,
              "matches": 2265
            }
          }
        }
      }
    }
  }
}
```

Recommended `win` / `lane` score object:

```json
{
  "raw": -2.41,
  "normalized": 18.7,
  "confidence": 0.86
}
```

## Suggested formulas

### Base row values

For each raw D2PT row:

```text
winEdge = winrate - 50
laneEdge = laneAdvantage
reliability = matches / (matches + reliabilityK)
```

With `reliabilityK = 400`, examples:

- 100 matches => 0.20
- 400 matches => 0.50
- 1200 matches => 0.75

### Pair scores

For matchup rows:

```text
pairMatchupWinRaw = winEdge * reliability
pairMatchupLaneRaw = (0.65 * winEdge + 0.35 * laneEdge) * reliability
```

For synergy rows:

```text
pairSynergyWinRaw = winEdge * reliability
pairSynergyLaneRaw = (0.75 * winEdge + 0.25 * laneEdge) * reliability * laneCoverageFactor
```

Where:

```text
laneCoverageFactor = 1.0 if laneAdvantage exists else laneMissingPenalty
```

Suggested:

```text
laneMissingPenalty = 0.65
```

That way lane-based synergy remains usable, but missing lane values weaken the
signal instead of pretending it is equally strong.

### Overall scores

Use weighted means of the pair scores, not raw sums.

That avoids heroes with more pair rows or more duplicated roles automatically
looking stronger just because they have more entries.

```text
overallMatchupWinRaw = weighted_mean(all pairMatchupWinRaw, weight=matches)
overallSynergyWinRaw = weighted_mean(all pairSynergyWinRaw, weight=matches)
overallCompositeWinRaw = 0.5 * overallMatchupWinRaw + 0.5 * overallSynergyWinRaw
overallMatchupLaneRaw = weighted_mean(all pairMatchupLaneRaw, weight=matches)
overallSynergyLaneRaw = weighted_mean(all pairSynergyLaneRaw, weight=matches)
```

Then normalize each score family to `0-100`.

Recommended normalization:

- compute the raw value for every hero-role in that family
- min-max normalize or percentile normalize across that family

Percentile normalization is usually better for UI because it resists outliers.

## Draft-mode runtime scores

The precomputed file should not store separate ban scores.

Ban impact can be derived from matchup pair scores:

- if a banned hero is a bad matchup for candidate hero, that is positive ban relief
- if a banned hero is a good matchup for candidate hero, ban should usually be neutral, not punitive

### Runtime components

For a draft candidate `candidateHeroRole`:

- `banReliefWin`
- `enemyCounterWin`
- `allySynergyWin`
- `banReliefLane`
- `enemyCounterLane`
- `allySynergyLane`

### Runtime formulas

```text
banReliefWin =
  mean(max(0, -pairVsWinRaw(candidate, bannedHeroRole)))

enemyCounterWin =
  mean(pairVsWinRaw(candidate, enemyHeroRole))

allySynergyWin =
  mean(pairWithWinRaw(candidate, allyHeroRole))
```

Lane versions use the corresponding lane score.

### Final draft outputs

I recommend these runtime outputs per candidate hero-role:

```json
{
  "draft": {
    "baselineWin": 71.3,
    "baselineLane": 62.8,
    "banReliefWin": 4.8,
    "banReliefLane": 1.1,
    "enemyWin": 10.4,
    "enemyLane": 7.2,
    "allyWin": 6.7,
    "allyLane": 2.0,
    "draftWin": 82.9,
    "draftLane": 68.4,
    "draftComposite": 77.8
  }
}
```

Recommended runtime blend:

```text
draftWin =
  baselineCompositeWin
  + 1.00 * enemyCounterWin
  + 0.80 * allySynergyWin
  + 0.35 * banReliefWin

draftLane =
  0.60 * overallMatchupLane
  + 0.40 * overallSynergyLane
  + 1.00 * enemyCounterLane
  + 0.70 * allySynergyLane
  + 0.25 * banReliefLane

draftComposite =
  0.65 * draftWin + 0.35 * draftLane
```

## Recommended UI display

For draft mode, each candidate hero row should show:

- Hero
- Role
- Draft Composite
- Draft Win
- Draft Lane
- Enemy
- Ally
- Ban Relief

And a detail drawer or side panel with reasons:

- `+8.4 vs Slark Carry`
- `+6.1 with Invoker Mid`
- `+2.9 because Ancient Apparition was banned`

## Integration idea for the current draft app

Current draft mode in:

- [draft_library_app.py](/home/jaredt/projects/dota-calculator-tool/draft_library_app.py)

is based on manual score notes and text-token matching.

The cleanest migration path is:

1. Keep the current manual system working
2. Add an optional DPT scorer layer beside it
3. Let the UI show:
   - manual score
   - DPT score
   - combined score

That lets you compare whether the generated DPT scorer feels sane before fully
replacing the current draft-library behavior.

## Suggested build order

1. Create `dpt_scores.json` from `dpt_matchups_synergies.json`
2. Precompute hero-role overall scores
3. Precompute pairwise `vs` and `with` scores
4. Add a small Python helper that scores one mock draft
5. Wire those outputs into draft mode UI
6. Decide whether to keep manual library scores as a second layer
