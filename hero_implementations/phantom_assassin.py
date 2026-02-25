"""Phantom Assassin hero-specific implementation."""

import json


from hero_implementations.default import DefaultHeroImplementation
from hero_implementations.helpers import build_talents_payload, deep_copy, make_effect


def calculate_attributes(level):
  return dict(
    strength=2*level,
    agility=2*level,
    intelligence=2*level
  )

class PhantomAssassinImplementation(DefaultHeroImplementation):
    # basic static attributes for display / default initialization
    name = "Phantom Assassin"
    attribute_type = "Agility"
    level = 1
    base_hp = 120
    base_hp_regen = 1
    movespeed = 310
    attack_speed = 110
    bat = 1.7
    base_damage = 36
    base_armor = 1
    base_magic_resist = 25
    evasion = 0
    strength = 19
    agility = 21
    intelligence = 15
    strength_per_level = 2
    agility_per_level = 3.4
    intelligence_per_level = 1.7
    turn_rate = 0.8

    # talent tier definitions (modifier-ready format)
    talent_tiers = [
        {
            "level": 10,
            "options": [
                {
                    "label": "-2s Stifling Dagger Cooldown",
                    "modifiers": {"stifling_dagger_cooldown": -2},
                    "selected": False
                },
                {
                    "label": "+0.6s Phantom Strike Duration",
                    "modifiers": {"phantom_strike_duration": 0.6},
                    "selected": False
                }
            ]
        },
        {
            "level": 15,
            "options": [
                {
                    "label": "+15% Stifling Dagger Instant Attack Damage",
                    "modifiers": {"stifling_dagger_instant_attack_damage_pct": 15},
                    "selected": False
                },
                {
                    "label": "+20% Immaterial Evasion",
                    "modifiers": {"immaterial_evasion_pct": 20},
                    "selected": False
                }
            ]
        },
        {
            "level": 20,
            "options": [
                {
                    "label": "+60 Phantom Strike Attack Speed",
                    "modifiers": {"phantom_strike_attack_speed": 60},
                    "selected": False
                },
                {
                    "label": "+200 Phantom Strike Cast Range",
                    "modifiers": {"phantom_strike_cast_range": 200},
                    "selected": False
                }
            ]
        },
        {
            "level": 25,
            "options": [
                {
                    "label": "Triple Stifling Dagger Strikes",
                    "modifiers": {"stifling_dagger_triple_strike": True},
                    "selected": False
                },
                {
                    "label": "+10% Coup de Grace Chance, -1 Methodical Required Attacks",
                    "modifiers": {
                        "coup_de_grace_chance_pct": 10,
                        "methodical_required_attacks_delta": -1
                    },
                    "selected": False
                }
            ]
        }
    ]

    @classmethod
    def hero_key(cls):
        """Return the normalized key used by the registry."""
        return "Phantom Assassin"

    def evaluate_spell(self, spell_state, hero_state, context):
        """Dispatch evaluation to special handlers when required."""
        spell_name = spell_state.get("spell_name", "").lower()
        if "stifling" in spell_name:
            return self.stiflingdagger(spell_state, hero_state, context)
        # default implementation simply returns empty dict
        return super().evaluate_spell(spell_state, hero_state, context)

    def stiflingdagger(self, spell_state, hero_state, context):
        """Compute Stifling Dagger damage/effects by delegating to the
        standalone helper.

        This keeps the hero-specific implementation thin; the actual math lives
        in ``stifling_dagger.py`` so it can be tested independently and reused by
        other modules if needed.
        """
        from spells.stifling_dagger import stifling_dagger as _sd

        # build minimal caster / target payloads from the incoming state
        level_data = spell_state.get("level_data", {}) or {}
        # determine inputs for helper
        attack_damage = hero_state.get("hero_auto_attack_damage", 0.0)
        level_idx = spell_state.get("level_index", 0)
        # hits are always one at the spell level; talents handled elsewhere if needed

        # target information is pulled from evaluation context.  the
        # frontend currently provides a list of simple target dicts under
        # "selected_targets"; take the first entry if present.  this keeps the
        # helper signature simple while still allowing the UI to drive
        # reductions.
        target_info = {}
        if isinstance(context, dict):
            sel = context.get("selected_targets")
            if isinstance(sel, list) and sel:
                # copy only the keys our standalone helper understands
                first = sel[0]
                if isinstance(first, dict):
                    if "armor" in first:
                        target_info["armor"] = first.get("armor")
                    if "magic_resistance" in first:
                        target_info["magic_resistance"] = first.get("magic_resistance")
            # allow an explicit override via context["target"] if desired
            explicit = context.get("target")
            if isinstance(explicit, dict):
                target_info.update(explicit)

        # get the raw/reduced damage values; start with attack_damage
        caster_payload = {"attack_damage": attack_damage}
        # propagate any slow/metadata or on-hit modifiers so the helper can
        # aggregate debuffs.  this keeps the hero-specific code simple while
        # letting the standalone module own the logic for building the list.
        metadata = spell_state.get("metadata", {}) or {}
        if "slow_pct" in metadata:
            caster_payload["slow_pct"] = metadata["slow_pct"]
        if "slow_duration" in metadata:
            caster_payload["slow_duration"] = metadata["slow_duration"]
        if "on_hit_modifiers" in metadata:
            caster_payload["on_hit_modifiers"] = metadata["on_hit_modifiers"]

        # apply talent-derived boolean flags based on hero_state effects
        for eff in hero_state.get("talent_effects", []) or []:
            if not isinstance(eff, dict):
                continue
            field = eff.get("field")
            # instant attack damage talent
            if field == "stifling_dagger_instant_attack_damage_pct":
                caster_payload["stifling_dagger_instant_attack_damage_pct"] = True
            elif field == "stifling_dagger_cooldown":
                caster_payload["stifling_dagger_cooldown"] = True

        dmg = _sd(caster_payload, level_idx, target_info)

        # the helper already returned any debuffs; we simply forward them.
        return {
            "damage": dmg["raw"],
            "damage_type": dmg["damage_type"],
            "hits": 1,  # stifling dagger always hits once
            "debuffs": dmg.get("debuffs", []),
            "damage_after_reduction": dmg["after_reduction"],
        }

    