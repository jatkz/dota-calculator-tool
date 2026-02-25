"""Standalone logic for Phantom Assassin's Stifling Dagger spell.

The goal of this module is to isolate the damage calculation so it can be
reviewed, tested and reused without coupling to the GUI or hero rows.  The
entry point takes a lightweight ``caster`` payload and a ``target`` dict and
returns raw/reduced damage plus a handful of static ability values.

Only the fields actually used by the math are required; callers may supply
additional keys (talent flags, slow data, on-hit modifiers) and the helper
will include them in the result when relevant.

Example usage::

    caster = {"attack_damage": 82.1,
              "stifling_dagger_instant_attack_damage_pct": True,
              "stifling_dagger_cooldown": True}
    target = {"armor": 10}
    result = stifling_dagger(caster, level_index=0, target=target)
    # {
    #   "raw": 82.1*0.45+65,
    #   "after_reduction": <reduced>,
    #   "damage_type": "Physical",
    #   "mana_cost": 30, ...
    # }
"""

from typing import Dict

# rely on central resistance formula
from spell_calculations import apply_physical_resistance


# --- static spell metadata ------------------------------------------------
# The following data is drawn directly from the in‑game tooltip shown in the
# provided PNG screenshot.  Having these values available in the module makes
# it easy for other parts of the codebase (or future tests) to reference
# cast ranges, slow percentages, talent descriptions, etc., without digging
# through JSON or UI logic.
#
# Values are organised by level index (0‑based) where appropriate.

STIFLING_DAGGER_STATS = {
    # only the initial cast animation portion is needed
    "cast_animation": 0.3,
    "cast_range": [700, 850, 1000, 1150],
    "targets": 1,  # becomes 3 with level‑25 talent (mask below)
    "instant_attack_factor": [0.3, 0.45, 0.6, 0.75],
    "attack_damage_bonus": [65, 70, 75, 80],
    "move_speed_slow_pct": 50,  # constant across levels
    "slow_duration": [2.1, 2.4, 2.7, 3.0],
    "talent_upgrade": "Launches additional Stifling Daggers upon cast toward"
                       " other random enemy units centered around the"
                       " unit-targeted enemy.",
    "shard_upgrade": "Advances Stifling Dagger's cooldown per hero kill"
                       " credited to Mortred.",
    "mana_cost": 30,
    "cooldown": 6,
}


def stifling_dagger(caster: Dict, level_index: int, target: Dict) -> Dict:
    """Compute Stifling Dagger damage using a caster payload and explicit level.

    Args:
        caster: dictionary containing at least:
            - "attack_damage" (float): final attack damage value to use.
        level_index: zero-based ability level (0..3); controls factor/bonus.
        target: dict with key "armor" (float) for physical resistance.

    The spell always deals one dagger; hits are not part of this helper.  Any
    attack modifiers (crit, minus armor, talent bonuses, etc.) should already
    have been applied to ``caster["attack_damage"]`` by the caller.

    Returns:
        A dict with "raw", "after_reduction", and "damage_type" keys.
    """

    attack_damage = float(caster.get("attack_damage", 0) or 0)
    lvl_idx = max(0, min(level_index, len(STIFLING_DAGGER_STATS["instant_attack_factor"]) - 1))

    factor = STIFLING_DAGGER_STATS["instant_attack_factor"][lvl_idx]
    bonus = STIFLING_DAGGER_STATS["attack_damage_bonus"][lvl_idx]

    # apply instant attack damage talent flag by bumping the factor
    if caster.get("stifling_dagger_instant_attack_damage_pct"):
        factor += 0.15
    raw = attack_damage * factor + bonus

    armor = float(target.get("armor", 0) or 0)
    reduced = apply_physical_resistance(raw, armor)

    # collect debuffs: slow info plus any on-hit modifiers provided by caster
    debuffs = []
    slow_val = caster.get("slow_pct") or caster.get("move_speed_slow_pct")
    if slow_val is not None:
        debuffs.append({
            "type": "slow",
            "value": slow_val,
            "duration": caster.get("slow_duration"),
        })
    for mod in caster.get("on_hit_modifiers", []) or []:
        if isinstance(mod, dict):
            debuffs.append(mod)

    # optional addon from sweet_release talent
    other_damage = None
    if caster.get("sweet_release"):
        other_damage = raw * 0.5

    return {
        "raw": raw,
        "after_reduction": reduced,
        "damage_type": "Physical",
        "debuffs": debuffs,
        "mana_cost": STIFLING_DAGGER_STATS.get("mana_cost"),
        "cooldown": STIFLING_DAGGER_STATS.get("cooldown")
                    - (2 if caster.get("stifling_dagger_cooldown") else 0),
        "cast_range": STIFLING_DAGGER_STATS.get("cast_range")[lvl_idx],
        "cast_animation": STIFLING_DAGGER_STATS.get("cast_animation"),
        "other_damage": other_damage,
    }
