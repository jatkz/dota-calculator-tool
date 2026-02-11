"""HeroLabSection class - orchestrates Hero Lab section"""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from modifiers import Modifier
from utils import safe_eval, armor_to_reduction


class HeroSpellRow:
    """Simple editable spell row attached to a hero."""

    DAMAGE_TYPES = ("Physical", "Magic", "Pure")

    def __init__(self, parent, on_delete):
        self.parent = parent
        self.on_delete = on_delete
        self.frame = ttk.Frame(parent)
        self._create_widgets()

    def _create_widgets(self):
        self.name_var = tk.StringVar(value="Spell")
        self.damage_var = tk.StringVar(value="0")
        self.damage_type_var = tk.StringVar(value=self.DAMAGE_TYPES[1])
        self.hits_var = tk.StringVar(value="1")
        self.cast_var = tk.StringVar(value="0")
        self.stun_var = tk.StringVar(value="0")
        self.mana_var = tk.StringVar(value="0")
        self.cooldown_var = tk.StringVar(value="0")

        top_row = ttk.Frame(self.frame)
        top_row.pack(fill="x")
        bottom_row = ttk.Frame(self.frame)
        bottom_row.pack(fill="x", pady=(2, 0))

        ttk.Label(top_row, text="Name:", font=('Arial', 8)).pack(side="left", padx=(0, 2))
        ttk.Entry(top_row, textvariable=self.name_var, width=14).pack(side="left", padx=2)

        ttk.Label(top_row, text="Damage:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Entry(top_row, textvariable=self.damage_var, width=8).pack(side="left", padx=2)

        ttk.Label(top_row, text="Type:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Combobox(
            top_row,
            textvariable=self.damage_type_var,
            values=self.DAMAGE_TYPES,
            state="readonly",
            width=9
        ).pack(side="left", padx=2)

        ttk.Button(top_row, text="X", width=2,
                   command=lambda: self.on_delete(self)).pack(side="right", padx=4)

        ttk.Label(bottom_row, text="Hits:", font=('Arial', 8)).pack(side="left", padx=(0, 2))
        ttk.Entry(bottom_row, textvariable=self.hits_var, width=6).pack(side="left", padx=2)

        ttk.Label(bottom_row, text="Cast:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Entry(bottom_row, textvariable=self.cast_var, width=6).pack(side="left", padx=2)

        ttk.Label(bottom_row, text="Stun:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Entry(bottom_row, textvariable=self.stun_var, width=6).pack(side="left", padx=2)

        ttk.Label(bottom_row, text="Mana:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Entry(bottom_row, textvariable=self.mana_var, width=8).pack(side="left", padx=2)

        ttk.Label(bottom_row, text="CD:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        ttk.Entry(bottom_row, textvariable=self.cooldown_var, width=8).pack(side="left", padx=2)

    def pack(self, **kwargs):
        """Pack spell row widget."""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Destroy spell row widget."""
        self.frame.destroy()

    def to_dict(self):
        """Serialize spell row to dictionary."""
        return {
            "name": self.name_var.get(),
            "damage": self.damage_var.get(),
            "damage_type": self.damage_type_var.get(),
            "hits": self.hits_var.get(),
            "cast": self.cast_var.get(),
            "stun": self.stun_var.get(),
            "mana": self.mana_var.get(),
            "cooldown": self.cooldown_var.get(),
        }

    def load_from_dict(self, data):
        """Load spell row values from dictionary."""
        self.name_var.set(str(data.get("name", self.name_var.get())))
        self.damage_var.set(str(data.get("damage", self.damage_var.get())))
        damage_type = str(data.get("damage_type", self.damage_type_var.get()))
        if damage_type in self.DAMAGE_TYPES:
            self.damage_type_var.set(damage_type)
        self.hits_var.set(str(data.get("hits", self.hits_var.get())))
        self.cast_var.set(str(data.get("cast", self.cast_var.get())))
        self.stun_var.set(str(data.get("stun", self.stun_var.get())))
        self.mana_var.set(str(data.get("mana", self.mana_var.get())))
        self.cooldown_var.set(str(data.get("cooldown", self.cooldown_var.get())))


class HeroRow:
    """Single hero row with base stats, modifiers, and item placeholder."""

    ATTRIBUTE_TYPES = ("Strength", "Agility", "Intelligence", "Universal")

    FIELD_CONFIG = [
        ("name", "Name", "Hero"),
        ("attribute_type", "Attribute Type", "Strength"),
        ("level", "Lvl", "1"),
        ("base_hp", "Base HP", "200"),
        ("base_hp_regen", "Base HP Regen", "0"),
        ("movespeed", "Move Speed", "300"),
        ("attack_speed", "Attack Speed", "100"),
        ("bat", "BAT", "1.7"),
        ("base_damage", "Base Damage", "50"),
        ("base_armor", "Base Armor", "0"),
        ("base_magic_resist", "Base Magic Resist (%)", "25"),
        ("evasion", "Evasion (%)", "0"),
        ("strength", "Strength", "20"),
        ("agility", "Agility", "20"),
        ("intelligence", "Intelligence", "20"),
        ("strength_per_level", "Str/Lvl", "0"),
        ("agility_per_level", "Agi/Lvl", "0"),
        ("intelligence_per_level", "Int/Lvl", "0"),
        ("turn_rate", "Turn Rate", "0.6"),
    ]

    def __init__(self, parent, hero_id, on_delete, on_save, get_variables):
        self.parent = parent
        self.hero_id = hero_id
        self.on_delete = on_delete
        self.on_save = on_save
        self.get_variables = get_variables
        self.modifiers = []
        self.spell_rows = []
        self.items = []  # Placeholder until items UI is implemented
        self.field_vars = {}
        self.field_entries = {}
        self.total_vars = {}

        self.frame = ttk.Frame(parent, relief='solid', borderwidth=1, padding="8")
        self._create_widgets()

    def _create_widgets(self):
        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 6))
        ttk.Button(header, text="Save", width=8,
                   command=lambda: self.on_save(self)).pack(side="right", padx=(0, 4))
        ttk.Button(header, text="Delete", width=8,
                   command=lambda: self.on_delete(self)).pack(side="right")

        stats_frame = ttk.Frame(self.frame)
        stats_frame.pack(fill="x", pady=(0, 6))

        # Fields split into multiple rows for readability
        top_fields = self.FIELD_CONFIG[:7]
        middle_fields = self.FIELD_CONFIG[7:14]
        bottom_fields = self.FIELD_CONFIG[14:]
        self._build_fields_row(stats_frame, top_fields)
        self._build_fields_row(stats_frame, middle_fields)
        self._build_fields_row(stats_frame, bottom_fields)

        # Modifiers block
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        mod_header = ttk.Frame(self.frame)
        mod_header.pack(fill="x", pady=(0, 5))
        ttk.Label(mod_header, text="Modifiers",
                  font=('Arial', 9, 'bold')).pack(side="left")

        self.modifier_type_var = tk.StringVar(value="")
        self.modifier_combo = ttk.Combobox(
            mod_header,
            textvariable=self.modifier_type_var,
            state="readonly",
            width=20
        )
        self.modifier_combo['values'] = Modifier.get_available_types()
        if self.modifier_combo['values']:
            self.modifier_type_var.set(self.modifier_combo['values'][0])
        self.modifier_combo.pack(side="right", padx=2)

        ttk.Button(mod_header, text="+ Add Modifier",
                   command=self.add_modifier).pack(side="right", padx=5)

        self.modifiers_container = ttk.Frame(self.frame)
        self.modifiers_container.pack(fill="x")

        # Items block (placeholder)
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        items_header = ttk.Frame(self.frame)
        items_header.pack(fill="x", pady=(0, 2))
        ttk.Label(items_header, text="Items",
                  font=('Arial', 9, 'bold')).pack(side="left")
        ttk.Button(items_header, text="+ Add Item (Soon)",
                   state='disabled').pack(side="right")
        ttk.Label(self.frame,
                  text="Items attachment is not implemented yet.",
                  foreground="#666", font=('Arial', 8)).pack(anchor="w")

        # Spells block
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        spells_header = ttk.Frame(self.frame)
        spells_header.pack(fill="x", pady=(0, 2))
        ttk.Label(spells_header, text="Spells",
                  font=('Arial', 9, 'bold')).pack(side="left")
        ttk.Button(spells_header, text="+ Add Spell",
                   command=self.add_spell).pack(side="right")

        self.spells_container = ttk.Frame(self.frame)
        self.spells_container.pack(fill="x")

        # Totals block
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        totals_header = ttk.Frame(self.frame)
        totals_header.pack(fill="x", pady=(0, 2))
        ttk.Label(totals_header, text="Totals",
                  font=('Arial', 9, 'bold')).pack(side="left")

        self.totals_container = ttk.Frame(self.frame)
        self.totals_container.pack(fill="x")
        self._create_totals_widgets()
        self.update_totals()

    def _build_fields_row(self, parent, field_config):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        for key, label, default_value in field_config:
            field_frame = ttk.Frame(row)
            field_frame.pack(side="left", padx=4)
            ttk.Label(field_frame, text=label, font=('Arial', 8)).pack(anchor="w")

            var = tk.StringVar(value=default_value)
            if key == "attribute_type":
                entry = ttk.Combobox(
                    field_frame,
                    textvariable=var,
                    values=self.ATTRIBUTE_TYPES,
                    state="readonly",
                    width=11
                )
            else:
                entry = ttk.Entry(field_frame, textvariable=var, width=11)
            entry.pack(anchor="w")
            self.field_vars[key] = var
            self.field_entries[key] = entry
            var.trace('w', lambda *args: self.update_totals())

    def _create_totals_widgets(self):
        """Create display rows for all requested totals."""
        totals = [
            ("total_strength", "Total Strength"),
            ("total_agility", "Total Agility"),
            ("total_intelligence", "Total Intelligence"),
            ("total_hp", "Total HP"),
            ("total_health_regen", "Total Health Regen"),
            ("total_mana", "Total Mana"),
            ("total_mana_regen", "Total Mana Regen"),
            ("attacks_per_second", "Attacks Per Second"),
            ("seconds_between_attack", "Seconds Between Attack"),
            ("total_base_damage", "Total Base Damage"),
            ("total_bonus_damage", "Total Bonus Damage"),
            ("total_auto_attack_damage", "Total Auto Attack Damage"),
            ("total_estimated_attack_damage", "Total Estimated Attack Damage"),
            ("estimated_dps", "Estimated DPS"),
            ("total_movespeed", "Total Movespeed"),
            ("armor", "Armor"),
            ("physical_reduction", "Physical Reduction"),
            ("magic_resistance", "Magic Resistance"),
            ("evasion", "Evasion"),
            ("physical_reduction_with_evasion", "Calculated Physical Reduction With Evasion"),
            ("ehp_physical_reduction", "Effective HP With Physical Reduction"),
            ("ehp_evasion", "Effective HP With Evasion"),
            ("ehp_physical_evasion", "Effective HP With Physical Reduction And Evasion"),
            ("ehp_magic_resistance", "Effective HP With Magic Resistance"),
        ]

        midpoint = (len(totals) + 1) // 2
        left_totals = totals[:midpoint]
        right_totals = totals[midpoint:]

        for index, (key, label) in enumerate(left_totals):
            label_widget = ttk.Label(self.totals_container, text=f"{label}:",
                                     font=('Arial', 8))
            label_widget.grid(row=index, column=0, sticky="w", padx=(0, 8), pady=1)

            var = tk.StringVar(value="0")
            value_widget = ttk.Label(self.totals_container, textvariable=var,
                                     font=('Arial', 8, 'bold'), foreground="#2b2b2b")
            value_widget.grid(row=index, column=1, sticky="w", padx=(0, 20), pady=1)
            self.total_vars[key] = var

        for index, (key, label) in enumerate(right_totals):
            label_widget = ttk.Label(self.totals_container, text=f"{label}:",
                                     font=('Arial', 8))
            label_widget.grid(row=index, column=2, sticky="w", padx=(0, 8), pady=1)

            var = tk.StringVar(value="0")
            value_widget = ttk.Label(self.totals_container, textvariable=var,
                                     font=('Arial', 8, 'bold'), foreground="#2b2b2b")
            value_widget.grid(row=index, column=3, sticky="w", pady=1)
            self.total_vars[key] = var

    def _get_numeric_field(self, key, default=0.0):
        """Get numeric field value, supporting expressions and global variables."""
        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.field_vars[key].get(), variables)
        return default if value is None else value

    def _clamp(self, value, low, high):
        """Clamp number to inclusive range."""
        return max(low, min(high, value))

    def _get_primary_attribute_bonus(self, strength, agility, intelligence):
        """Get base attack bonus damage from attribute type."""
        attr_type = self.field_vars["attribute_type"].get().strip().lower()
        if attr_type == "strength":
            return strength
        if attr_type == "agility":
            return agility
        if attr_type == "intelligence":
            return intelligence
        # Universal: basic estimate from all attributes.
        return 0.45 * (strength + agility + intelligence)

    def _format_value(self, value, suffix=""):
        """Format value for totals display."""
        if value == float("inf"):
            return "Infinity"
        return f"{value:.2f}{suffix}"

    def _effective_hp_from_mitigation(self, hp, mitigation_fraction):
        """Calculate effective HP using mitigation fraction [0..1)."""
        denominator = 1 - mitigation_fraction
        if denominator <= 0:
            return float("inf")
        return hp / denominator

    def _is_flat_damage_modifier(self, mod):
        """Check whether modifier is a flat damage modifier."""
        return getattr(mod, "TYPE_NAME", "") == "Flat Damage"

    def _is_percentage_damage_modifier(self, mod):
        """Check whether modifier is a percentage damage modifier."""
        return getattr(mod, "TYPE_NAME", "") == "Percentage Damage"

    def update_totals(self):
        """Recalculate and refresh all totals for this hero."""
        base_hp = self._get_numeric_field("base_hp")
        base_hp_regen = self._get_numeric_field("base_hp_regen")
        movespeed = self._get_numeric_field("movespeed")
        attack_speed = self._get_numeric_field("attack_speed")
        bat = self._get_numeric_field("bat")
        base_damage = self._get_numeric_field("base_damage")
        base_armor = self._get_numeric_field("base_armor")
        base_magic_resist = self._clamp(self._get_numeric_field("base_magic_resist"), 0, 100)
        base_evasion = self._clamp(self._get_numeric_field("evasion"), 0, 100)
        level = max(1.0, self._get_numeric_field("level", 1.0))
        base_strength = self._get_numeric_field("strength")
        base_agility = self._get_numeric_field("agility")
        base_intelligence = self._get_numeric_field("intelligence")
        strength_per_level = self._get_numeric_field("strength_per_level")
        agility_per_level = self._get_numeric_field("agility_per_level")
        intelligence_per_level = self._get_numeric_field("intelligence_per_level")

        level_factor = max(0.0, level - 1.0)
        strength = base_strength + (strength_per_level * level_factor)
        agility = base_agility + (agility_per_level * level_factor)
        intelligence = base_intelligence + (intelligence_per_level * level_factor)

        total_hp = max(0.0, base_hp + (strength * 22.0))
        total_health_regen = base_hp_regen + (strength * 0.1)
        total_mana = max(0.0, 75.0 + (intelligence * 12.0))
        total_mana_regen = intelligence * 0.05

        effective_attack_speed = max(0.0, attack_speed + agility)
        attacks_per_second = 0.0
        if bat > 0:
            attacks_per_second = effective_attack_speed / (100 * bat)
        seconds_between_attack = 0.0
        if attacks_per_second > 0:
            seconds_between_attack = 1.0 / attacks_per_second

        attribute_damage = self._get_primary_attribute_bonus(strength, agility, intelligence)
        raw_base_damage = base_damage + attribute_damage

        total_bonus_damage = 0.0
        for mod in self.modifiers:
            if mod.is_enabled() and self._is_flat_damage_modifier(mod):
                total_bonus_damage += mod.get_damage_for_hit(1, 0.0)

        total_base_damage = raw_base_damage
        total_auto_attack_damage = raw_base_damage + total_bonus_damage
        for mod in self.modifiers:
            if mod.is_enabled() and self._is_percentage_damage_modifier(mod):
                total_base_damage = mod.apply_damage_for_hit(1, total_base_damage, raw_base_damage)
                total_auto_attack_damage = mod.apply_damage_for_hit(1, total_auto_attack_damage, raw_base_damage)

        estimated_physical_damage = total_auto_attack_damage
        for mod in self.modifiers:
            if mod.is_enabled() and not self._is_flat_damage_modifier(mod) and not self._is_percentage_damage_modifier(mod):
                estimated_physical_damage = mod.apply_damage_for_hit(
                    1, estimated_physical_damage, raw_base_damage
                )

        estimated_magic_damage = 0.0
        for mod in self.modifiers:
            if mod.is_enabled():
                estimated_magic_damage += mod.get_magic_damage_for_hit(1, estimated_physical_damage)

        total_estimated_attack_damage = estimated_physical_damage + estimated_magic_damage
        estimated_dps = total_estimated_attack_damage * attacks_per_second

        armor = base_armor + (agility / 6.0)
        physical_reduction = armor_to_reduction(armor)
        magic_resistance = self._clamp(base_magic_resist + (intelligence * 0.1), 0, 100)
        evasion = base_evasion

        physical_reduction_fraction = physical_reduction / 100.0
        magic_resistance_fraction = magic_resistance / 100.0
        evasion_fraction = evasion / 100.0

        physical_reduction_with_evasion = 1 - ((1 - physical_reduction_fraction) * (1 - evasion_fraction))
        physical_reduction_with_evasion_pct = physical_reduction_with_evasion * 100.0

        ehp_physical_reduction = self._effective_hp_from_mitigation(total_hp, physical_reduction_fraction)
        ehp_evasion = self._effective_hp_from_mitigation(total_hp, evasion_fraction)
        ehp_physical_evasion = total_hp / ((1 - physical_reduction_fraction) * (1 - evasion_fraction)) \
            if (1 - physical_reduction_fraction) > 0 and (1 - evasion_fraction) > 0 else float("inf")
        ehp_magic_resistance = self._effective_hp_from_mitigation(total_hp, magic_resistance_fraction)

        self.total_vars["total_strength"].set(self._format_value(strength))
        self.total_vars["total_agility"].set(self._format_value(agility))
        self.total_vars["total_intelligence"].set(self._format_value(intelligence))
        self.total_vars["total_hp"].set(self._format_value(total_hp))
        self.total_vars["total_health_regen"].set(self._format_value(total_health_regen))
        self.total_vars["total_mana"].set(self._format_value(total_mana))
        self.total_vars["total_mana_regen"].set(self._format_value(total_mana_regen))
        self.total_vars["attacks_per_second"].set(self._format_value(attacks_per_second))
        self.total_vars["seconds_between_attack"].set(self._format_value(seconds_between_attack))
        self.total_vars["total_base_damage"].set(self._format_value(total_base_damage))
        self.total_vars["total_bonus_damage"].set(self._format_value(total_bonus_damage))
        self.total_vars["total_auto_attack_damage"].set(self._format_value(total_auto_attack_damage))
        self.total_vars["total_estimated_attack_damage"].set(self._format_value(total_estimated_attack_damage))
        self.total_vars["estimated_dps"].set(self._format_value(estimated_dps))
        self.total_vars["total_movespeed"].set(self._format_value(movespeed))
        self.total_vars["armor"].set(self._format_value(armor))
        self.total_vars["physical_reduction"].set(self._format_value(physical_reduction, "%"))
        self.total_vars["magic_resistance"].set(self._format_value(magic_resistance, "%"))
        self.total_vars["evasion"].set(self._format_value(evasion, "%"))
        self.total_vars["physical_reduction_with_evasion"].set(
            self._format_value(physical_reduction_with_evasion_pct, "%")
        )
        self.total_vars["ehp_physical_reduction"].set(self._format_value(ehp_physical_reduction))
        self.total_vars["ehp_evasion"].set(self._format_value(ehp_evasion))
        self.total_vars["ehp_physical_evasion"].set(self._format_value(ehp_physical_evasion))
        self.total_vars["ehp_magic_resistance"].set(self._format_value(ehp_magic_resistance))

    def add_modifier(self):
        """Add a modifier attached to this hero."""
        type_name = self.modifier_type_var.get()
        if not type_name:
            return

        mod = Modifier.create(
            type_name,
            self.modifiers_container,
            self._on_modifier_changed,
            self.delete_modifier,
            get_variables=self.get_variables
        )
        if mod:
            mod.pack(fill="x", pady=2)
            self.modifiers.append(mod)
            self._on_modifier_changed()

    def delete_modifier(self, mod):
        """Delete a hero modifier."""
        self.modifiers.remove(mod)
        mod.destroy()
        self._on_modifier_changed()

    def _on_modifier_changed(self):
        """Update modifier displays after changes."""
        for mod in self.modifiers:
            mod.update_display()
        self.update_totals()

    def add_spell(self, spell_data=None):
        """Add a spell attached to this hero."""
        spell_row = HeroSpellRow(self.spells_container, self.delete_spell)
        if spell_data:
            spell_row.load_from_dict(spell_data)
        spell_row.pack(fill="x", pady=2)
        self.spell_rows.append(spell_row)

    def delete_spell(self, spell_row):
        """Delete a spell attached to this hero."""
        self.spell_rows.remove(spell_row)
        spell_row.destroy()

    def _serialize_modifier(self, mod):
        """Serialize modifier to dictionary."""
        values = {}
        for key, value in mod.__dict__.items():
            if key.endswith("_var") and hasattr(value, "get"):
                values[key] = value.get()
        return {
            "type": getattr(mod, "TYPE_NAME", ""),
            "values": values
        }

    def _load_modifier(self, modifier_data):
        """Instantiate and load a modifier from dictionary."""
        type_name = modifier_data.get("type")
        if not type_name:
            return

        mod = Modifier.create(
            type_name,
            self.modifiers_container,
            self._on_modifier_changed,
            self.delete_modifier,
            get_variables=self.get_variables
        )
        if not mod:
            return

        for key, value in modifier_data.get("values", {}).items():
            var = getattr(mod, key, None)
            if hasattr(var, "set"):
                var.set(value)

        mod.pack(fill="x", pady=2)
        self.modifiers.append(mod)
        mod.update_display()

    def to_dict(self):
        """Serialize hero row including fields, modifiers, spells, and items."""
        return {
            "hero_id": self.hero_id,
            "fields": {key: var.get() for key, var in self.field_vars.items()},
            "modifiers": [self._serialize_modifier(mod) for mod in self.modifiers],
            "spells": [spell_row.to_dict() for spell_row in self.spell_rows],
            "items": self.items[:],
        }

    def load_from_dict(self, data):
        """Load hero row data including fields, modifiers, spells, and items."""
        for key, value in data.get("fields", {}).items():
            if key in self.field_vars:
                self.field_vars[key].set(str(value))

        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()

        for spell_row in self.spell_rows[:]:
            spell_row.destroy()
        self.spell_rows.clear()

        for modifier_data in data.get("modifiers", []):
            self._load_modifier(modifier_data)

        for spell_data in data.get("spells", []):
            self.add_spell(spell_data=spell_data)

        items = data.get("items", [])
        self.items = items if isinstance(items, list) else []
        self.update_totals()

    def pack(self, **kwargs):
        """Pack row widget."""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Destroy row and attached modifiers."""
        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()
        for spell_row in self.spell_rows[:]:
            spell_row.destroy()
        self.spell_rows.clear()
        self.frame.destroy()


class HeroLabSection:
    """Orchestrates the Hero Lab section"""

    HERO_LIBRARY_FILENAME = "hero_library.json"

    def __init__(self, parent, get_variables):
        """
        Initialize the Hero Lab section.

        Args:
            parent: Parent widget to add section to
            get_variables: Callback to get current variables dict
        """
        self.parent = parent
        self.get_variables = get_variables
        self.visible = False
        self.hero_rows = []
        self.next_hero_id = 1
        self._create_widgets()

    def _create_widgets(self):
        """Create all widgets for the Hero Lab section"""
        self.section_frame = ttk.Frame(self.parent)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        header = ttk.Frame(self.section_frame)
        header.pack(fill="x", pady=(5, 5))
        ttk.Label(header, text="HERO LAB", font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(header, text="Load Heroes",
                   command=self.load_heroes).pack(side="right", padx=5)
        ttk.Button(header, text="+ Add Hero",
                   command=self.add_hero).pack(side="right", padx=5)

        self.heroes_container = ttk.Frame(self.section_frame)
        self.heroes_container.pack(fill="x", pady=5)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def pack_content(self):
        """Pack the section content (called by parent's toggle)"""
        if not self.visible:
            self.section_frame.pack(fill="x", pady=5)
            self.visible = True
            if not self.hero_rows:
                self.add_hero()

    def add_hero(self, hero_data=None):
        """Add a new hero row."""
        if hero_data and isinstance(hero_data.get("hero_id"), int):
            hero_id = hero_data["hero_id"]
            self.next_hero_id = max(self.next_hero_id, hero_id + 1)
        else:
            hero_id = self.next_hero_id
            self.next_hero_id += 1

        hero_row = HeroRow(
            self.heroes_container,
            hero_id,
            self.delete_hero,
            self.save_hero,
            self.get_variables
        )
        if hero_data:
            hero_row.load_from_dict(hero_data)
        hero_row.pack(fill="x", pady=4)
        self.hero_rows.append(hero_row)

    def delete_hero(self, hero_row):
        """Delete an existing hero row."""
        if hero_row in self.hero_rows:
            self.hero_rows.remove(hero_row)
            hero_row.destroy()

    def clear(self):
        """Clear all hero rows."""
        for hero_row in self.hero_rows[:]:
            hero_row.destroy()
        self.hero_rows.clear()
        self.next_hero_id = 1

    def _get_heroes_payload(self):
        """Build save payload for all heroes."""
        return {
            "version": 1,
            "heroes": [hero_row.to_dict() for hero_row in self.hero_rows],
        }

    def _get_library_path(self):
        """Get canonical path for hero library file."""
        return os.path.join(os.path.dirname(__file__), self.HERO_LIBRARY_FILENAME)

    def _read_library_heroes(self):
        """Read hero library and return list of hero dictionaries."""
        file_path = self._get_library_path()
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Library Error", f"Could not read hero library:\n{exc}")
            return None

        heroes = payload.get("heroes", [])
        if not isinstance(heroes, list):
            messagebox.showerror("Library Error", "Invalid hero library format.")
            return None
        return [hero for hero in heroes if isinstance(hero, dict)]

    def _write_library_heroes(self, heroes):
        """Write list of hero dictionaries to hero library file."""
        file_path = self._get_library_path()
        payload = {"version": 1, "heroes": heroes}
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _normalize_name(self, name):
        """Normalize hero name for duplicate checks."""
        return str(name).strip().lower()

    def _hero_name_from_data(self, hero_data, fallback_index=None):
        """Extract displayable hero name from serialized hero data."""
        hero_name = hero_data.get("fields", {}).get("name", "").strip()
        if hero_name:
            return hero_name
        if fallback_index is not None:
            return f"Hero {fallback_index + 1}"
        return "Hero"

    def _generate_version_name(self, base_name, existing_heroes):
        """Generate non-duplicate version name based on base hero name."""
        normalized_existing = {
            self._normalize_name(self._hero_name_from_data(hero, idx))
            for idx, hero in enumerate(existing_heroes)
        }
        root = base_name.strip() if base_name.strip() else "Hero"
        version = 2
        while True:
            candidate = f"{root} v{version}"
            if self._normalize_name(candidate) not in normalized_existing:
                return candidate
            version += 1

    def save_hero(self, hero_row):
        """Open save menu for a single hero."""
        hero_data = hero_row.to_dict()
        current_name = hero_data.get("fields", {}).get("name", "").strip()
        if not current_name:
            messagebox.showerror("Save Failed", "Hero must have a non-empty Name.")
            return

        existing_heroes = self._read_library_heroes()
        if existing_heroes is None:
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Save Hero")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)

        ttk.Label(content, text=f"Hero: {current_name}",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 8))
        ttk.Label(content, text="Choose save mode:",
                  font=('Arial', 8)).pack(anchor="w", pady=(0, 6))

        existing_names = [
            self._hero_name_from_data(hero, idx)
            for idx, hero in enumerate(existing_heroes)
        ]

        update_name_var = tk.StringVar(value=existing_names[0] if existing_names else "")
        update_combo = ttk.Combobox(
            content,
            textvariable=update_name_var,
            values=existing_names,
            state="readonly",
            width=32
        )
        update_combo.pack(fill="x", pady=(0, 10))
        if not existing_names:
            update_combo.configure(state="disabled")

        buttons = ttk.Frame(content)
        buttons.pack(fill="x")

        def _save_new():
            normalized_target = self._normalize_name(current_name)
            normalized_existing = {
                self._normalize_name(name) for name in existing_names
            }
            if normalized_target in normalized_existing:
                messagebox.showerror(
                    "Duplicate Name",
                    "A saved hero with this name already exists. Use Update Existing or Save New Version."
                )
                return
            existing_heroes.append(hero_data)
            try:
                self._write_library_heroes(existing_heroes)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save hero:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Hero Saved", f"Saved new hero '{current_name}'.")

        def _update_existing():
            if not existing_names:
                messagebox.showerror("Update Failed", "No saved heroes to update.")
                return

            selected_name = update_combo.get().strip()
            if not selected_name:
                return

            selected_index = next(
                (idx for idx, name in enumerate(existing_names) if name == selected_name),
                None
            )
            if selected_index is None:
                return

            normalized_target = self._normalize_name(current_name)
            for idx, name in enumerate(existing_names):
                if idx != selected_index and self._normalize_name(name) == normalized_target:
                    messagebox.showerror(
                        "Duplicate Name",
                        "Another saved hero already uses this name. Rename current hero first."
                    )
                    return

            existing_heroes[selected_index] = hero_data
            try:
                self._write_library_heroes(existing_heroes)
            except OSError as exc:
                messagebox.showerror("Update Failed", f"Could not update hero:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Hero Updated", f"Updated saved hero '{selected_name}'.")

        def _save_new_version():
            version_name = self._generate_version_name(current_name, existing_heroes)
            version_data = hero_row.to_dict()
            version_data.setdefault("fields", {})
            version_data["fields"]["name"] = version_name
            existing_heroes.append(version_data)
            try:
                self._write_library_heroes(existing_heroes)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save hero version:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Hero Version Saved", f"Saved as '{version_name}'.")

        ttk.Button(buttons, text="Save New",
                   command=_save_new).pack(side="left")
        ttk.Button(buttons, text="Update Existing",
                   command=_update_existing).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save New Version",
                   command=_save_new_version).pack(side="left")
        ttk.Button(buttons, text="Cancel",
                   command=menu.destroy).pack(side="right")

    def load_heroes(self):
        """Open top-level load menu for selecting heroes from canonical file."""
        heroes_data = self._read_library_heroes()
        if heroes_data is None:
            return
        if not heroes_data:
            messagebox.showinfo("No Hero Library", f"No saved heroes in:\n{self._get_library_path()}")
            return

        self._open_load_menu(heroes_data)

    def _open_load_menu(self, heroes_data):
        """Open a top-level menu to load selected hero(s)."""
        valid_heroes = [hero for hero in heroes_data if isinstance(hero, dict)]
        if not valid_heroes:
            messagebox.showinfo("No Heroes", "Hero library is empty.")
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Load Heroes")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Select hero from library:",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 6))

        def _build_display_names():
            names = []
            for idx, hero in enumerate(valid_heroes):
                hero_name = hero.get("fields", {}).get("name", "").strip()
                if not hero_name:
                    hero_name = f"Hero {idx + 1}"
                names.append(hero_name)
            return names

        display_names = _build_display_names()

        selected_name = tk.StringVar(value=display_names[0])
        combo = ttk.Combobox(
            content,
            textvariable=selected_name,
            values=display_names,
            state="readonly",
            width=32
        )
        combo.pack(fill="x", pady=(0, 10))

        buttons = ttk.Frame(content)
        buttons.pack(fill="x")

        def _save_library():
            self._write_library_heroes(valid_heroes)

        def _refresh_combo():
            names = _build_display_names()
            combo["values"] = names
            if names:
                combo.current(0)
            else:
                menu.destroy()
                messagebox.showinfo("Library Updated", "All saved heroes were deleted.")

        def _load_selected_replace():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.clear()
            self.add_hero(hero_data=valid_heroes[selected_index])
            menu.destroy()

        def _load_selected_append():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.add_hero(hero_data=valid_heroes[selected_index])
            menu.destroy()

        def _load_all_replace():
            self.clear()
            for hero in valid_heroes:
                self.add_hero(hero_data=hero)
            if not self.hero_rows:
                self.add_hero()
            menu.destroy()

        def _delete_selected_saved():
            selected_index = combo.current()
            if selected_index < 0:
                return
            selected_name_local = combo.get() or f"Hero {selected_index + 1}"
            should_delete = messagebox.askyesno(
                "Delete Saved Hero",
                f"Delete saved hero '{selected_name_local}' from library?"
            )
            if not should_delete:
                return
            valid_heroes.pop(selected_index)
            try:
                _save_library()
            except OSError as exc:
                messagebox.showerror("Delete Failed", f"Could not update library:\n{exc}")
                return
            _refresh_combo()

        ttk.Button(buttons, text="Load Selected",
                   command=_load_selected_replace).pack(side="left")
        ttk.Button(buttons, text="Append Selected",
                   command=_load_selected_append).pack(side="left", padx=5)
        ttk.Button(buttons, text="Load All",
                   command=_load_all_replace).pack(side="left")
        ttk.Button(buttons, text="Delete Selected",
                   command=_delete_selected_saved).pack(side="left", padx=(5, 0))
        ttk.Button(buttons, text="Cancel",
                   command=menu.destroy).pack(side="right")
