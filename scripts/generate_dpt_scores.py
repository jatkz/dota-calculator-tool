#!/usr/bin/env python3
"""Generate a derived DPT scoring dataset from raw matchup/synergy data."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import pstdev


ROLE_BY_KEY = {
    "1": "Carry",
    "2": "Mid",
    "3": "Offlane",
    "4": "Support",
    "5": "Hard Support",
}
ROLE_KEY_BY_LABEL = {label: key for key, label in ROLE_BY_KEY.items()}

MATCHUP_LANE_WIN_WEIGHT = 0.65
MATCHUP_LANE_ADV_WEIGHT = 0.35
SYNERGY_LANE_WIN_WEIGHT = 0.75
SYNERGY_LANE_ADV_WEIGHT = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dpt_scores.json from dpt_matchups_synergies.json."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="dpt_matchups_synergies.json",
        help="Input DPT matchup/synergy library. Default: dpt_matchups_synergies.json",
    )
    parser.add_argument(
        "--output",
        default="dpt_scores.json",
        help="Output score file. Default: dpt_scores.json",
    )
    parser.add_argument(
        "--min-row-matches",
        type=int,
        default=150,
        help="Ignore pair rows below this number of matches. Default: 150",
    )
    parser.add_argument(
        "--reliability-k",
        type=float,
        default=400.0,
        help="Reliability smoothing parameter. Default: 400",
    )
    parser.add_argument(
        "--lane-missing-penalty",
        type=float,
        default=0.65,
        help="Confidence and lane-signal penalty when laneAdvantage is missing. Default: 0.65",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def weighted_mean(values: list[float], weights: list[float]) -> float | None:
    if not values or not weights:
        return None
    total_weight = sum(weights)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def family_scale(values: list[float]) -> float:
    if not values:
        return 1.0
    stddev = pstdev(values) if len(values) > 1 else abs(values[0])
    mean_abs = sum(abs(value) for value in values) / len(values)
    return max(stddev * 2.0, mean_abs * 1.25, 0.25)


def normalize_raw(raw: float | None, scale: float) -> float | None:
    if raw is None:
        return None
    return 50.0 + (50.0 * math.tanh(raw / scale))


def round_score_object(payload: dict) -> dict:
    rounded = dict(payload)
    for key in ("raw", "normalized", "confidence"):
        if key in rounded and isinstance(rounded[key], (int, float)):
            digits = 4 if key in {"raw", "confidence"} else 2
            rounded[key] = round(float(rounded[key]), digits)
    return rounded


def build_score_object(
    raw: float | None,
    confidence: float,
    row_count: int,
    covered_row_count: int,
    total_matches: int,
    notes: str,
    lane_data_row_count: int | None = None,
) -> dict:
    payload = {
        "raw": raw,
        "normalized": None,
        "confidence": max(0.0, min(1.0, confidence)),
        "rowCount": row_count,
        "coveredRowCount": covered_row_count,
        "totalMatches": total_matches,
        "notes": notes,
    }
    if lane_data_row_count is not None:
        payload["laneDataRowCount"] = lane_data_row_count
    return round_score_object(payload)


def score_row(
    row: dict,
    *,
    reliability_k: float,
    lane_missing_penalty: float,
    lane_win_weight: float,
    lane_adv_weight: float,
    min_row_matches: int,
) -> dict | None:
    matches = int(row.get("matches") or 0)
    winrate = row.get("winrate")
    if matches < min_row_matches or winrate is None:
        return None

    reliability = matches / (matches + reliability_k) if matches > 0 else 0.0
    win_edge = float(winrate) - 50.0
    lane_value = row.get("laneAdvantage")
    has_lane = lane_value is not None
    lane_edge = float(lane_value) if has_lane else 0.0
    lane_factor = 1.0 if has_lane else lane_missing_penalty

    return {
        "matches": matches,
        "winRaw": win_edge * reliability,
        "laneRaw": (lane_win_weight * win_edge + lane_adv_weight * lane_edge)
        * reliability
        * lane_factor,
        "reliability": reliability,
        "laneConfidence": reliability * lane_factor,
        "hasLane": has_lane,
    }


def compute_overall_from_rows(
    rows: list[dict],
    *,
    min_row_matches: int,
    reliability_k: float,
    lane_missing_penalty: float,
    lane_win_weight: float,
    lane_adv_weight: float,
    win_notes: str,
    lane_notes: str,
) -> tuple[dict, dict]:
    scored_rows = [
        score_row(
            row,
            reliability_k=reliability_k,
            lane_missing_penalty=lane_missing_penalty,
            lane_win_weight=lane_win_weight,
            lane_adv_weight=lane_adv_weight,
            min_row_matches=min_row_matches,
        )
        for row in rows
    ]
    eligible = [row for row in scored_rows if row is not None]
    weights = [row["matches"] for row in eligible]

    row_count = len(rows)
    covered_row_count = len(eligible)
    total_matches = sum(weights)
    base_confidence = weighted_mean([row["reliability"] for row in eligible], weights) or 0.0
    coverage_ratio = (covered_row_count / row_count) if row_count else 0.0

    win_raw = weighted_mean([row["winRaw"] for row in eligible], weights)
    win_confidence = base_confidence * coverage_ratio if covered_row_count else 0.0

    lane_data_row_count = sum(1 for row in eligible if row["hasLane"])
    lane_coverage_ratio = (
        lane_data_row_count / covered_row_count if covered_row_count else 0.0
    )
    lane_raw = weighted_mean([row["laneRaw"] for row in eligible], weights)
    lane_confidence = (
        base_confidence
        * coverage_ratio
        * (
            lane_coverage_ratio
            + ((1.0 - lane_coverage_ratio) * lane_missing_penalty)
        )
        if covered_row_count
        else 0.0
    )

    win_score = build_score_object(
        win_raw,
        win_confidence,
        row_count,
        covered_row_count,
        total_matches,
        win_notes,
    )
    lane_score = build_score_object(
        lane_raw,
        lane_confidence,
        row_count,
        covered_row_count,
        total_matches,
        lane_notes,
        lane_data_row_count=lane_data_row_count,
    )
    return win_score, lane_score


def build_pair_entry(
    row: dict,
    scored_row: dict,
) -> dict:
    return {
        "win": round_score_object(
            {
                "raw": scored_row["winRaw"],
                "normalized": None,
                "confidence": scored_row["reliability"],
            }
        ),
        "lane": round_score_object(
            {
                "raw": scored_row["laneRaw"],
                "normalized": None,
                "confidence": scored_row["laneConfidence"],
            }
        ),
        "row": {
            "winrate": row.get("winrate"),
            "laneAdvantage": row.get("laneAdvantage"),
            "matches": row.get("matches"),
        },
    }


def finalize_normalized_scores(payload: dict, family_scales: dict[str, float]) -> None:
    overall_family_names = {
        "matchupWin": "overallMatchupWin",
        "synergyWin": "overallSynergyWin",
        "compositeWin": "overallCompositeWin",
        "matchupLane": "overallMatchupLane",
        "synergyLane": "overallSynergyLane",
    }
    for hero_data in payload["heroes"].values():
        for role_data in hero_data.get("roles", {}).values():
            overall = role_data.get("overall", {})
            for family_name, score in overall.items():
                score["normalized"] = normalize_raw(
                    score.get("raw"),
                    family_scales[overall_family_names[family_name]],
                )
                round_score_object(score)
                if isinstance(score.get("normalized"), (int, float)):
                    score["normalized"] = round(float(score["normalized"]), 2)

            for pair_group, win_family, lane_family in (
                ("vs", "pairVsWin", "pairVsLane"),
                ("with", "pairWithWin", "pairWithLane"),
            ):
                for target_data in role_data.get("pairs", {}).get(pair_group, {}).values():
                    for role_score in target_data.get("roles", {}).values():
                        for score_name, family_name in (
                            ("win", win_family),
                            ("lane", lane_family),
                        ):
                            score = role_score[score_name]
                            score["normalized"] = normalize_raw(
                                score.get("raw"),
                                family_scales[family_name],
                            )
                            round_score_object(score)
                            if isinstance(score.get("normalized"), (int, float)):
                                score["normalized"] = round(float(score["normalized"]), 2)


def combine_component_scores(
    components: list[tuple[float | None, float, float]],
    *,
    row_count: int,
    covered_row_count: int,
    total_matches: int,
    notes: str,
) -> dict:
    valid = [
        (raw, confidence, weight)
        for raw, confidence, weight in components
        if raw is not None and weight > 0
    ]
    if valid:
        total_weight = sum(weight for _raw, _confidence, weight in valid)
        raw = sum(raw * weight for raw, _confidence, weight in valid) / total_weight
        confidence = (
            sum(confidence * weight for _raw, confidence, weight in valid) / total_weight
        )
    else:
        raw = None
        confidence = 0.0
    return build_score_object(
        raw,
        confidence,
        row_count,
        covered_row_count,
        total_matches,
        notes,
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    input_payload = load_json(input_path)
    heroes_payload = input_payload.get("heroes", {})

    output_payload = {
        "source": "dota2protracker",
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "minRowMatches": args.min_row_matches,
            "reliabilityK": args.reliability_k,
            "laneMissingPenalty": args.lane_missing_penalty,
            "overallWeights": {
                "matchupWin": 0.5,
                "synergyWin": 0.5,
            },
            "draftWeights": {
                "enemy": 1.0,
                "ally": 0.8,
                "banRelief": 0.35,
                "winVsLaneBlend": {
                    "win": 0.65,
                    "lane": 0.35,
                },
            },
        },
        "heroes": {},
    }

    family_raws = {
        "overallMatchupWin": [],
        "overallSynergyWin": [],
        "overallCompositeWin": [],
        "overallMatchupLane": [],
        "overallSynergyLane": [],
        "pairVsWin": [],
        "pairVsLane": [],
        "pairWithWin": [],
        "pairWithLane": [],
    }

    hero_role_count = 0
    pair_count = {"vs": 0, "with": 0}

    for hero_name, hero_data in heroes_payload.items():
        out_hero = {
            "hero": hero_name,
            "rolePriors": {},
            "roles": {},
        }

        for role_key, role_data in hero_data.get("roles", {}).items():
            hero_role_count += 1
            matchup_rows = role_data.get("matchups", [])
            synergy_rows = role_data.get("synergies", [])

            matchup_win, matchup_lane = compute_overall_from_rows(
                matchup_rows,
                min_row_matches=args.min_row_matches,
                reliability_k=args.reliability_k,
                lane_missing_penalty=args.lane_missing_penalty,
                lane_win_weight=MATCHUP_LANE_WIN_WEIGHT,
                lane_adv_weight=MATCHUP_LANE_ADV_WEIGHT,
                win_notes="Weighted matchup winrate edge with match reliability.",
                lane_notes="Weighted matchup lane signal using lane advantage, winrate edge, and match reliability.",
            )
            synergy_win, synergy_lane = compute_overall_from_rows(
                synergy_rows,
                min_row_matches=args.min_row_matches,
                reliability_k=args.reliability_k,
                lane_missing_penalty=args.lane_missing_penalty,
                lane_win_weight=SYNERGY_LANE_WIN_WEIGHT,
                lane_adv_weight=SYNERGY_LANE_ADV_WEIGHT,
                win_notes="Weighted synergy winrate edge with match reliability.",
                lane_notes="Weighted synergy lane signal using lane advantage, winrate edge, and match reliability.",
            )

            composite_win = combine_component_scores(
                [
                    (matchup_win["raw"], matchup_win["confidence"], 0.5),
                    (synergy_win["raw"], synergy_win["confidence"], 0.5),
                ],
                row_count=matchup_win["rowCount"] + synergy_win["rowCount"],
                covered_row_count=matchup_win["coveredRowCount"] + synergy_win["coveredRowCount"],
                total_matches=matchup_win["totalMatches"] + synergy_win["totalMatches"],
                notes="Blend of overall matchup and synergy win scores.",
            )

            overall = {
                "matchupWin": matchup_win,
                "synergyWin": synergy_win,
                "compositeWin": composite_win,
                "matchupLane": matchup_lane,
                "synergyLane": synergy_lane,
            }

            for family_name, score in (
                ("overallMatchupWin", matchup_win),
                ("overallSynergyWin", synergy_win),
                ("overallCompositeWin", composite_win),
                ("overallMatchupLane", matchup_lane),
                ("overallSynergyLane", synergy_lane),
            ):
                if score.get("raw") is not None:
                    family_raws[family_name].append(score["raw"])

            role_out = {
                "role": role_data.get("role") or ROLE_BY_KEY.get(role_key, role_key),
                "updatedAt": role_data.get("updatedAt"),
                "source": role_data.get("source"),
                "overall": overall,
                "pairs": {
                    "vs": {},
                    "with": {},
                },
            }

            for pair_group, rows, lane_win_weight, lane_adv_weight, win_family, lane_family in (
                ("vs", matchup_rows, MATCHUP_LANE_WIN_WEIGHT, MATCHUP_LANE_ADV_WEIGHT, "pairVsWin", "pairVsLane"),
                ("with", synergy_rows, SYNERGY_LANE_WIN_WEIGHT, SYNERGY_LANE_ADV_WEIGHT, "pairWithWin", "pairWithLane"),
            ):
                for row in rows:
                    scored_row = score_row(
                        row,
                        reliability_k=args.reliability_k,
                        lane_missing_penalty=args.lane_missing_penalty,
                        lane_win_weight=lane_win_weight,
                        lane_adv_weight=lane_adv_weight,
                        min_row_matches=args.min_row_matches,
                    )
                    if scored_row is None:
                        continue

                    target_hero = row.get("hero")
                    target_role_label = row.get("role")
                    target_role_key = ROLE_KEY_BY_LABEL.get(target_role_label)
                    if not target_hero or not target_role_key:
                        continue

                    target_record = role_out["pairs"][pair_group].setdefault(
                        target_hero,
                        {"roles": {}},
                    )
                    target_record["roles"][target_role_key] = {
                        "role": target_role_label,
                        **build_pair_entry(row, scored_row),
                    }
                    family_raws[win_family].append(scored_row["winRaw"])
                    family_raws[lane_family].append(scored_row["laneRaw"])
                    pair_count[pair_group] += 1

            out_hero["roles"][role_key] = role_out

        role_prior_samples = {}
        for role_key, role_out in out_hero["roles"].items():
            composite = role_out["overall"]["compositeWin"]
            role_prior_samples[role_key] = int(composite.get("totalMatches") or 0)

        total_role_prior_samples = sum(role_prior_samples.values())
        for role_key, sample_matches in role_prior_samples.items():
            out_hero["rolePriors"][role_key] = {
                "role": out_hero["roles"][role_key]["role"],
                "sampleMatches": sample_matches,
                "weight": (
                    sample_matches / total_role_prior_samples
                    if total_role_prior_samples > 0
                    else 0.0
                ),
            }

        output_payload["heroes"][hero_name] = out_hero

    family_scales = {family_name: family_scale(values) for family_name, values in family_raws.items()}
    finalize_normalized_scores(output_payload, family_scales)

    output_payload["stats"] = {
        "heroCount": len(output_payload["heroes"]),
        "heroRoleCount": hero_role_count,
        "pairCount": pair_count,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(
        f"Saved DPT scores for {len(output_payload['heroes'])} heroes "
        f"across {hero_role_count} hero-role entries to {output_path}"
    )
    print(
        f"Pair scores: vs={pair_count['vs']} with={pair_count['with']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
