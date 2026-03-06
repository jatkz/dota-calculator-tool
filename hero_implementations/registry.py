"""Registry for hero implementation resolution."""

from __future__ import annotations

from .helpers import build_talents_payload, deep_copy, normalize_key
from .phantom_assassin import PhantomAssassinImplementation


class DefaultHeroImplementation:
    """Safe no-op implementation used for unknown heroes."""

    def get_hero_fields_template(self):
        return {}

    def get_spells_template(self):
        return []

    def get_talents_template(self):
        return build_talents_payload({})

    def normalize_talents(self, talents_payload):
        return build_talents_payload(talents_payload)

    def resolve_talent_effects(self, payload):
        return []

    def normalize_spell_metadata(self, spell_name, metadata):
        data = deep_copy(metadata) if isinstance(metadata, dict) else {}
        runtime_inputs = data.get("runtime_inputs", {})
        if not isinstance(runtime_inputs, dict):
            runtime_inputs = {}
        runtime_inputs.setdefault("hero_kills_credited_this_cast", 0)
        runtime_inputs.setdefault("target_armors_csv", "0")
        data["runtime_inputs"] = runtime_inputs
        return data

    def evaluate_spell(self, spell_state, hero_state, eval_context):
        return {}

    def build_spell_runtime_ui_model(self, spell_state, result):
        return {"talent_text": "", "runtime_status": ""}


class HeroImplementationRegistry:
    """Resolve hero-specific implementation objects by hero name."""

    _default_impl = DefaultHeroImplementation()
    _registry = {
        "phantomassassin": PhantomAssassinImplementation,
        "mortred": PhantomAssassinImplementation,
    }

    @classmethod
    def get_implementation(cls, hero_name):
        key = normalize_key(hero_name)
        impl_cls = cls._registry.get(key)
        if impl_cls is None:
            return cls._default_impl
        return impl_cls()
