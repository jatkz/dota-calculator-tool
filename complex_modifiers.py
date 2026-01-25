"""Complex modifiers with special stacking or conditional behavior"""

import tkinter as tk
from tkinter import ttk
from abc import ABC, abstractmethod

from utils import safe_eval


class ComplexModifier(ABC):
    """Base class for complex modifiers with special behavior"""

    # Class-level registry of available complex modifier types
    REGISTRY = {}

    def __init__(self, parent, on_change_callback, on_delete_callback, get_variables=None):
        self.parent = parent
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.get_variables = get_variables
        self.enabled_var = tk.BooleanVar(value=True)

        self.frame = ttk.Frame(parent)
        self._create_widgets()

    @classmethod
    def register(cls, modifier_class):
        """Register a complex modifier type"""
        cls.REGISTRY[modifier_class.TYPE_NAME] = modifier_class
        return modifier_class

    @classmethod
    def get_available_types(cls):
        """Get list of available complex modifier type names"""
        return list(cls.REGISTRY.keys())

    @classmethod
    def create(cls, type_name, parent, on_change, on_delete, get_variables=None):
        """Factory method to create a complex modifier by type name"""
        if type_name in cls.REGISTRY:
            return cls.REGISTRY[type_name](parent, on_change, on_delete, get_variables)
        return None

    @abstractmethod
    def _create_widgets(self):
        """Create the UI widgets for this modifier"""
        pass

    @abstractmethod
    def get_label(self):
        """Get the display label for this modifier"""
        pass

    @abstractmethod
    def get_damage_for_hit(self, hit_number, base_dph):
        """
        Calculate the damage contribution for a specific hit number.

        Args:
            hit_number: The hit number (1-indexed)
            base_dph: The base damage per hit before this modifier

        Returns:
            The total damage for this specific hit (base + modifier contribution)
        """
        pass

    @abstractmethod
    def get_total_damage_for_hits(self, num_hits, base_dph):
        """
        Calculate total damage across multiple hits.

        Args:
            num_hits: Number of hits
            base_dph: The base damage per hit before this modifier

        Returns:
            Total damage across all hits
        """
        pass

    def is_enabled(self):
        """Check if modifier is enabled"""
        return self.enabled_var.get()

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this modifier"""
        self.frame.destroy()


@ComplexModifier.register
class FurySwipesModifier(ComplexModifier):
    """
    Fury Swipes: Each attack adds stacking bonus damage.
    Hit 1: +N damage
    Hit 2: +2N damage
    Hit 3: +3N damage
    etc.
    """

    TYPE_NAME = "Fury Swipes"

    def _create_widgets(self):
        # Enabled checkbox
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(self.frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Type label
        ttk.Label(self.frame, text="Fury Swipes",
                  font=('Arial', 9, 'bold'), foreground='#8B4513').pack(side="left", padx=(0, 10))

        # Label input
        ttk.Label(self.frame, text="Label:").pack(side="left")
        self.label_var = tk.StringVar(value="Fury Swipes")
        label_entry = ttk.Entry(self.frame, textvariable=self.label_var, width=12)
        label_entry.pack(side="left", padx=2)

        # Damage per stack input
        ttk.Label(self.frame, text="Dmg/Stack:").pack(side="left", padx=(10, 0))
        self.damage_var = tk.StringVar(value="15")
        self.damage_var.trace('w', lambda *args: self.on_change())
        damage_entry = ttk.Entry(self.frame, textvariable=self.damage_var, width=6)
        damage_entry.pack(side="left", padx=2)

        # Info display
        self.info_var = tk.StringVar(value="")
        info_label = ttk.Label(self.frame, textvariable=self.info_var,
                               foreground='#666', font=('Arial', 8))
        info_label.pack(side="left", padx=5)

        # Delete button
        delete_btn = ttk.Button(self.frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="right", padx=5)

        self._update_info()

    def _update_info(self):
        """Update the info display"""
        dmg = self._get_damage_per_stack()
        if dmg > 0:
            # Show example: Hit 1: +15, Hit 5: +75
            self.info_var.set(f"Hit1: +{dmg:.0f}, Hit5: +{dmg*5:.0f}")
        else:
            self.info_var.set("")

    def _get_damage_per_stack(self):
        """Get the damage per stack value"""
        if not self.enabled_var.get():
            return 0
        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.damage_var.get(), variables)
        return value if value is not None else 0

    def get_label(self):
        """Get the display label"""
        return self.label_var.get()

    def get_damage_for_hit(self, hit_number, base_dph):
        """
        Calculate damage for a specific hit with fury swipes stacking.

        Args:
            hit_number: The hit number (1-indexed)
            base_dph: Base damage per hit

        Returns:
            Total damage for this hit
        """
        if not self.is_enabled():
            return base_dph

        dmg_per_stack = self._get_damage_per_stack()
        # Hit N adds N stacks worth of damage
        stack_damage = dmg_per_stack * hit_number
        return base_dph + stack_damage

    def get_total_damage_for_hits(self, num_hits, base_dph):
        """
        Calculate total damage across multiple hits with fury swipes.

        The formula for sum of 1+2+3+...+n = n*(n+1)/2

        Args:
            num_hits: Number of hits
            base_dph: Base damage per hit

        Returns:
            Total damage across all hits
        """
        if not self.is_enabled():
            return base_dph * num_hits

        dmg_per_stack = self._get_damage_per_stack()
        # Base damage for all hits
        total_base = base_dph * num_hits
        # Stacking damage: dmg * (1 + 2 + 3 + ... + n) = dmg * n*(n+1)/2
        total_stacks = num_hits * (num_hits + 1) // 2
        total_stack_damage = dmg_per_stack * total_stacks

        return total_base + total_stack_damage

    def update_display(self):
        """Update the display"""
        self._update_info()
