"""Unit tests for the standalone stifling_dagger calculation."""

import pytest

from spells.stifling_dagger import stifling_dagger
from spell_calculations import (
    apply_physical_resistance,
    apply_magic_resistance,
)


def test_physical_damage_basic():
    caster = {"attack_damage": 100}
    result = stifling_dagger(caster, level_index=0, target={"armor": 10})

    assert result["damage_type"] == "Physical"
    assert result["raw"] == pytest.approx(95)  # 100*0.3 + 65

    expected_after = apply_physical_resistance(95, 10)
    assert result["after_reduction"] == pytest.approx(expected_after)

    # metadata should be returned
    assert result["mana_cost"] == 30
    assert result["cooldown"] == 6
    # cast_range should correspond to chosen level
    assert result["cast_range"] == STIFLING_DAGGER_STATS["cast_range"][0]
    assert result["cast_animation"] == STIFLING_DAGGER_STATS["cast_animation"]

    # if we ask at a higher level, range updates accordingly
    lvl2 = stifling_dagger(caster, level_index=2, target={"armor":10})
    assert lvl2["cast_range"] == STIFLING_DAGGER_STATS["cast_range"][2]

    # talents should modify raw damage and cooldown when provided
    # boolean talent flags now control the effects
    tstr = {"attack_damage":100,
            "stifling_dagger_instant_attack_damage_pct": True,
            "stifling_dagger_cooldown": True}
    tres = stifling_dagger(tstr, level_index=0, target={"armor":0})
    # factor was 0.3 originally; +0.15 gives 0.45
    assert tres["raw"] == pytest.approx(100*0.45 + 65)
    assert tres["cooldown"] == STIFLING_DAGGER_STATS["cooldown"] - 2

    # sweet_release should add other_damage equal to half raw
    sres = stifling_dagger({"attack_damage":100, "sweet_release": True}, level_index=0, target={"armor":0})
    assert sres["other_damage"] == pytest.approx((100*0.3+65)*0.5)
    assert tres.get("other_damage") is None




def test_missing_fields_default_sane_values():
    # caster with no attack_damage yields zero
    result = stifling_dagger({}, level_index=0, target={"armor": 0})

    assert result["raw"] == 0
    assert result["after_reduction"] == 0
    assert result["damage_type"] == "Physical"


def test_static_tooltip_values_exposed():
    # ensure the module exports the expected constants matching the PNG
    from spells.stifling_dagger import STIFLING_DAGGER_STATS, STIFLING_DAGGER_DAMAGE_BY_LEVEL

    assert STIFLING_DAGGER_STATS["mana_cost"] == 30
    assert STIFLING_DAGGER_STATS["cast_range"] == [700, 850, 1000, 1150]
    assert STIFLING_DAGGER_STATS["move_speed_slow_pct"] == 50
    assert STIFLING_DAGGER_STATS["instant_attack_factor"] == [0.3, 0.45, 0.6, 0.75]
    assert STIFLING_DAGGER_STATS["attack_damage_bonus"] == [65, 70, 75, 80]
    assert STIFLING_DAGGER_DAMAGE_BY_LEVEL == [82.1, 95.65, 109.2, 122.75]


def test_resistance_helpers_public():
    # ensure the shared helpers are available
    assert apply_physical_resistance(100, 10) == pytest.approx(
        (100 * (1 - ((0.06 * 10) / (1 + 0.06 * abs(10)))))
    )
    assert apply_magic_resistance(200, 0.5) == pytest.approx(100)


def test_attack_factor_and_bonus_applied():
    caster = {"attack_damage": 50}
    result = stifling_dagger(caster, level_index=1, target={"armor": 0})
    assert result["raw"] == pytest.approx(50*0.45 + 70)


def test_multiple_hits_and_armor():
    # signature no longer accepts hits; just verify armor application
    single = stifling_dagger({"attack_damage":100}, level_index=0, target={"armor": 0})
    double = stifling_dagger({"attack_damage":100}, level_index=0, target={"armor": 10})
    assert double["raw"] == pytest.approx(single["raw"])
    assert double["after_reduction"] < double["raw"]


# modifiers are expected to be applied by the caller; this helper
# simply uses the provided attack_damage value.  no separate test is needed here.


def test_debuff_aggregation():
    caster = {"attack_damage": 50, "slow_pct": 25, "slow_duration": 2.5,
              "on_hit_modifiers": [{"type": "stun", "value": 1, "duration": 0.5}]}
    result = stifling_dagger(caster, level_index=0, target={"armor":0})
    assert any(d.get("type") == "slow" for d in result["debuffs"])
    assert any(d.get("type") == "stun" for d in result["debuffs"])
