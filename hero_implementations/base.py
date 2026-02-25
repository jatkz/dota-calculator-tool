"""Base interface for hero-specific behavior."""

from abc import ABC, abstractmethod


class HeroImplementation(ABC):
    """Interface for hero-specific runtime behavior."""

    @classmethod
    @abstractmethod
    def hero_key(cls):
        """Stable normalized hero key this implementation handles."""

    @abstractmethod
    def normalize_talents(self, raw_talents):
        """Normalize/upgrade talent payload into runtime shape."""

    @abstractmethod
    def get_hero_fields_template(self):
        """Return canonical hero fields template for this hero."""

    @abstractmethod
    def get_spells_template(self):
        """Return canonical spells template list for this hero."""

    @abstractmethod
    def get_talents_template(self):
        """Return canonical talents template for this hero."""

    @abstractmethod
    def resolve_talent_effects(self, hero_state):
        """Resolve selected talents into normalized effect entries."""

    @abstractmethod
    def normalize_spell_metadata(self, spell_name, metadata):
        """Normalize spell metadata for this hero."""

    @abstractmethod
    def evaluate_spell(self, spell_state, hero_state, context):
        """Evaluate spell cast result for this hero."""

    @abstractmethod
    def build_spell_runtime_ui_model(self, spell_state, eval_result):
        """Build UI model text values from evaluation result."""

    @abstractmethod
    def export_canonical_hero_payload(self, hero_id=1):
        """Export a canonical hero payload for persistence/export."""
