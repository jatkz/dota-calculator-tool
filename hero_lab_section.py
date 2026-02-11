"""HeroLabSection class - orchestrates Hero Lab section"""

import tkinter as tk
from tkinter import ttk

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

    def __init__(self, parent, hero_id, on_delete, get_variables):
        self.parent = parent
        self.hero_id = hero_id
        self.on_delete = on_delete
        self.get_variables = get_variables
        self.modifiers = []
        self.spell_rows = []
        self.field_vars = {}
        self.field_entries = {}
        self.total_vars = {}

        self.frame = ttk.Frame(parent, relief='solid', borderwidth=1, padding="8")
        self._create_widgets()

    def _create_widgets(self):
        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 6))
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

    def add_spell(self):
        """Add a spell attached to this hero."""
        spell_row = HeroSpellRow(self.spells_container, self.delete_spell)
        spell_row.pack(fill="x", pady=2)
        self.spell_rows.append(spell_row)

    def delete_spell(self, spell_row):
        """Delete a spell attached to this hero."""
        self.spell_rows.remove(spell_row)
        spell_row.destroy()

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

    def add_hero(self):
        """Add a new hero row."""
        hero_id = self.next_hero_id
        self.next_hero_id += 1
        hero_row = HeroRow(
            self.heroes_container,
            hero_id,
            self.delete_hero,
            self.get_variables
        )
        hero_row.pack(fill="x", pady=4)
        self.hero_rows.append(hero_row)

    def delete_hero(self, hero_row):
        """Delete an existing hero row."""
        if len(self.hero_rows) <= 1:
            return
        self.hero_rows.remove(hero_row)
        hero_row.destroy()

    def clear(self):
        """Clear all hero rows."""
        for hero_row in self.hero_rows[:]:
            hero_row.destroy()
        self.hero_rows.clear()
        self.next_hero_id = 1
