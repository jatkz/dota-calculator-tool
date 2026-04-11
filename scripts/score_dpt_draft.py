#!/usr/bin/env python3
"""Score draft candidates from dpt_scores.json."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import pstdev


ROLE_BY_KEY = {
    "1": "Carry",
    "2": "Mid",
    "3": "Offlane",
    "4": "Support",
    "5": "Hard Support",
}
ROLE_KEY_BY_LABEL = {label.lower(): key for key, label in ROLE_BY_KEY.items()}

DRAFT_WEIGHTS = {
    "enemy": 1.0,
    "ally": 0.8,
    "ban_relief": 0.35,
    "lane_baseline_matchup": 0.6,
    "lane_baseline_synergy": 0.4,
    "ally_lane": 0.7,
    "ban_relief_lane": 0.25,
    "composite_win": 0.65,
    "composite_lane": 0.35,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score draft candidates using dpt_scores.json."
    )
    parser.add_argument(
        "--scores",
        default="dpt_scores.json",
        help="Path to dpt_scores.json. Default: dpt_scores.json",
    )
    parser.add_argument(
        "--candidate-role",
        default="3",
        help="Role to score candidates for (1-5 or role label). Default: 3",
    )
    parser.add_argument(
        "--ally",
        action="append",
        default=[],
        help='Known ally pick, format "Hero:Role" or "Hero". Repeatable.',
    )
    parser.add_argument(
        "--enemy",
        action="append",
        default=[],
        help='Enemy pick, format "Hero:Role" or "Hero". If role is omitted, role priors are used. Repeatable.',
    )
    parser.add_argument(
        "--ban",
        action="append",
        default=[],
        help='Banned hero, format "Hero:Role" or "Hero". If role is omitted, role priors are used. Repeatable.',
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many top candidates to show. Default: 20",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON results instead of a text table.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def resolve_role_key(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text in ROLE_BY_KEY:
        return text
    return ROLE_KEY_BY_LABEL.get(text.lower())


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


def weighted_mean(items: list[tuple[float, float]]) -> float | None:
    if not items:
        return None
    total_weight = sum(weight for _value, weight in items)
    if total_weight <= 0:
        return None
    return sum(value * weight for value, weight in items) / total_weight


def average_or_zero(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_hero_lookup(scores_payload: dict) -> dict[str, str]:
    return {
        normalize_text(hero_name): hero_name
        for hero_name in scores_payload.get("heroes", {})
    }


def parse_hero_spec(spec: str, hero_lookup: dict[str, str]) -> tuple[str, str | None]:
    text = str(spec or "").strip()
    if not text:
        raise ValueError("Empty hero spec.")

    hero_part = text
    role_part = None
    if ":" in text:
        hero_part, role_part = text.rsplit(":", 1)
        hero_part = hero_part.strip()
        role_part = role_part.strip()

    hero_name = hero_lookup.get(normalize_text(hero_part))
    if not hero_name:
        raise ValueError(f"Unknown hero: {hero_part}")

    role_key = resolve_role_key(role_part) if role_part else None
    if role_part and not role_key:
        raise ValueError(f"Unknown role: {role_part}")
    return hero_name, role_key


def get_role_priors(scores_payload: dict, hero_name: str) -> dict[str, dict]:
    hero_data = scores_payload["heroes"].get(hero_name, {})
    priors = hero_data.get("rolePriors", {})
    if priors:
        return priors

    roles = hero_data.get("roles", {})
    sample_matches = {
        role_key: int(role_data["overall"]["compositeWin"].get("totalMatches") or 0)
        for role_key, role_data in roles.items()
    }
    total = sum(sample_matches.values())
    return {
        role_key: {
            "role": roles[role_key]["role"],
            "sampleMatches": sample_matches[role_key],
            "weight": sample_matches[role_key] / total if total > 0 else 0.0,
        }
        for role_key in roles
    }


def resolve_pair_score(
    scores_payload: dict,
    candidate_role_data: dict,
    pair_group: str,
    target_hero: str,
    score_name: str,
    target_role_key: str | None = None,
) -> dict | None:
    target_data = candidate_role_data.get("pairs", {}).get(pair_group, {}).get(target_hero)
    if not target_data:
        return None

    roles_payload = target_data.get("roles", {})
    if target_role_key and target_role_key in roles_payload:
        role_payload = roles_payload[target_role_key]
        score_payload = role_payload.get(score_name)
        if not score_payload:
            return None
        return {
            "raw": score_payload.get("raw"),
            "confidence": score_payload.get("confidence"),
            "normalized": score_payload.get("normalized"),
            "resolvedRoles": [
                {
                    "roleKey": target_role_key,
                    "role": role_payload.get("role"),
                    "weight": 1.0,
                    "raw": score_payload.get("raw"),
                    "confidence": score_payload.get("confidence"),
                }
            ],
            "usedRolePriors": False,
        }

    priors = get_role_priors(scores_payload, target_hero)
    weighted_raws = []
    weighted_confidence = []
    resolved_roles = []

    for role_key, prior in priors.items():
        role_payload = roles_payload.get(role_key)
        if not role_payload:
            continue
        score_payload = role_payload.get(score_name)
        raw = score_payload.get("raw")
        confidence = score_payload.get("confidence")
        weight = float(prior.get("weight") or 0.0)
        if raw is None or weight <= 0:
            continue
        weighted_raws.append((raw, weight))
        if confidence is not None:
            weighted_confidence.append((confidence, weight))
        resolved_roles.append(
            {
                "roleKey": role_key,
                "role": role_payload.get("role"),
                "weight": weight,
                "raw": raw,
                "confidence": confidence,
            }
        )

    if not weighted_raws:
        return None

    return {
        "raw": weighted_mean(weighted_raws),
        "confidence": weighted_mean(weighted_confidence) if weighted_confidence else None,
        "normalized": None,
        "resolvedRoles": resolved_roles,
        "usedRolePriors": True,
    }


def resolve_reverse_pair_score(
    scores_payload: dict,
    candidate_hero: str,
    candidate_role_key: str,
    pair_group: str,
    target_hero: str,
    score_name: str,
    target_role_key: str | None = None,
) -> dict | None:
    target_hero_data = scores_payload["heroes"].get(target_hero)
    if not target_hero_data:
        return None

    target_roles = target_hero_data.get("roles", {})
    if target_role_key and target_role_key in target_roles:
        target_role_data = target_roles[target_role_key]
        candidate_pair = (
            target_role_data.get("pairs", {})
            .get(pair_group, {})
            .get(candidate_hero)
        )
        if not candidate_pair:
            return None
        candidate_role_payload = candidate_pair.get("roles", {}).get(candidate_role_key)
        if not candidate_role_payload:
            return None
        score_payload = candidate_role_payload.get(score_name)
        if not score_payload:
            return None
        return {
            "raw": score_payload.get("raw"),
            "confidence": score_payload.get("confidence"),
            "normalized": score_payload.get("normalized"),
            "resolvedRoles": [
                {
                    "roleKey": target_role_key,
                    "role": target_role_data.get("role"),
                    "weight": 1.0,
                    "raw": score_payload.get("raw"),
                    "confidence": score_payload.get("confidence"),
                }
            ],
            "usedRolePriors": False,
        }

    priors = get_role_priors(scores_payload, target_hero)
    weighted_raws = []
    weighted_confidence = []
    resolved_roles = []

    for role_key, prior in priors.items():
        target_role_data = target_roles.get(role_key)
        if not target_role_data:
            continue
        candidate_pair = (
            target_role_data.get("pairs", {})
            .get(pair_group, {})
            .get(candidate_hero)
        )
        if not candidate_pair:
            continue
        candidate_role_payload = candidate_pair.get("roles", {}).get(candidate_role_key)
        if not candidate_role_payload:
            continue
        score_payload = candidate_role_payload.get(score_name)
        if not score_payload:
            continue
        raw = score_payload.get("raw")
        confidence = score_payload.get("confidence")
        weight = float(prior.get("weight") or 0.0)
        if raw is None or weight <= 0:
            continue
        weighted_raws.append((raw, weight))
        if confidence is not None:
            weighted_confidence.append((confidence, weight))
        resolved_roles.append(
            {
                "roleKey": role_key,
                "role": target_role_data.get("role"),
                "weight": weight,
                "raw": raw,
                "confidence": confidence,
            }
        )

    if not weighted_raws:
        return None

    return {
        "raw": weighted_mean(weighted_raws),
        "confidence": weighted_mean(weighted_confidence) if weighted_confidence else None,
        "normalized": None,
        "resolvedRoles": resolved_roles,
        "usedRolePriors": True,
    }


def adapt_score_perspective(score: dict | None, *, invert_raw: bool) -> dict | None:
    if not score:
        return None

    adapted = {
        "raw": score.get("raw"),
        "confidence": score.get("confidence"),
        "normalized": score.get("normalized"),
        "resolvedRoles": [],
        "usedRolePriors": bool(score.get("usedRolePriors")),
    }
    if invert_raw and adapted["raw"] is not None:
        adapted["raw"] = -float(adapted["raw"])

    for role_info in score.get("resolvedRoles", []):
        adapted_role = dict(role_info)
        if invert_raw and adapted_role.get("raw") is not None:
            adapted_role["raw"] = -float(adapted_role["raw"])
        adapted["resolvedRoles"].append(adapted_role)

    return adapted


def combine_score_views(
    direct_score: dict | None,
    reverse_score: dict | None,
) -> dict | None:
    sources = []
    for name, score in (("direct", direct_score), ("reciprocal", reverse_score)):
        if not score or score.get("raw") is None:
            continue
        confidence = float(score.get("confidence") or 0.0)
        sources.append((name, score, confidence))

    if not sources:
        return None

    total_weight = sum(confidence for _name, _score, confidence in sources)
    use_equal_weights = total_weight <= 0
    if use_equal_weights:
        total_weight = float(len(sources))

    weighted_parts = []
    for name, score, confidence in sources:
        weight = 1.0 if use_equal_weights else confidence
        weighted_parts.append((name, score, weight))

    raw = sum(float(score["raw"]) * weight for _name, score, weight in weighted_parts) / total_weight
    confidence = sum(float(score.get("confidence") or 0.0) * weight for _name, score, weight in weighted_parts) / total_weight
    weights = {
        name: (weight / total_weight) if total_weight > 0 else 0.0
        for name, _score, weight in weighted_parts
    }

    return {
        "raw": raw,
        "confidence": confidence,
        "normalized": None,
        "weights": weights,
        "sourcesUsed": [name for name, _score, _weight in weighted_parts],
    }


def round_optional(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def build_score_view_payload(score: dict | None) -> dict:
    if not score or score.get("raw") is None:
        return {
            "available": False,
            "raw": None,
            "confidence": None,
            "usedRolePriors": False,
            "resolvedRoles": [],
        }

    return {
        "available": True,
        "raw": round_optional(score.get("raw")),
        "confidence": round_optional(score.get("confidence")),
        "usedRolePriors": bool(score.get("usedRolePriors")),
        "resolvedRoles": [
            {
                "roleKey": role_info.get("roleKey"),
                "role": role_info.get("role"),
                "weight": round_optional(role_info.get("weight")),
                "raw": round_optional(role_info.get("raw")),
                "confidence": round_optional(role_info.get("confidence")),
            }
            for role_info in score.get("resolvedRoles", [])
        ],
    }


def build_combined_view_payload(score: dict | None) -> dict:
    if not score or score.get("raw") is None:
        return {
            "available": False,
            "raw": None,
            "confidence": None,
            "weights": {},
            "sourcesUsed": [],
        }

    return {
        "available": True,
        "raw": round_optional(score.get("raw")),
        "confidence": round_optional(score.get("confidence")),
        "weights": {
            name: round_optional(weight)
            for name, weight in score.get("weights", {}).items()
        },
        "sourcesUsed": list(score.get("sourcesUsed", [])),
    }


def score_candidate(
    scores_payload: dict,
    hero_name: str,
    candidate_role_key: str,
    allies: list[tuple[str, str | None]],
    enemies: list[tuple[str, str | None]],
    bans: list[tuple[str, str | None]],
) -> dict | None:
    hero_data = scores_payload["heroes"].get(hero_name)
    if not hero_data:
        return None

    role_data = hero_data.get("roles", {}).get(candidate_role_key)
    if not role_data:
        return None

    overall = role_data["overall"]
    baseline_win_raw = overall["compositeWin"]["raw"] or 0.0
    baseline_win_conf = overall["compositeWin"]["confidence"] or 0.0

    baseline_lane_raw = (
        DRAFT_WEIGHTS["lane_baseline_matchup"] * (overall["matchupLane"]["raw"] or 0.0)
        + DRAFT_WEIGHTS["lane_baseline_synergy"] * (overall["synergyLane"]["raw"] or 0.0)
    )
    baseline_lane_conf = (
        DRAFT_WEIGHTS["lane_baseline_matchup"] * (overall["matchupLane"]["confidence"] or 0.0)
        + DRAFT_WEIGHTS["lane_baseline_synergy"] * (overall["synergyLane"]["confidence"] or 0.0)
    )

    enemy_win_contribs = []
    enemy_win_direct_contribs = []
    enemy_win_reverse_contribs = []
    enemy_lane_contribs = []
    enemy_lane_direct_contribs = []
    enemy_lane_reverse_contribs = []
    enemy_details = []
    for target_hero, target_role_key in enemies:
        direct_win_score = resolve_pair_score(
            scores_payload,
            role_data,
            "vs",
            target_hero,
            "win",
            target_role_key=target_role_key,
        )
        reciprocal_win_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "vs",
                target_hero,
                "win",
                target_role_key=target_role_key,
            ),
            invert_raw=True,
        )
        combined_win_score = combine_score_views(direct_win_score, reciprocal_win_score)

        direct_lane_score = resolve_pair_score(
            scores_payload,
            role_data,
            "vs",
            target_hero,
            "lane",
            target_role_key=target_role_key,
        )
        reciprocal_lane_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "vs",
                target_hero,
                "lane",
                target_role_key=target_role_key,
            ),
            invert_raw=True,
        )
        combined_lane_score = combine_score_views(direct_lane_score, reciprocal_lane_score)

        win_raw = combined_win_score["raw"] if combined_win_score and combined_win_score.get("raw") is not None else 0.0
        lane_raw = combined_lane_score["raw"] if combined_lane_score and combined_lane_score.get("raw") is not None else 0.0
        enemy_win_contribs.append(win_raw)
        enemy_lane_contribs.append(lane_raw)
        enemy_win_direct_contribs.append(
            direct_win_score["raw"] if direct_win_score and direct_win_score.get("raw") is not None else 0.0
        )
        enemy_win_reverse_contribs.append(
            reciprocal_win_score["raw"] if reciprocal_win_score and reciprocal_win_score.get("raw") is not None else 0.0
        )
        enemy_lane_direct_contribs.append(
            direct_lane_score["raw"] if direct_lane_score and direct_lane_score.get("raw") is not None else 0.0
        )
        enemy_lane_reverse_contribs.append(
            reciprocal_lane_score["raw"] if reciprocal_lane_score and reciprocal_lane_score.get("raw") is not None else 0.0
        )
        enemy_details.append(
            {
                "hero": target_hero,
                "roleKey": target_role_key,
                "role": ROLE_BY_KEY.get(target_role_key) if target_role_key else None,
                "winRaw": round(win_raw, 4),
                "laneRaw": round(lane_raw, 4),
                "winViews": {
                    "direct": build_score_view_payload(direct_win_score),
                    "reciprocal": build_score_view_payload(reciprocal_win_score),
                    "combined": build_combined_view_payload(combined_win_score),
                },
                "laneViews": {
                    "direct": build_score_view_payload(direct_lane_score),
                    "reciprocal": build_score_view_payload(reciprocal_lane_score),
                    "combined": build_combined_view_payload(combined_lane_score),
                },
            }
        )

    ally_win_contribs = []
    ally_win_direct_contribs = []
    ally_win_reverse_contribs = []
    ally_lane_contribs = []
    ally_lane_direct_contribs = []
    ally_lane_reverse_contribs = []
    ally_details = []
    for target_hero, target_role_key in allies:
        direct_win_score = resolve_pair_score(
            scores_payload,
            role_data,
            "with",
            target_hero,
            "win",
            target_role_key=target_role_key,
        )
        reciprocal_win_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "with",
                target_hero,
                "win",
                target_role_key=target_role_key,
            ),
            invert_raw=False,
        )
        combined_win_score = combine_score_views(direct_win_score, reciprocal_win_score)

        direct_lane_score = resolve_pair_score(
            scores_payload,
            role_data,
            "with",
            target_hero,
            "lane",
            target_role_key=target_role_key,
        )
        reciprocal_lane_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "with",
                target_hero,
                "lane",
                target_role_key=target_role_key,
            ),
            invert_raw=False,
        )
        combined_lane_score = combine_score_views(direct_lane_score, reciprocal_lane_score)

        win_raw = combined_win_score["raw"] if combined_win_score and combined_win_score.get("raw") is not None else 0.0
        lane_raw = combined_lane_score["raw"] if combined_lane_score and combined_lane_score.get("raw") is not None else 0.0
        ally_win_contribs.append(win_raw)
        ally_lane_contribs.append(lane_raw)
        ally_win_direct_contribs.append(
            direct_win_score["raw"] if direct_win_score and direct_win_score.get("raw") is not None else 0.0
        )
        ally_win_reverse_contribs.append(
            reciprocal_win_score["raw"] if reciprocal_win_score and reciprocal_win_score.get("raw") is not None else 0.0
        )
        ally_lane_direct_contribs.append(
            direct_lane_score["raw"] if direct_lane_score and direct_lane_score.get("raw") is not None else 0.0
        )
        ally_lane_reverse_contribs.append(
            reciprocal_lane_score["raw"] if reciprocal_lane_score and reciprocal_lane_score.get("raw") is not None else 0.0
        )
        ally_details.append(
            {
                "hero": target_hero,
                "roleKey": target_role_key,
                "role": ROLE_BY_KEY.get(target_role_key) if target_role_key else None,
                "winRaw": round(win_raw, 4),
                "laneRaw": round(lane_raw, 4),
                "winViews": {
                    "direct": build_score_view_payload(direct_win_score),
                    "reciprocal": build_score_view_payload(reciprocal_win_score),
                    "combined": build_combined_view_payload(combined_win_score),
                },
                "laneViews": {
                    "direct": build_score_view_payload(direct_lane_score),
                    "reciprocal": build_score_view_payload(reciprocal_lane_score),
                    "combined": build_combined_view_payload(combined_lane_score),
                },
            }
        )

    ban_relief_win_contribs = []
    ban_relief_win_direct_contribs = []
    ban_relief_win_reverse_contribs = []
    ban_relief_lane_contribs = []
    ban_relief_lane_direct_contribs = []
    ban_relief_lane_reverse_contribs = []
    ban_details = []
    for target_hero, target_role_key in bans:
        direct_win_score = resolve_pair_score(
            scores_payload,
            role_data,
            "vs",
            target_hero,
            "win",
            target_role_key=target_role_key,
        )
        reciprocal_win_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "vs",
                target_hero,
                "win",
                target_role_key=target_role_key,
            ),
            invert_raw=True,
        )
        combined_win_score = combine_score_views(direct_win_score, reciprocal_win_score)

        direct_lane_score = resolve_pair_score(
            scores_payload,
            role_data,
            "vs",
            target_hero,
            "lane",
            target_role_key=target_role_key,
        )
        reciprocal_lane_score = adapt_score_perspective(
            resolve_reverse_pair_score(
                scores_payload,
                hero_name,
                candidate_role_key,
                "vs",
                target_hero,
                "lane",
                target_role_key=target_role_key,
            ),
            invert_raw=True,
        )
        combined_lane_score = combine_score_views(direct_lane_score, reciprocal_lane_score)

        direct_base_win_raw = direct_win_score["raw"] if direct_win_score and direct_win_score.get("raw") is not None else 0.0
        reciprocal_base_win_raw = reciprocal_win_score["raw"] if reciprocal_win_score and reciprocal_win_score.get("raw") is not None else 0.0
        base_win_raw = combined_win_score["raw"] if combined_win_score and combined_win_score.get("raw") is not None else 0.0

        direct_base_lane_raw = direct_lane_score["raw"] if direct_lane_score and direct_lane_score.get("raw") is not None else 0.0
        reciprocal_base_lane_raw = reciprocal_lane_score["raw"] if reciprocal_lane_score and reciprocal_lane_score.get("raw") is not None else 0.0
        base_lane_raw = combined_lane_score["raw"] if combined_lane_score and combined_lane_score.get("raw") is not None else 0.0

        relief_win_raw = max(0.0, -base_win_raw)
        relief_lane_raw = max(0.0, -base_lane_raw)
        direct_relief_win_raw = max(0.0, -direct_base_win_raw)
        reciprocal_relief_win_raw = max(0.0, -reciprocal_base_win_raw)
        direct_relief_lane_raw = max(0.0, -direct_base_lane_raw)
        reciprocal_relief_lane_raw = max(0.0, -reciprocal_base_lane_raw)
        ban_relief_win_contribs.append(relief_win_raw)
        ban_relief_lane_contribs.append(relief_lane_raw)
        ban_relief_win_direct_contribs.append(direct_relief_win_raw)
        ban_relief_win_reverse_contribs.append(reciprocal_relief_win_raw)
        ban_relief_lane_direct_contribs.append(direct_relief_lane_raw)
        ban_relief_lane_reverse_contribs.append(reciprocal_relief_lane_raw)
        ban_details.append(
            {
                "hero": target_hero,
                "roleKey": target_role_key,
                "role": ROLE_BY_KEY.get(target_role_key) if target_role_key else None,
                "baseWinRaw": round(base_win_raw, 4),
                "baseLaneRaw": round(base_lane_raw, 4),
                "reliefWinRaw": round(relief_win_raw, 4),
                "reliefLaneRaw": round(relief_lane_raw, 4),
                "winViews": {
                    "direct": build_score_view_payload(direct_win_score),
                    "reciprocal": build_score_view_payload(reciprocal_win_score),
                    "combined": build_combined_view_payload(combined_win_score),
                },
                "laneViews": {
                    "direct": build_score_view_payload(direct_lane_score),
                    "reciprocal": build_score_view_payload(reciprocal_lane_score),
                    "combined": build_combined_view_payload(combined_lane_score),
                },
                "reliefViews": {
                    "win": {
                        "direct": round_optional(direct_relief_win_raw),
                        "reciprocal": round_optional(reciprocal_relief_win_raw),
                        "combined": round_optional(relief_win_raw),
                    },
                    "lane": {
                        "direct": round_optional(direct_relief_lane_raw),
                        "reciprocal": round_optional(reciprocal_relief_lane_raw),
                        "combined": round_optional(relief_lane_raw),
                    },
                },
            }
        )

    enemy_win_avg = average_or_zero(enemy_win_contribs)
    enemy_win_direct_avg = average_or_zero(enemy_win_direct_contribs)
    enemy_win_reverse_avg = average_or_zero(enemy_win_reverse_contribs)
    enemy_lane_avg = average_or_zero(enemy_lane_contribs)
    enemy_lane_direct_avg = average_or_zero(enemy_lane_direct_contribs)
    enemy_lane_reverse_avg = average_or_zero(enemy_lane_reverse_contribs)
    ally_win_avg = average_or_zero(ally_win_contribs)
    ally_win_direct_avg = average_or_zero(ally_win_direct_contribs)
    ally_win_reverse_avg = average_or_zero(ally_win_reverse_contribs)
    ally_lane_avg = average_or_zero(ally_lane_contribs)
    ally_lane_direct_avg = average_or_zero(ally_lane_direct_contribs)
    ally_lane_reverse_avg = average_or_zero(ally_lane_reverse_contribs)
    ban_relief_win_avg = average_or_zero(ban_relief_win_contribs)
    ban_relief_win_direct_avg = average_or_zero(ban_relief_win_direct_contribs)
    ban_relief_win_reverse_avg = average_or_zero(ban_relief_win_reverse_contribs)
    ban_relief_lane_avg = average_or_zero(ban_relief_lane_contribs)
    ban_relief_lane_direct_avg = average_or_zero(ban_relief_lane_direct_contribs)
    ban_relief_lane_reverse_avg = average_or_zero(ban_relief_lane_reverse_contribs)

    draft_win_raw = (
        baseline_win_raw
        + DRAFT_WEIGHTS["enemy"] * enemy_win_avg
        + DRAFT_WEIGHTS["ally"] * ally_win_avg
        + DRAFT_WEIGHTS["ban_relief"] * ban_relief_win_avg
    )
    draft_lane_raw = (
        baseline_lane_raw
        + DRAFT_WEIGHTS["enemy"] * enemy_lane_avg
        + DRAFT_WEIGHTS["ally_lane"] * ally_lane_avg
        + DRAFT_WEIGHTS["ban_relief_lane"] * ban_relief_lane_avg
    )
    draft_composite_raw = (
        DRAFT_WEIGHTS["composite_win"] * draft_win_raw
        + DRAFT_WEIGHTS["composite_lane"] * draft_lane_raw
    )

    confidence_terms = [baseline_win_conf, baseline_lane_conf]
    for details in (enemy_details, ally_details, ban_details):
        for detail in details:
            for view_key in ("winViews", "laneViews"):
                combined_view = detail.get(view_key, {}).get("combined", {})
                if combined_view.get("available") and combined_view.get("confidence") is not None:
                    confidence_terms.append(float(combined_view["confidence"]))
    draft_confidence = sum(confidence_terms) / len(confidence_terms) if confidence_terms else 0.0

    return {
        "hero": hero_name,
        "roleKey": candidate_role_key,
        "role": role_data["role"],
        "baseline": {
            "compositeWinRaw": round(baseline_win_raw, 4),
            "compositeWinNormalized": overall["compositeWin"]["normalized"],
            "compositeWinConfidence": round(baseline_win_conf, 4),
            "laneRaw": round(baseline_lane_raw, 4),
            "laneConfidence": round(baseline_lane_conf, 4),
        },
        "components": {
            "enemyWinRaw": round(enemy_win_avg, 4),
            "enemyWinDirectRaw": round(enemy_win_direct_avg, 4),
            "enemyWinReciprocalRaw": round(enemy_win_reverse_avg, 4),
            "enemyLaneRaw": round(enemy_lane_avg, 4),
            "enemyLaneDirectRaw": round(enemy_lane_direct_avg, 4),
            "enemyLaneReciprocalRaw": round(enemy_lane_reverse_avg, 4),
            "allyWinRaw": round(ally_win_avg, 4),
            "allyWinDirectRaw": round(ally_win_direct_avg, 4),
            "allyWinReciprocalRaw": round(ally_win_reverse_avg, 4),
            "allyLaneRaw": round(ally_lane_avg, 4),
            "allyLaneDirectRaw": round(ally_lane_direct_avg, 4),
            "allyLaneReciprocalRaw": round(ally_lane_reverse_avg, 4),
            "banReliefWinRaw": round(ban_relief_win_avg, 4),
            "banReliefWinDirectRaw": round(ban_relief_win_direct_avg, 4),
            "banReliefWinReciprocalRaw": round(ban_relief_win_reverse_avg, 4),
            "banReliefLaneRaw": round(ban_relief_lane_avg, 4),
            "banReliefLaneDirectRaw": round(ban_relief_lane_direct_avg, 4),
            "banReliefLaneReciprocalRaw": round(ban_relief_lane_reverse_avg, 4),
        },
        "draft": {
            "winRaw": round(draft_win_raw, 4),
            "laneRaw": round(draft_lane_raw, 4),
            "compositeRaw": round(draft_composite_raw, 4),
            "confidence": round(draft_confidence, 4),
            "winNormalized": None,
            "laneNormalized": None,
            "compositeNormalized": None,
        },
        "details": {
            "enemy": enemy_details,
            "ally": ally_details,
            "ban": ban_details,
        },
    }


def finalize_candidate_normalization(rows: list[dict]) -> None:
    win_scale = family_scale([row["draft"]["winRaw"] for row in rows])
    lane_scale = family_scale([row["draft"]["laneRaw"] for row in rows])
    composite_scale = family_scale([row["draft"]["compositeRaw"] for row in rows])

    for row in rows:
        row["draft"]["winNormalized"] = round(
            float(normalize_raw(row["draft"]["winRaw"], win_scale)), 2
        )
        row["draft"]["laneNormalized"] = round(
            float(normalize_raw(row["draft"]["laneRaw"], lane_scale)), 2
        )
        row["draft"]["compositeNormalized"] = round(
            float(normalize_raw(row["draft"]["compositeRaw"], composite_scale)), 2
        )


def main() -> int:
    args = parse_args()
    scores_payload = load_json(Path(args.scores))
    hero_lookup = build_hero_lookup(scores_payload)

    candidate_role_key = resolve_role_key(args.candidate_role)
    if not candidate_role_key:
        raise SystemExit(f"Unknown candidate role: {args.candidate_role}")

    allies = [parse_hero_spec(spec, hero_lookup) for spec in args.ally]
    enemies = [parse_hero_spec(spec, hero_lookup) for spec in args.enemy]
    bans = [parse_hero_spec(spec, hero_lookup) for spec in args.ban]

    excluded_heroes = {hero for hero, _role in allies + enemies + bans}
    rows = []
    for hero_name in sorted(scores_payload.get("heroes", {})):
        if hero_name in excluded_heroes:
            continue
        candidate = score_candidate(
            scores_payload,
            hero_name,
            candidate_role_key,
            allies,
            enemies,
            bans,
        )
        if candidate is not None:
            rows.append(candidate)

    if not rows:
        raise SystemExit("No candidates found for the requested role.")

    finalize_candidate_normalization(rows)
    rows.sort(
        key=lambda row: (
            -row["draft"]["compositeNormalized"],
            -row["draft"]["winNormalized"],
            -row["draft"]["confidence"],
            row["hero"],
        )
    )

    if args.json:
        print(
            json.dumps(
                {
                    "candidateRole": candidate_role_key,
                    "candidateRoleLabel": ROLE_BY_KEY[candidate_role_key],
                    "allies": allies,
                    "enemies": enemies,
                    "bans": bans,
                    "rows": rows[: args.top],
                },
                indent=2,
            )
        )
        return 0

    print(
        f"Top {min(args.top, len(rows))} candidates for role "
        f"{candidate_role_key} ({ROLE_BY_KEY[candidate_role_key]})"
    )
    if allies:
        print("Allies:", ", ".join(
            f"{hero}{':' + ROLE_BY_KEY[role] if role else ''}" for hero, role in allies
        ))
    if enemies:
        print("Enemies:", ", ".join(
            f"{hero}{':' + ROLE_BY_KEY[role] if role else ''}" for hero, role in enemies
        ))
    if bans:
        print("Bans:", ", ".join(
            f"{hero}{':' + ROLE_BY_KEY[role] if role else ''}" for hero, role in bans
        ))
    print()
    print("Rank  Hero                     Role           Draft   Win     Lane    Conf")
    print("----  -----------------------  -------------  ------  ------  ------  -----")
    for index, row in enumerate(rows[: args.top], start=1):
        print(
            f"{index:>4}  "
            f"{row['hero'][:23]:<23}  "
            f"{row['role'][:13]:<13}  "
            f"{row['draft']['compositeNormalized']:>6.2f}  "
            f"{row['draft']['winNormalized']:>6.2f}  "
            f"{row['draft']['laneNormalized']:>6.2f}  "
            f"{row['draft']['confidence']:>5.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
