"""HeroLabSection class - orchestrates Hero Lab section"""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from modifiers import Modifier
from utils import safe_eval, armor_to_reduction


class HeroSpellRow:
    """Editable spell row with per-level values attached to a hero."""

    DAMAGE_TYPES = ("Physical", "Magic", "Pure")
    DEFAULT_LEVEL = {
        "damage": "0",
        "damage_type": "Magic",
        "hits": "1",
        "cast": "0",
        "stun": "0",
        "mana": "0",
        "cooldown": "0",
    }

    def __init__(self, parent, on_delete=None, show_delete_button=True, get_variables=None):
        self.parent = parent
        self.on_delete = on_delete
        self.show_delete_button = show_delete_button
        self.get_variables = get_variables
        self.frame = ttk.Frame(parent)
        self._syncing_level_fields = False
        self._syncing_level_controls = False
        self._loaded_level_index = 0
        self._visited_level_indices = {0}
        self.levels = []
        self.level_modifiers = []
        self._create_widgets()

    def _create_widgets(self):
        self.name_var = tk.StringVar(value="Spell")
        self.max_level_var = tk.StringVar(value="4")
        self.current_level_var = tk.StringVar(value="1")
        self.damage_var = tk.StringVar(value=self.DEFAULT_LEVEL["damage"])
        self.damage_type_var = tk.StringVar(value=self.DEFAULT_LEVEL["damage_type"])
        self.hits_var = tk.StringVar(value=self.DEFAULT_LEVEL["hits"])
        self.cast_var = tk.StringVar(value=self.DEFAULT_LEVEL["cast"])
        self.stun_var = tk.StringVar(value=self.DEFAULT_LEVEL["stun"])
        self.mana_var = tk.StringVar(value=self.DEFAULT_LEVEL["mana"])
        self.cooldown_var = tk.StringVar(value=self.DEFAULT_LEVEL["cooldown"])
        self.level_field_vars = [
            self.damage_var,
            self.damage_type_var,
            self.hits_var,
            self.cast_var,
            self.stun_var,
            self.mana_var,
            self.cooldown_var,
        ]

        top_row = ttk.Frame(self.frame)
        top_row.pack(fill="x")
        bottom_row = ttk.Frame(self.frame)
        bottom_row.pack(fill="x", pady=(2, 0))

        ttk.Label(top_row, text="Name:", font=('Arial', 8)).pack(side="left", padx=(0, 2))
        ttk.Entry(top_row, textvariable=self.name_var, width=14).pack(side="left", padx=2)

        ttk.Label(top_row, text="Max Lvl:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        self.max_level_combo = ttk.Combobox(
            top_row,
            textvariable=self.max_level_var,
            values=[str(i) for i in range(1, 11)],
            state="readonly",
            width=4
        )
        self.max_level_combo.pack(side="left", padx=2)

        ttk.Label(top_row, text="Current Lvl:", font=('Arial', 8)).pack(side="left", padx=(8, 2))
        self.current_level_combo = ttk.Combobox(
            top_row,
            textvariable=self.current_level_var,
            values=["1"],
            state="readonly",
            width=4
        )
        self.current_level_combo.pack(side="left", padx=2)

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

        if self.show_delete_button and self.on_delete:
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

        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=4)
        mod_header = ttk.Frame(self.frame)
        mod_header.pack(fill="x", pady=(0, 2))
        ttk.Label(mod_header, text="Level Modifiers",
                  font=('Arial', 8, 'bold')).pack(side="left")
        self.modifier_type_var = tk.StringVar(value="")
        self.modifier_combo = ttk.Combobox(
            mod_header,
            textvariable=self.modifier_type_var,
            state="readonly",
            width=20
        )
        self.modifier_combo["values"] = Modifier.get_available_types()
        if self.modifier_combo["values"]:
            self.modifier_type_var.set(self.modifier_combo["values"][0])
        self.modifier_combo.pack(side="right", padx=2)
        ttk.Button(mod_header, text="+ Add Modifier",
                   command=self.add_modifier).pack(side="right", padx=5)

        self.modifiers_container = ttk.Frame(self.frame)
        self.modifiers_container.pack(fill="x")

        self.max_level_var.trace('w', lambda *args: self._on_max_level_changed())
        self.current_level_var.trace('w', lambda *args: self._on_current_level_changed())
        for var in self.level_field_vars:
            var.trace('w', lambda *args: self._sync_current_level_values())

        self._ensure_levels(4)
        self._refresh_level_controls()
        self._load_current_level_values()

    def _default_level_data(self):
        """Get a new default level dictionary."""
        level_data = dict(self.DEFAULT_LEVEL)
        level_data["modifiers"] = []
        return level_data

    def _parse_level(self, raw_value, default_value):
        """Parse level integer with bounds."""
        try:
            value = int(str(raw_value).strip())
        except (TypeError, ValueError):
            return default_value
        return max(1, min(10, value))

    def _ensure_levels(self, max_level):
        """Resize level list to the provided max level."""
        max_level = max(1, min(10, int(max_level)))
        while len(self.levels) < max_level:
            if self.levels:
                prior = self.levels[-1]
                copied = dict(prior)
                copied["modifiers"] = json.loads(json.dumps(prior.get("modifiers", [])))
                self.levels.append(copied)
            else:
                self.levels.append(self._default_level_data())
        if len(self.levels) > max_level:
            self.levels = self.levels[:max_level]
        self._visited_level_indices = {
            idx for idx in self._visited_level_indices if idx < len(self.levels)
        }
        if self.levels:
            self._visited_level_indices.add(0)

    def _clone_level_from_previous_level(self, target_idx):
        """Copy level values/modifiers from previous numeric level into target level."""
        if target_idx <= 0 or target_idx >= len(self.levels):
            return
        source = self.levels[target_idx - 1]
        copied = dict(source)
        copied["modifiers"] = json.loads(json.dumps(source.get("modifiers", [])))
        self.levels[target_idx] = copied

    def _refresh_level_controls(self):
        """Refresh max/current level control values and options."""
        self._syncing_level_controls = True
        max_level = self._parse_level(self.max_level_var.get(), 1)
        if self.max_level_var.get() != str(max_level):
            self.max_level_var.set(str(max_level))
        self.current_level_combo["values"] = [str(i) for i in range(1, max_level + 1)]
        current_level = self._parse_level(self.current_level_var.get(), 1)
        current_level = max(1, min(max_level, current_level))
        if self.current_level_var.get() != str(current_level):
            self.current_level_var.set(str(current_level))
        self._syncing_level_controls = False

    def _on_max_level_changed(self):
        """Handle max level changes."""
        if self._syncing_level_controls:
            return
        self._save_current_level_modifiers()
        max_level = self._parse_level(self.max_level_var.get(), 1)
        self._ensure_levels(max_level)
        self._refresh_level_controls()
        self._load_current_level_values()

    def _on_current_level_changed(self):
        """Handle current level changes."""
        if self._syncing_level_controls:
            return
        self._save_current_level_modifiers()
        self._refresh_level_controls()
        target_idx = self._current_level_index()
        if target_idx not in self._visited_level_indices:
            self._clone_level_from_previous_level(target_idx)
        self._load_current_level_values()

    def _current_level_index(self):
        """Get zero-based current level index."""
        current_level = self._parse_level(self.current_level_var.get(), 1)
        return max(0, min(len(self.levels) - 1, current_level - 1))

    def _sync_current_level_values(self):
        """Persist currently displayed field values into active level slot."""
        if self._syncing_level_fields or not self.levels:
            return
        idx = self._current_level_index()
        level = self.levels[idx]
        level["damage"] = self.damage_var.get()
        damage_type = self.damage_type_var.get()
        if damage_type not in self.DAMAGE_TYPES:
            damage_type = self.DEFAULT_LEVEL["damage_type"]
            self.damage_type_var.set(damage_type)
        level["damage_type"] = damage_type
        level["hits"] = self.hits_var.get()
        level["cast"] = self.cast_var.get()
        level["stun"] = self.stun_var.get()
        level["mana"] = self.mana_var.get()
        level["cooldown"] = self.cooldown_var.get()

    def _load_current_level_values(self):
        """Load active level values into visible field vars."""
        if not self.levels:
            self._ensure_levels(1)
        idx = self._current_level_index()
        self._visited_level_indices.add(idx)
        level = self.levels[idx]
        self._syncing_level_fields = True
        self.damage_var.set(str(level.get("damage", self.DEFAULT_LEVEL["damage"])))
        damage_type = str(level.get("damage_type", self.DEFAULT_LEVEL["damage_type"]))
        if damage_type not in self.DAMAGE_TYPES:
            damage_type = self.DEFAULT_LEVEL["damage_type"]
        self.damage_type_var.set(damage_type)
        self.hits_var.set(str(level.get("hits", self.DEFAULT_LEVEL["hits"])))
        self.cast_var.set(str(level.get("cast", self.DEFAULT_LEVEL["cast"])))
        self.stun_var.set(str(level.get("stun", self.DEFAULT_LEVEL["stun"])))
        self.mana_var.set(str(level.get("mana", self.DEFAULT_LEVEL["mana"])))
        self.cooldown_var.set(str(level.get("cooldown", self.DEFAULT_LEVEL["cooldown"])))
        self._syncing_level_fields = False
        self._load_current_level_modifiers()

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

    def _save_current_level_modifiers(self, level_index=None):
        """Persist active modifier widgets to current level data."""
        if not self.levels:
            return
        if level_index is None:
            idx = self._loaded_level_index
        else:
            idx = max(0, min(len(self.levels) - 1, int(level_index)))
        self.levels[idx]["modifiers"] = [
            self._serialize_modifier(mod) for mod in self.level_modifiers
        ]

    def _destroy_level_modifiers(self):
        """Destroy active modifier widgets."""
        for mod in self.level_modifiers[:]:
            mod.destroy()
        self.level_modifiers.clear()

    def _load_modifier_into_ui(self, modifier_data):
        """Instantiate one modifier widget from saved dictionary."""
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
        mod.pack(fill="x", pady=1)
        if hasattr(mod, "update_display"):
            mod.update_display()
        self.level_modifiers.append(mod)

    def _load_current_level_modifiers(self):
        """Load modifier widgets for current level."""
        self._destroy_level_modifiers()
        if not self.levels:
            return
        idx = self._current_level_index()
        self._loaded_level_index = idx
        modifiers_data = self.levels[idx].get("modifiers", [])
        if not isinstance(modifiers_data, list):
            modifiers_data = []
        for modifier_data in modifiers_data:
            if isinstance(modifier_data, dict):
                self._load_modifier_into_ui(modifier_data)

    def _on_modifier_changed(self):
        """Update modifier displays and sync active level modifier payload."""
        for mod in self.level_modifiers:
            if hasattr(mod, "update_display"):
                mod.update_display()
        self._save_current_level_modifiers()

    def add_modifier(self):
        """Add a modifier to current spell level."""
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
        if not mod:
            return
        mod.pack(fill="x", pady=1)
        self.level_modifiers.append(mod)
        self._on_modifier_changed()

    def delete_modifier(self, mod):
        """Delete modifier from current spell level."""
        if mod in self.level_modifiers:
            self.level_modifiers.remove(mod)
        mod.destroy()
        self._on_modifier_changed()

    def pack(self, **kwargs):
        """Pack spell row widget."""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Destroy spell row widget."""
        self._destroy_level_modifiers()
        self.frame.destroy()

    def to_dict(self):
        """Serialize spell row to dictionary."""
        self._sync_current_level_values()
        self._save_current_level_modifiers()
        max_level = self._parse_level(self.max_level_var.get(), 1)
        current_level = self._parse_level(self.current_level_var.get(), 1)
        return {
            "name": self.name_var.get(),
            "max_level": max_level,
            "current_level": max(1, min(max_level, current_level)),
            "levels": [dict(level_data) for level_data in self.levels[:max_level]],
        }

    def load_from_dict(self, data):
        """Load spell row values from dictionary."""
        self.name_var.set(str(data.get("name", self.name_var.get())))
        levels_data = data.get("levels")
        if isinstance(levels_data, list) and levels_data:
            parsed_levels = []
            for level_data in levels_data[:10]:
                parsed = self._default_level_data()
                if isinstance(level_data, dict):
                    parsed["damage"] = str(level_data.get("damage", parsed["damage"]))
                    damage_type = str(level_data.get("damage_type", parsed["damage_type"]))
                    parsed["damage_type"] = (
                        damage_type if damage_type in self.DAMAGE_TYPES else self.DEFAULT_LEVEL["damage_type"]
                    )
                    parsed["hits"] = str(level_data.get("hits", parsed["hits"]))
                    parsed["cast"] = str(level_data.get("cast", parsed["cast"]))
                    parsed["stun"] = str(level_data.get("stun", parsed["stun"]))
                    parsed["mana"] = str(level_data.get("mana", parsed["mana"]))
                    parsed["cooldown"] = str(level_data.get("cooldown", parsed["cooldown"]))
                    modifiers_data = level_data.get("modifiers", [])
                    if isinstance(modifiers_data, list):
                        parsed["modifiers"] = [
                            mod for mod in modifiers_data if isinstance(mod, dict)
                        ]
                parsed_levels.append(parsed)
            self.levels = parsed_levels
            max_level_default = len(self.levels)
        else:
            # Backward compatibility for single-level spell payloads.
            legacy_level = self._default_level_data()
            legacy_level["damage"] = str(data.get("damage", legacy_level["damage"]))
            legacy_type = str(data.get("damage_type", legacy_level["damage_type"]))
            legacy_level["damage_type"] = (
                legacy_type if legacy_type in self.DAMAGE_TYPES else self.DEFAULT_LEVEL["damage_type"]
            )
            legacy_level["hits"] = str(data.get("hits", legacy_level["hits"]))
            legacy_level["cast"] = str(data.get("cast", legacy_level["cast"]))
            legacy_level["stun"] = str(data.get("stun", legacy_level["stun"]))
            legacy_level["mana"] = str(data.get("mana", legacy_level["mana"]))
            legacy_level["cooldown"] = str(data.get("cooldown", legacy_level["cooldown"]))
            legacy_modifiers = data.get("modifiers", [])
            if isinstance(legacy_modifiers, list):
                legacy_level["modifiers"] = [
                    mod for mod in legacy_modifiers if isinstance(mod, dict)
                ]
            self.levels = [legacy_level]
            max_level_default = 1

        max_level = self._parse_level(data.get("max_level", max_level_default), max_level_default)
        self._ensure_levels(max_level)
        self._visited_level_indices = set(range(len(self.levels)))
        current_level = self._parse_level(data.get("current_level", 1), 1)
        self.max_level_var.set(str(max_level))
        self.current_level_var.set(str(max(1, min(max_level, current_level))))
        self._refresh_level_controls()
        self._load_current_level_values()


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

    def __init__(
        self,
        parent,
        hero_id,
        on_delete,
        on_save,
        get_variables,
        get_item_library_items,
        get_spell_library_spells
    ):
        self.parent = parent
        self.hero_id = hero_id
        self.on_delete = on_delete
        self.on_save = on_save
        self.get_variables = get_variables
        self.get_item_library_items = get_item_library_items
        self.get_spell_library_spells = get_spell_library_spells
        self.modifiers = []
        self.spell_rows = []
        self.items = []
        self.item_widgets = []
        self.item_modifiers = []
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

        # Items block
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        items_header = ttk.Frame(self.frame)
        items_header.pack(fill="x", pady=(0, 2))
        ttk.Label(items_header, text="Items",
                  font=('Arial', 9, 'bold')).pack(side="left")
        ttk.Button(items_header, text="+ Add Item From Library",
                   command=self.open_add_item_menu).pack(side="right")

        self.items_container = ttk.Frame(self.frame)
        self.items_container.pack(fill="x")

        # Spells block
        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        spells_header = ttk.Frame(self.frame)
        spells_header.pack(fill="x", pady=(0, 2))
        ttk.Label(spells_header, text="Spells",
                  font=('Arial', 9, 'bold')).pack(side="left")
        ttk.Button(spells_header, text="+ Add Spell From Library",
                   command=self.open_add_spell_menu).pack(side="right")
        ttk.Button(spells_header, text="+ Add Spell",
                   command=self.add_spell).pack(side="right", padx=(0, 5))

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
        # Hidden container for item-derived modifier instances used in totals math.
        self.item_modifiers_eval_container = ttk.Frame(self.frame)
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
                entry.pack(anchor="w")
            elif key == "level":
                level_input = ttk.Frame(field_frame)
                level_input.pack(anchor="w")
                entry = ttk.Entry(level_input, textvariable=var, width=6)
                entry.pack(side="left")
                ttk.Button(
                    level_input,
                    text="+",
                    width=2,
                    command=lambda v=var: self._change_level_value(v, 1)
                ).pack(side="left", padx=(2, 0))
                ttk.Button(
                    level_input,
                    text="-",
                    width=2,
                    command=lambda v=var: self._change_level_value(v, -1)
                ).pack(side="left", padx=(2, 0))
            else:
                entry = ttk.Entry(field_frame, textvariable=var, width=11)
                entry.pack(anchor="w")
            self.field_vars[key] = var
            self.field_entries[key] = entry
            var.trace('w', lambda *args: self.update_totals())

    def _change_level_value(self, level_var, step):
        """Increment/decrement hero level by step, clamped to at least 1."""
        variables = self.get_variables() if self.get_variables else None
        current_value = safe_eval(level_var.get(), variables)
        if current_value is None:
            current_level = 1
        else:
            try:
                current_level = int(current_value)
            except (TypeError, ValueError):
                current_level = 1
        new_level = max(1, current_level + step)
        level_var.set(str(new_level))

    def _create_totals_widgets(self):
        """Create display rows for all requested totals."""
        totals = [
            ("total_strength", "Total Strength"),
            ("total_agility", "Total Agility"),
            ("total_intelligence", "Total Intelligence"),
            ("total_item_gold", "Total Item Gold"),
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

    def _get_total_enabled_item_gold(self):
        """Get total gold from enabled attached items."""
        variables = self.get_variables() if self.get_variables else None
        total = 0.0
        for item in self.items:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            fields = item.get("fields", {})
            gold_expr = str(fields.get("gold_amount", "0"))
            gold_value = safe_eval(gold_expr, variables)
            if gold_value is not None:
                total += max(0.0, gold_value)
        return total

    def _destroy_item_modifiers(self):
        """Destroy cached item-derived modifier instances."""
        for mod in self.item_modifiers[:]:
            mod.destroy()
        self.item_modifiers.clear()

    def _rebuild_item_modifiers(self):
        """Build modifier instances from attached item data for calculations."""
        self._destroy_item_modifiers()
        for item in self.items:
            if not item.get("enabled", True):
                continue
            modifiers_data = item.get("modifiers", [])
            if not isinstance(modifiers_data, list):
                continue
            for modifier_data in modifiers_data:
                type_name = modifier_data.get("type")
                if not type_name:
                    continue
                mod = Modifier.create(
                    type_name,
                    self.item_modifiers_eval_container,
                    lambda: None,
                    lambda _: None,
                    get_variables=self.get_variables
                )
                if not mod:
                    continue
                for key, value in modifier_data.get("values", {}).items():
                    var = getattr(mod, key, None)
                    if hasattr(var, "set"):
                        var.set(value)
                self.item_modifiers.append(mod)

    def update_totals(self):
        """Recalculate and refresh all totals for this hero."""
        all_modifiers = self.modifiers + self.item_modifiers

        base_hp = self._get_numeric_field("base_hp")
        base_hp_regen = self._get_numeric_field("base_hp_regen")
        base_movespeed = self._get_numeric_field("movespeed")
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

        bonus_strength = sum(mod.get_strength_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_agility = sum(mod.get_agility_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_intelligence = sum(mod.get_intelligence_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_movespeed_flat = sum(mod.get_movespeed_flat_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_movespeed_pct = sum(mod.get_movespeed_pct_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_armor = sum(mod.get_armor_bonus() for mod in all_modifiers if mod.is_enabled())
        magic_resistance_bonus_sources = [
            mod.get_magic_resistance_bonus() for mod in all_modifiers if mod.is_enabled()
        ]
        bonus_attack_speed = sum(mod.get_attack_speed_bonus() for mod in all_modifiers if mod.is_enabled())
        total_bat_reduction_pct = sum(mod.get_bat_reduction_pct() for mod in all_modifiers if mod.is_enabled())
        bonus_mana = sum(mod.get_mana_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_hp = sum(mod.get_hp_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_mana_regen = sum(mod.get_mana_regen_flat_bonus() for mod in all_modifiers if mod.is_enabled())
        bonus_hp_regen = sum(mod.get_hp_regen_flat_bonus() for mod in all_modifiers if mod.is_enabled())

        level_factor = max(0.0, level - 1.0)
        strength = base_strength + (strength_per_level * level_factor) + bonus_strength
        agility = base_agility + (agility_per_level * level_factor) + bonus_agility
        intelligence = base_intelligence + (intelligence_per_level * level_factor) + bonus_intelligence

        total_hp = max(0.0, base_hp + (strength * 22.0) + bonus_hp)
        total_health_regen = base_hp_regen + (strength * 0.1) + bonus_hp_regen
        total_mana = max(0.0, 75.0 + (intelligence * 12.0) + bonus_mana)
        total_mana_regen = (intelligence * 0.05) + bonus_mana_regen
        total_item_gold = self._get_total_enabled_item_gold()

        effective_attack_speed = max(0.0, attack_speed + agility + bonus_attack_speed)
        effective_bat = max(0.01, bat * (1 - max(0.0, min(0.95, total_bat_reduction_pct))))
        attacks_per_second = 0.0
        if effective_bat > 0:
            attacks_per_second = effective_attack_speed / (100 * effective_bat)
        seconds_between_attack = 0.0
        if attacks_per_second > 0:
            seconds_between_attack = 1.0 / attacks_per_second

        attribute_damage = self._get_primary_attribute_bonus(strength, agility, intelligence)
        raw_base_damage = base_damage + attribute_damage

        total_bonus_damage = 0.0
        for mod in all_modifiers:
            if mod.is_enabled() and self._is_flat_damage_modifier(mod):
                total_bonus_damage += mod.get_damage_for_hit(1, 0.0)

        total_base_damage = raw_base_damage
        total_auto_attack_damage = raw_base_damage + total_bonus_damage
        for mod in all_modifiers:
            if mod.is_enabled() and self._is_percentage_damage_modifier(mod):
                total_base_damage = mod.apply_damage_for_hit(1, total_base_damage, raw_base_damage)
                total_auto_attack_damage = mod.apply_damage_for_hit(1, total_auto_attack_damage, raw_base_damage)

        estimated_physical_damage = total_auto_attack_damage
        for mod in all_modifiers:
            if mod.is_enabled() and not self._is_flat_damage_modifier(mod) and not self._is_percentage_damage_modifier(mod):
                estimated_physical_damage = mod.apply_damage_for_hit(
                    1, estimated_physical_damage, raw_base_damage
                )

        estimated_magic_damage = 0.0
        for mod in all_modifiers:
            if mod.is_enabled():
                estimated_magic_damage += mod.get_magic_damage_for_hit(1, estimated_physical_damage)

        total_estimated_attack_damage = estimated_physical_damage + estimated_magic_damage
        estimated_dps = total_estimated_attack_damage * attacks_per_second

        total_movespeed = (base_movespeed + bonus_movespeed_flat) * (1 + bonus_movespeed_pct)
        armor = base_armor + (agility / 6.0) + bonus_armor
        physical_reduction = armor_to_reduction(armor)
        base_magic_resistance_total = self._clamp(base_magic_resist + (intelligence * 0.1), 0, 100)
        remaining_magic_damage = 1 - (base_magic_resistance_total / 100.0)
        for bonus in magic_resistance_bonus_sources:
            bonus_fraction = self._clamp(bonus, 0, 100) / 100.0
            remaining_magic_damage *= (1 - bonus_fraction)
        magic_resistance = self._clamp((1 - remaining_magic_damage) * 100.0, 0, 100)
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
        self.total_vars["total_item_gold"].set(self._format_value(total_item_gold))
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
        self.total_vars["total_movespeed"].set(self._format_value(total_movespeed))
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
        spell_row = HeroSpellRow(
            self.spells_container,
            self.delete_spell,
            show_delete_button=True,
            get_variables=self.get_variables
        )
        if spell_data:
            spell_row.load_from_dict(spell_data)
        spell_row.pack(fill="x", pady=2)
        self.spell_rows.append(spell_row)

    def delete_spell(self, spell_row):
        """Delete a spell attached to this hero."""
        self.spell_rows.remove(spell_row)
        spell_row.destroy()

    def _spell_display_name(self, spell_data, fallback_index=None):
        """Get display name for a spell payload."""
        spell_name = str(spell_data.get("name", "")).strip() if isinstance(spell_data, dict) else ""
        if spell_name:
            return spell_name
        if fallback_index is not None:
            return f"Spell {fallback_index + 1}"
        return "Spell"

    def open_add_spell_menu(self):
        """Open a menu to attach a spell from spell library."""
        library_spells = self.get_spell_library_spells() if self.get_spell_library_spells else []
        if not library_spells:
            messagebox.showinfo("No Spell Library", "No saved spells found in spell library.")
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Add Spell")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Select spell from library:",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 6))

        display_names = [self._spell_display_name(spell, idx) for idx, spell in enumerate(library_spells)]
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

        def _add_selected():
            selected_index = combo.current()
            if selected_index < 0:
                return
            selected_spell = library_spells[selected_index]
            copied_spell = json.loads(json.dumps(selected_spell))
            self.add_spell(spell_data=copied_spell)
            menu.destroy()

        ttk.Button(buttons, text="Add Selected", command=_add_selected).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=menu.destroy).pack(side="right")

    def _item_display_name(self, item_data, fallback_index=None):
        """Get display name for attached item."""
        item_name = item_data.get("fields", {}).get("name", "").strip()
        if item_name:
            return item_name
        if fallback_index is not None:
            return f"Item {fallback_index + 1}"
        return "Item"

    def _refresh_items_display(self):
        """Refresh attached items UI."""
        for _, frame in self.item_widgets:
            frame.destroy()
        self.item_widgets.clear()

        for idx, item_data in enumerate(self.items):
            row = ttk.Frame(self.items_container)
            row.pack(fill="x", pady=1)

            enabled_var = tk.BooleanVar(value=item_data.get("enabled", True))
            enabled_var.trace('w', lambda *args, i=idx, v=enabled_var: self._toggle_item_enabled(i, v))
            ttk.Checkbutton(row, variable=enabled_var).pack(side="left", padx=(0, 4))

            name = self._item_display_name(item_data, idx)
            ttk.Label(row, text=name, font=('Arial', 8, 'bold'),
                      foreground='#3d5a80').pack(side="left")

            remove_btn = ttk.Button(
                row, text="✕", width=2, command=lambda i=idx: self._remove_item(i)
            )
            remove_btn.pack(side="left", padx=4)
            self.item_widgets.append((item_data, row, enabled_var))

    def _toggle_item_enabled(self, index, enabled_var):
        """Enable/disable an attached item and refresh totals."""
        if 0 <= index < len(self.items):
            self.items[index]["enabled"] = bool(enabled_var.get())
            self._rebuild_item_modifiers()
            self.update_totals()

    def _remove_item(self, index):
        """Remove attached item by index."""
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._refresh_items_display()
            self._rebuild_item_modifiers()
            self.update_totals()

    def open_add_item_menu(self):
        """Open a menu to attach an item from item library."""
        library_items = self.get_item_library_items() if self.get_item_library_items else []
        if not library_items:
            messagebox.showinfo("No Item Library", "No saved items found in item library.")
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Add Item")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Select item from library:",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 6))

        display_names = [self._item_display_name(item, idx) for idx, item in enumerate(library_items)]
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

        def _add_selected():
            selected_index = combo.current()
            if selected_index < 0:
                return
            selected_item = library_items[selected_index]
            # Deep copy to keep hero-attached item stable if library changes later.
            copied_item = json.loads(json.dumps(selected_item))
            copied_item.setdefault("enabled", True)
            self.items.append(copied_item)
            self._refresh_items_display()
            self._rebuild_item_modifiers()
            self.update_totals()
            menu.destroy()

        ttk.Button(buttons, text="Add Selected", command=_add_selected).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=menu.destroy).pack(side="right")

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
        for item in self.items:
            if isinstance(item, dict):
                item.setdefault("enabled", True)
        self._refresh_items_display()
        self._rebuild_item_modifiers()
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
        self._destroy_item_modifiers()
        self.frame.destroy()


class ItemWorkbenchRow:
    """Single item row for creating and persisting reusable items."""

    def __init__(self, parent, item_id, on_delete, on_save, get_variables):
        self.parent = parent
        self.item_id = item_id
        self.on_delete = on_delete
        self.on_save = on_save
        self.get_variables = get_variables
        self.field_vars = {}
        self.notes_var = tk.StringVar(value="")
        self.modifiers = []

        self.frame = ttk.Frame(parent, relief='solid', borderwidth=1, padding="8")
        self._create_widgets()

    def _create_widgets(self):
        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 6))
        ttk.Button(header, text="Save", width=8,
                   command=lambda: self.on_save(self)).pack(side="right", padx=(0, 4))
        ttk.Button(header, text="Delete", width=8,
                   command=lambda: self.on_delete(self)).pack(side="right")

        fields_row = ttk.Frame(self.frame)
        fields_row.pack(fill="x", pady=(0, 4))
        ttk.Label(fields_row, text="Name:", font=('Arial', 8)).pack(side="left", padx=(0, 4))
        self.field_vars["name"] = tk.StringVar(value="Item")
        ttk.Entry(fields_row, textvariable=self.field_vars["name"], width=30).pack(side="left")

        notes_row = ttk.Frame(self.frame)
        notes_row.pack(fill="x", pady=(0, 4))
        ttk.Label(notes_row, text="Notes:", font=('Arial', 8)).pack(side="left", padx=(0, 4))
        ttk.Entry(notes_row, textvariable=self.notes_var, width=80).pack(side="left", fill="x", expand=True)

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

    def add_modifier(self):
        """Add a modifier attached to this item."""
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
        """Delete an item modifier."""
        self.modifiers.remove(mod)
        mod.destroy()
        self._on_modifier_changed()

    def _on_modifier_changed(self):
        """Update modifier displays after changes."""
        for mod in self.modifiers:
            mod.update_display()

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
        """Serialize item row to dictionary."""
        return {
            "item_id": self.item_id,
            "fields": {key: var.get() for key, var in self.field_vars.items()},
            "notes": self.notes_var.get(),
            "modifiers": [self._serialize_modifier(mod) for mod in self.modifiers],
        }

    def load_from_dict(self, data):
        """Load item row values from dictionary."""
        for key, value in data.get("fields", {}).items():
            if key in self.field_vars:
                self.field_vars[key].set(str(value))
        self.notes_var.set(str(data.get("notes", "")))

        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()
        for modifier_data in data.get("modifiers", []):
            self._load_modifier(modifier_data)

    def pack(self, **kwargs):
        """Pack row widget."""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Destroy row widget."""
        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()
        self.frame.destroy()


class HeroLabSection:
    """Orchestrates the Hero Lab section"""

    HERO_LIBRARY_FILENAME = "hero_library.json"
    ITEM_LIBRARY_FILENAME = "item_library.json"
    SPELL_LIBRARY_FILENAME = "spell_library.json"

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
        self.item_rows = []
        self.next_hero_id = 1
        self.next_item_id = 1
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
            self.get_variables,
            self.get_item_library_items,
            self.get_spell_library_spells
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

    def clear_heroes(self):
        """Clear all hero rows."""
        for hero_row in self.hero_rows[:]:
            hero_row.destroy()
        self.hero_rows.clear()
        self.next_hero_id = 1

    def add_item(self, item_data=None):
        """Add a new item workbench row."""
        if item_data and isinstance(item_data.get("item_id"), int):
            item_id = item_data["item_id"]
            self.next_item_id = max(self.next_item_id, item_id + 1)
        else:
            item_id = self.next_item_id
            self.next_item_id += 1

        item_row = ItemWorkbenchRow(
            self.items_container,
            item_id,
            self.delete_item,
            self.save_item,
            self.get_variables
        )
        if item_data:
            item_row.load_from_dict(item_data)
        item_row.pack(fill="x", pady=4)
        self.item_rows.append(item_row)

    def delete_item(self, item_row):
        """Delete an existing item row."""
        if item_row in self.item_rows:
            self.item_rows.remove(item_row)
            item_row.destroy()

    def clear_items(self):
        """Clear all item rows."""
        for item_row in self.item_rows[:]:
            item_row.destroy()
        self.item_rows.clear()
        self.next_item_id = 1

    def clear(self):
        """Clear all hero and item rows."""
        self.clear_heroes()
        self.clear_items()

    def _get_heroes_payload(self):
        """Build save payload for all heroes."""
        return {
            "version": 1,
            "heroes": [hero_row.to_dict() for hero_row in self.hero_rows],
        }

    def _get_library_path(self):
        """Get canonical path for hero library file."""
        return os.path.join(os.path.dirname(__file__), self.HERO_LIBRARY_FILENAME)

    def _get_item_library_path(self):
        """Get canonical path for item library file."""
        return os.path.join(os.path.dirname(__file__), self.ITEM_LIBRARY_FILENAME)

    def _get_spell_library_path(self):
        """Get canonical path for spell library file."""
        return os.path.join(os.path.dirname(__file__), self.SPELL_LIBRARY_FILENAME)

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

    def _read_library_items(self):
        """Read item library and return list of item dictionaries."""
        file_path = self._get_item_library_path()
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Library Error", f"Could not read item library:\n{exc}")
            return None

        items = payload.get("items", [])
        if not isinstance(items, list):
            messagebox.showerror("Library Error", "Invalid item library format.")
            return None
        return [item for item in items if isinstance(item, dict)]

    def get_item_library_items(self):
        """Get item library list for attaching items to heroes."""
        items = self._read_library_items()
        return items if items is not None else []

    def _read_library_spells(self):
        """Read spell library and return list of spell dictionaries."""
        file_path = self._get_spell_library_path()
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Library Error", f"Could not read spell library:\n{exc}")
            return None

        spells = payload.get("spells", [])
        if not isinstance(spells, list):
            messagebox.showerror("Library Error", "Invalid spell library format.")
            return None
        return [spell for spell in spells if isinstance(spell, dict)]

    def get_spell_library_spells(self):
        """Get spell library list for attaching spells to heroes."""
        spells = self._read_library_spells()
        return spells if spells is not None else []

    def _write_library_items(self, items):
        """Write list of item dictionaries to item library file."""
        file_path = self._get_item_library_path()
        payload = {"version": 1, "items": items}
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

    def _item_name_from_data(self, item_data, fallback_index=None):
        """Extract displayable item name from serialized item data."""
        item_name = item_data.get("fields", {}).get("name", "").strip()
        if item_name:
            return item_name
        if fallback_index is not None:
            return f"Item {fallback_index + 1}"
        return "Item"

    def _generate_item_version_name(self, base_name, existing_items):
        """Generate non-duplicate version name based on base item name."""
        normalized_existing = {
            self._normalize_name(self._item_name_from_data(item, idx))
            for idx, item in enumerate(existing_items)
        }
        root = base_name.strip() if base_name.strip() else "Item"
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

        selected_update_index = next(
            (idx for idx, name in enumerate(existing_names)
             if self._normalize_name(name) == self._normalize_name(current_name)),
            0
        ) if existing_names else -1
        update_name_var = tk.StringVar(
            value=existing_names[selected_update_index] if selected_update_index >= 0 else ""
        )
        update_combo = ttk.Combobox(
            content,
            textvariable=update_name_var,
            values=existing_names,
            state="readonly",
            width=32
        )
        update_combo.pack(fill="x", pady=(0, 10))
        if selected_update_index >= 0:
            update_combo.current(selected_update_index)
        else:
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

    def save_item(self, item_row):
        """Open save menu for a single item."""
        item_data = item_row.to_dict()
        current_name = item_data.get("fields", {}).get("name", "").strip()
        if not current_name:
            messagebox.showerror("Save Failed", "Item must have a non-empty Name.")
            return

        existing_items = self._read_library_items()
        if existing_items is None:
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Save Item")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)

        ttk.Label(content, text=f"Item: {current_name}",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 8))
        ttk.Label(content, text="Choose save mode:",
                  font=('Arial', 8)).pack(anchor="w", pady=(0, 6))

        existing_names = [
            self._item_name_from_data(item, idx)
            for idx, item in enumerate(existing_items)
        ]

        selected_update_index = next(
            (idx for idx, name in enumerate(existing_names)
             if self._normalize_name(name) == self._normalize_name(current_name)),
            0
        ) if existing_names else -1
        update_name_var = tk.StringVar(
            value=existing_names[selected_update_index] if selected_update_index >= 0 else ""
        )
        update_combo = ttk.Combobox(
            content,
            textvariable=update_name_var,
            values=existing_names,
            state="readonly",
            width=32
        )
        update_combo.pack(fill="x", pady=(0, 10))
        if selected_update_index >= 0:
            update_combo.current(selected_update_index)
        else:
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
                    "A saved item with this name already exists. Use Update Existing or Save New Version."
                )
                return
            existing_items.append(item_data)
            try:
                self._write_library_items(existing_items)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save item:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Item Saved", f"Saved new item '{current_name}'.")

        def _update_existing():
            if not existing_names:
                messagebox.showerror("Update Failed", "No saved items to update.")
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
                        "Another saved item already uses this name. Rename current item first."
                    )
                    return

            existing_items[selected_index] = item_data
            try:
                self._write_library_items(existing_items)
            except OSError as exc:
                messagebox.showerror("Update Failed", f"Could not update item:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Item Updated", f"Updated saved item '{selected_name}'.")

        def _save_new_version():
            version_name = self._generate_item_version_name(current_name, existing_items)
            version_data = item_row.to_dict()
            version_data.setdefault("fields", {})
            version_data["fields"]["name"] = version_name
            existing_items.append(version_data)
            try:
                self._write_library_items(existing_items)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save item version:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Item Version Saved", f"Saved as '{version_name}'.")

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
            self.clear_heroes()
            self.add_hero(hero_data=valid_heroes[selected_index])
            menu.destroy()

        def _load_selected_append():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.add_hero(hero_data=valid_heroes[selected_index])
            menu.destroy()

        def _load_all_replace():
            self.clear_heroes()
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

    def load_items(self):
        """Open top-level load menu for selecting items from item library."""
        items_data = self._read_library_items()
        if items_data is None:
            return
        if not items_data:
            messagebox.showinfo("No Item Library", f"No saved items in:\n{self._get_item_library_path()}")
            return

        self._open_item_load_menu(items_data)

    def _open_item_load_menu(self, items_data):
        """Open a top-level menu to load selected item(s)."""
        valid_items = [item for item in items_data if isinstance(item, dict)]
        if not valid_items:
            messagebox.showinfo("No Items", "Item library is empty.")
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Load Items")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)

        ttk.Label(content, text="Select item from library:",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 6))

        def _build_display_names():
            names = []
            for idx, item in enumerate(valid_items):
                item_name = item.get("fields", {}).get("name", "").strip()
                if not item_name:
                    item_name = f"Item {idx + 1}"
                names.append(item_name)
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
            self._write_library_items(valid_items)

        def _refresh_combo():
            names = _build_display_names()
            combo["values"] = names
            if names:
                combo.current(0)
            else:
                menu.destroy()
                messagebox.showinfo("Library Updated", "All saved items were deleted.")

        def _load_selected_replace():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.clear_items()
            self.add_item(item_data=valid_items[selected_index])
            menu.destroy()

        def _load_selected_append():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.add_item(item_data=valid_items[selected_index])
            menu.destroy()

        def _load_all_replace():
            self.clear_items()
            for item in valid_items:
                self.add_item(item_data=item)
            menu.destroy()

        def _delete_selected_saved():
            selected_index = combo.current()
            if selected_index < 0:
                return
            selected_name_local = combo.get() or f"Item {selected_index + 1}"
            should_delete = messagebox.askyesno(
                "Delete Saved Item",
                f"Delete saved item '{selected_name_local}' from library?"
            )
            if not should_delete:
                return
            valid_items.pop(selected_index)
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
