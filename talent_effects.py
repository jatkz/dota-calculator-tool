"""Talent helpers and compatibility adapters."""

from hero_implementations.helpers import build_talents_payload, deep_copy, normalize_key
from hero_implementations.registry import HeroImplementationRegistry


def _effect(effect_id, tier_level, side, label, target, field, operation, value, simulated, note=""):
    """Compatibility helper for existing callers/tests."""
    return {
        "id": effect_id,
        "tier_level": tier_level,
        "side": side,
        "label": label,
        "target": target,
        "field": field,
        "operation": operation,
        "value": value,
        "simulated": bool(simulated),
        "note": note,
    }


def resolve_talent_effects(hero_name, talents_payload):
    """Resolve selected talents using registered hero implementation."""
    impl = HeroImplementationRegistry.get_implementation(hero_name)
    normalized = impl.normalize_talents(talents_payload)
    return impl.resolve_talent_effects({
        "hero_name": hero_name,
        "talents": normalized,
    })


class TalentEffectModifier:
    """Lightweight read-only modifier used for auto-applied talent effects."""

    TYPE_NAME = "Talent Effect"

    def __init__(self, label, attack_speed_bonus=0.0, evasion_bonus=0.0):
        self.label = str(label or "Talent Effect")
        self.attack_speed_bonus = float(attack_speed_bonus or 0.0)
        self.evasion_bonus = float(evasion_bonus or 0.0)

    def is_enabled(self):
        return True

    def destroy(self):
        return None

    def update_display(self):
        return None

    def get_label(self):
        return self.label

    def get_strength_bonus(self):
        return 0

    def get_agility_bonus(self):
        return 0

    def get_intelligence_bonus(self):
        return 0

    def get_movespeed_flat_bonus(self):
        return 0

    def get_movespeed_pct_bonus(self):
        return 0

    def get_armor_bonus(self):
        return 0

    def get_magic_resistance_bonus(self):
        return 0

    def get_attack_speed_bonus(self):
        return self.attack_speed_bonus

    def get_bat_reduction_pct(self):
        return 0

    def get_mana_bonus(self):
        return 0

    def get_hp_bonus(self):
        return 0

    def get_mana_regen_flat_bonus(self):
        return 0

    def get_hp_regen_flat_bonus(self):
        return 0

    def get_evasion_bonus(self):
        return self.evasion_bonus

    def get_magic_damage_for_hit(self, hit_number, physical_damage=0):
        return 0

    def apply_damage_for_hit(self, hit_number, current_dph, base_dph=None):
        return current_dph
