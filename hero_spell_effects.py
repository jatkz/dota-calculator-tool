"""Compatibility wrapper for hero spell runtime evaluation."""

from hero_implementations.phantom_assassin import PhantomAssassinImplementation
from hero_implementations.registry import HeroImplementationRegistry


def normalize_stifling_metadata(metadata):
    """Compatibility helper for older call sites."""
    return PhantomAssassinImplementation().normalize_spell_metadata("Stifling Dagger", metadata)


def evaluate_hero_spell(spell_row, hero_row, selected_targets, context):
    """Evaluate spell using the active hero implementation."""
    context = context if isinstance(context, dict) else {}
    hero_name = context.get("hero_name", "")
    if not hero_name and hero_row is not None:
        fields = getattr(hero_row, "field_vars", {})
        name_var = fields.get("name") if isinstance(fields, dict) else None
        if hasattr(name_var, "get"):
            hero_name = name_var.get()

    impl = HeroImplementationRegistry.get_implementation(hero_name)

    level_index = max(0, int(getattr(spell_row, "_current_level_index")()))
    levels = getattr(spell_row, "levels", []) or []
    level_data = levels[level_index] if 0 <= level_index < len(levels) else {}
    spell_name = getattr(getattr(spell_row, "name_var", None), "get", lambda: "")()
    metadata = getattr(spell_row, "metadata", {})
    runtime_inputs = {}
    if hasattr(spell_row, "get_runtime_context"):
        runtime_inputs = spell_row.get_runtime_context() or {}

    spell_state = {
        "spell_name": spell_name,
        "level_index": level_index,
        "level_data": level_data,
        "levels": levels,
        "metadata": metadata if isinstance(metadata, dict) else {},
        "runtime_inputs": runtime_inputs if isinstance(runtime_inputs, dict) else {},
    }

    hero_auto_attack_damage = context.get("hero_auto_attack_damage", 0.0)
    talent_effects = context.get("talent_effects", [])
    hero_state = {
        "hero_name": hero_name,
        "hero_auto_attack_damage": hero_auto_attack_damage,
        "talent_effects": talent_effects,
    }

    eval_context = dict(context)
    eval_context["selected_targets"] = selected_targets if isinstance(selected_targets, list) else []
    return impl.evaluate_spell(spell_state, hero_state, eval_context)
