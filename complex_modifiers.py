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

    def get_magic_damage_for_hit(self, hit_number):
        """
        Calculate magic damage for a specific hit (reduced by magic resistance).
        Override in modifiers that deal magic damage.

        Args:
            hit_number: The hit number (1-indexed)

        Returns:
            Magic damage for this hit (default: 0)
        """
        return 0

    def get_total_magic_damage_for_hits(self, num_hits):
        """
        Calculate total magic damage across multiple hits.
        Override in modifiers that deal magic damage.

        Args:
            num_hits: Number of hits

        Returns:
            Total magic damage across all hits (default: 0)
        """
        return 0

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


@ComplexModifier.register
class CritModifier(ComplexModifier):
    """
    Critical Strike: Chance to deal bonus damage on hit.
    Average damage = base * (1 + crit_chance * (crit_multiplier - 1))

    Example: 30% crit chance, 150% crit multiplier
    Average = base * (1 + 0.3 * 0.5) = base * 1.15
    """

    TYPE_NAME = "Critical Strike"

    def _create_widgets(self):
        # Enabled checkbox
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(self.frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Type label
        ttk.Label(self.frame, text="Crit",
                  font=('Arial', 9, 'bold'), foreground='#DC143C').pack(side="left", padx=(0, 10))

        # Label input
        ttk.Label(self.frame, text="Label:").pack(side="left")
        self.label_var = tk.StringVar(value="Crit")
        label_entry = ttk.Entry(self.frame, textvariable=self.label_var, width=10)
        label_entry.pack(side="left", padx=2)

        # Crit chance input
        ttk.Label(self.frame, text="Chance:").pack(side="left", padx=(10, 0))
        self.chance_var = tk.StringVar(value="30")
        self.chance_var.trace('w', lambda *args: self.on_change())
        chance_entry = ttk.Entry(self.frame, textvariable=self.chance_var, width=4)
        chance_entry.pack(side="left", padx=2)
        ttk.Label(self.frame, text="%").pack(side="left")

        # Crit multiplier input
        ttk.Label(self.frame, text="Mult:").pack(side="left", padx=(10, 0))
        self.mult_var = tk.StringVar(value="150")
        self.mult_var.trace('w', lambda *args: self.on_change())
        mult_entry = ttk.Entry(self.frame, textvariable=self.mult_var, width=4)
        mult_entry.pack(side="left", padx=2)
        ttk.Label(self.frame, text="%").pack(side="left")

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
        chance = self._get_crit_chance()
        mult = self._get_crit_multiplier()
        if chance > 0 and mult > 1:
            # Show average multiplier
            avg_mult = 1 + chance * (mult - 1)
            self.info_var.set(f"Avg: {avg_mult:.2f}x")
        else:
            self.info_var.set("")

    def _get_crit_chance(self):
        """Get crit chance as decimal (0-1)"""
        if not self.enabled_var.get():
            return 0
        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.chance_var.get(), variables)
        if value is None:
            return 0
        return min(100, max(0, value)) / 100  # Clamp 0-100, convert to decimal

    def _get_crit_multiplier(self):
        """Get crit multiplier as decimal (e.g., 150% -> 1.5)"""
        if not self.enabled_var.get():
            return 1
        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.mult_var.get(), variables)
        if value is None:
            return 1
        return max(100, value) / 100  # Min 100%, convert to decimal

    def get_label(self):
        """Get the display label"""
        return self.label_var.get()

    def get_damage_for_hit(self, hit_number, base_dph):
        """
        Calculate average damage for a hit with crit.

        Args:
            hit_number: The hit number (not used for crit, same every hit)
            base_dph: Base damage per hit

        Returns:
            Average damage for this hit
        """
        if not self.is_enabled():
            return base_dph

        chance = self._get_crit_chance()
        mult = self._get_crit_multiplier()
        # Average damage = base * (1 + chance * (mult - 1))
        avg_multiplier = 1 + chance * (mult - 1)
        return base_dph * avg_multiplier

    def get_total_damage_for_hits(self, num_hits, base_dph):
        """
        Calculate total average damage across multiple hits with crit.

        Args:
            num_hits: Number of hits
            base_dph: Base damage per hit

        Returns:
            Total average damage across all hits
        """
        if not self.is_enabled():
            return base_dph * num_hits

        chance = self._get_crit_chance()
        mult = self._get_crit_multiplier()
        avg_multiplier = 1 + chance * (mult - 1)
        return base_dph * avg_multiplier * num_hits

    def update_display(self):
        """Update the display"""
        self._update_info()


@ComplexModifier.register
class MagicDamageOnHitModifier(ComplexModifier):
    """
    Magic Damage on Hit: Chance to deal bonus magic damage on each attack.
    Average bonus damage per hit = proc_chance * magic_damage

    Example: 65% proc chance, 55 magic damage
    Average bonus = 0.65 * 55 = 35.75 magic damage per hit
    """

    TYPE_NAME = "Magic on Hit"

    def _create_widgets(self):
        # Enabled checkbox
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(self.frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Type label
        ttk.Label(self.frame, text="Magic on Hit",
                  font=('Arial', 9, 'bold'), foreground='#4169E1').pack(side="left", padx=(0, 10))

        # Label input
        ttk.Label(self.frame, text="Label:").pack(side="left")
        self.label_var = tk.StringVar(value="Magic Proc")
        label_entry = ttk.Entry(self.frame, textvariable=self.label_var, width=10)
        label_entry.pack(side="left", padx=2)

        # Proc chance input
        ttk.Label(self.frame, text="Chance:").pack(side="left", padx=(10, 0))
        self.chance_var = tk.StringVar(value="65")
        self.chance_var.trace('w', lambda *args: self.on_change())
        chance_entry = ttk.Entry(self.frame, textvariable=self.chance_var, width=4)
        chance_entry.pack(side="left", padx=2)
        ttk.Label(self.frame, text="%").pack(side="left")

        # Magic damage input
        ttk.Label(self.frame, text="Damage:").pack(side="left", padx=(10, 0))
        self.damage_var = tk.StringVar(value="55")
        self.damage_var.trace('w', lambda *args: self.on_change())
        damage_entry = ttk.Entry(self.frame, textvariable=self.damage_var, width=5)
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
        chance = self._get_proc_chance()
        damage = self._get_magic_damage()
        if chance > 0 and damage > 0:
            avg_damage = chance * damage
            self.info_var.set(f"Avg: +{avg_damage:.1f}")
        else:
            self.info_var.set("")

    def _get_proc_chance(self):
        """Get proc chance as decimal (0-1)"""
        if not self.enabled_var.get():
            return 0
        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.chance_var.get(), variables)
        if value is None:
            return 0
        return min(100, max(0, value)) / 100  # Clamp 0-100, convert to decimal

    def _get_magic_damage(self):
        """Get magic damage value"""
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
        Physical damage is unchanged - magic damage is separate.

        Args:
            hit_number: The hit number
            base_dph: Base damage per hit

        Returns:
            Base physical damage (unchanged)
        """
        return base_dph

    def get_total_damage_for_hits(self, num_hits, base_dph):
        """
        Physical damage is unchanged - magic damage is separate.

        Args:
            num_hits: Number of hits
            base_dph: Base damage per hit

        Returns:
            Total physical damage (unchanged)
        """
        return base_dph * num_hits

    def get_magic_damage_for_hit(self, hit_number):
        """
        Calculate average magic damage for a specific hit.

        Args:
            hit_number: The hit number

        Returns:
            Average magic damage for this hit
        """
        if not self.is_enabled():
            return 0

        chance = self._get_proc_chance()
        damage = self._get_magic_damage()
        return chance * damage

    def get_total_magic_damage_for_hits(self, num_hits):
        """
        Calculate total average magic damage across multiple hits.

        Args:
            num_hits: Number of hits

        Returns:
            Total average magic damage
        """
        if not self.is_enabled():
            return 0

        chance = self._get_proc_chance()
        damage = self._get_magic_damage()
        return chance * damage * num_hits

    def update_display(self):
        """Update the display"""
        self._update_info()
