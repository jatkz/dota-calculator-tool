import json
import os
import tkinter as tk
from tkinter import ttk


DEFAULT_INVENTORY_SLOTS = 6
DISPLAY_STAT_ORDER = [
    "health",
    "mana",
    "health_regen",
    "mana_regen",
    "move_speed",
    "armor",
    "magic_resist",
    "strength",
    "agility",
    "intelligence",
    "base_damage",
    "bonus_attack_damage",
    "total_attack_damage",
    "attack_speed",
    "base_attack_time",
    "turn_rate",
    "animation",
]

EDITABLE_STATS = [
    "health",
    "mana",
    "health_regen",
    "mana_regen",
    "move_speed",
    "armor",
    "magic_resist",
    "strength",
    "agility",
    "intelligence",
    "base_damage",
    "bonus_attack_damage",
    "total_attack_damage",
    "attack_speed",
    "base_attack_time",
    "turn_rate",
]

STAT_LABELS = {
    "health": "Health",
    "mana": "Mana",
    "health_regen": "Health Regen",
    "mana_regen": "Mana Regen",
    "move_speed": "Move Speed",
    "armor": "Armor",
    "magic_resist": "Magic Resist",
    "strength": "Strength",
    "agility": "Agility",
    "intelligence": "Intelligence",
    "base_damage": "Base Damage",
    "bonus_attack_damage": "Bonus Attack Damage",
    "total_attack_damage": "Total Attack Damage",
    "attack_speed": "Attack Speed",
    "base_attack_time": "Base Attack Time",
    "turn_rate": "Turn Rate",
    "animation": "Animation",
}


def _to_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return default
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return default


def _format_number(value):
    if isinstance(value, str):
        return value
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _sum_damage_bonuses(bonus_data, stats_data, attack_type, primary_attribute):
    total = 0.0
    has_direct_bonus_damage = any(
        key in bonus_data
        for key in (
            "attackDamage",
            "Attack Damage",
            "attack_damage",
            "meleeAttackDamage",
            "rangedAttackDamage",
            "attackDamageToStrAgiInt",
            "attackDamageToUniversal",
        )
    )
    has_attribute_bonus = any(key in bonus_data for key in ("strength", "agility", "intelligence"))

    total += _to_float(bonus_data.get("attackDamage"))
    total += _to_float(bonus_data.get("Attack Damage"))
    total += _to_float(bonus_data.get("attack_damage"))

    if attack_type == "melee":
        total += _to_float(bonus_data.get("meleeAttackDamage"))
    elif attack_type == "ranged":
        total += _to_float(bonus_data.get("rangedAttackDamage"))

    if primary_attribute in {"strength", "agility", "intelligence"}:
        total += _to_float(bonus_data.get("attackDamageToStrAgiInt"))
    elif primary_attribute == "universal":
        total += _to_float(bonus_data.get("attackDamageToUniversal"))

    if not has_direct_bonus_damage and not has_attribute_bonus:
        total += _to_float(stats_data.get("mainAttackDamage"))

    if primary_attribute == "strength" and not has_attribute_bonus:
        total += _to_float(stats_data.get("mainAttackDamageStrength"))
        total += _to_float(stats_data.get("mainAttackDamageStrengthHeroes"))
        total += _to_float(stats_data.get("mainAttackDamageStr"))
        total += _to_float(stats_data.get("strengthDamage"))
    elif primary_attribute == "agility" and not has_attribute_bonus:
        total += _to_float(stats_data.get("mainAttackDamageAgility"))
        total += _to_float(stats_data.get("mainAttackDamageAgi"))
        total += _to_float(stats_data.get("agilityDamage"))
    elif primary_attribute == "intelligence" and not has_attribute_bonus:
        total += _to_float(stats_data.get("mainAttackDamageIntelligence"))
        total += _to_float(stats_data.get("mainAttackDamageInt"))
        total += _to_float(stats_data.get("main_attack_damage_intelligence"))
        total += _to_float(stats_data.get("intelligenceDamage"))
    elif primary_attribute == "universal" and not has_attribute_bonus:
        total += _to_float(stats_data.get("mainAttackDamageUniversal"))
        total += _to_float(stats_data.get("mainAttackDamageUniversalHeroes"))
        total += _to_float(stats_data.get("main_attack_damage_universal"))
        total += _to_float(stats_data.get("universalDamage"))

    return total


def _apply_operation(current, operation, value):
    if operation == "add":
        return current + value
    if operation == "subtract":
        return current - value
    if operation == "multiply":
        return current * value
    if operation == "divide" and value != 0:
        return current / value
    return current


class ManualAdjustmentRow:
    def __init__(self, parent, on_change, on_delete):
        self.on_change = on_change
        self.on_delete = on_delete
        self.frame = ttk.Frame(parent)

        self.stat_var = tk.StringVar(value=EDITABLE_STATS[0])
        self.operation_var = tk.StringVar(value="add")
        self.value_var = tk.StringVar(value="0")

        ttk.Label(self.frame, text="Stat").pack(side="left", padx=(0, 4))
        stat_combo = ttk.Combobox(
            self.frame,
            textvariable=self.stat_var,
            values=EDITABLE_STATS,
            state="normal",
            width=22,
        )
        stat_combo.pack(side="left", padx=4)
        stat_combo.bind("<KeyRelease>", lambda e: self._handle_stat_keyrelease(e))
        stat_combo.bind("<FocusOut>", lambda e: self._normalize_stat_value())

        ttk.Label(self.frame, text="Operation").pack(side="left", padx=(8, 4))
        op_combo = ttk.Combobox(
            self.frame,
            textvariable=self.operation_var,
            values=["add", "subtract", "multiply", "divide"],
            state="readonly",
            width=10,
        )
        op_combo.pack(side="left", padx=4)

        ttk.Label(self.frame, text="Value").pack(side="left", padx=(8, 4))
        value_entry = ttk.Entry(self.frame, textvariable=self.value_var, width=10)
        value_entry.pack(side="left", padx=4)

        ttk.Button(self.frame, text="Remove", command=lambda: self.on_delete(self)).pack(side="left", padx=(8, 0))

        self.stat_var.trace_add("write", lambda *_: self.on_change())
        self.operation_var.trace_add("write", lambda *_: self.on_change())
        self.value_var.trace_add("write", lambda *_: self.on_change())

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def destroy(self):
        self.frame.destroy()

    def _normalize_stat_value(self):
        current = self.stat_var.get().strip()
        if not current:
            self.stat_var.set("")
            self.on_change()
            return

        exact = next((name for name in EDITABLE_STATS if name.lower() == current.lower()), None)
        if exact is not None:
            self.stat_var.set(exact)
            self.on_change()

    def _handle_stat_keyrelease(self, event):
        if event.keysym in {"Up", "Down", "Left", "Right", "Tab", "Return", "Escape"}:
            self.on_change()
            return

        widget = event.widget
        current = widget.get()
        cursor = widget.index(tk.INSERT)
        selection = widget.selection_present()

        should_autocomplete = selection or cursor == len(current)
        if should_autocomplete and current.strip():
            match = next((name for name in EDITABLE_STATS if name.lower().startswith(current.lower())), None)
            if match and match != current:
                widget.delete(0, tk.END)
                widget.insert(0, match)
                widget.icursor(len(current))
                widget.select_range(len(current), tk.END)
                self.stat_var.set(match)
                self.on_change()
                return

        self.on_change()

    def apply(self, stats):
        stat_name = self.stat_var.get()
        if stat_name not in stats:
            return None

        value = _to_float(self.value_var.get(), default=None)
        if value is None:
            return None

        return {
            "stat_name": stat_name,
            "operation": self.operation_var.get(),
            "value": value,
        }


class DatasetHeroApp:
    def __init__(self, parent):
        self.parent = parent
        self.dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
        self.heroes = self._load_heroes()
        self.items = self._load_items()
        self.adjustment_rows = []
        self.stat_value_vars = {key: tk.StringVar(value="") for key in DISPLAY_STAT_ORDER}

        self.hero_names = sorted(self.heroes.keys())
        self.item_names = [""] + sorted(self.items.keys())

        self.hero_var = tk.StringVar(value=self.hero_names[0] if self.hero_names else "")
        self.level_var = tk.StringVar(value="1")
        self.inventory_vars = [tk.StringVar(value="") for _ in range(DEFAULT_INVENTORY_SLOTS)]
        self.summary_var = tk.StringVar(value="")

        self._create_widgets()
        self.recalculate()

    def _load_heroes(self):
        with open(self.dataset_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.dataset_payload = payload
        heroes = payload.get("heroes", {})
        if isinstance(heroes, dict):
            return heroes
        return {}

    def _load_items(self):
        items = self.dataset_payload.get("items", {})
        if isinstance(items, dict):
            return items
        return {}

    def _create_widgets(self):
        canvas = tk.Canvas(self.parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, padding="16")

        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        ttk.Label(content, text="Dataset Hero Stats Lab", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(content)
        top.pack(fill="x", pady=(0, 12))

        ttk.Label(top, text="Hero").grid(row=0, column=0, sticky="w", padx=(0, 6))
        hero_combo = ttk.Combobox(top, textvariable=self.hero_var, values=self.hero_names, state="normal", width=28)
        hero_combo.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.hero_combo = hero_combo

        ttk.Label(top, text="Level").grid(row=0, column=2, sticky="w", padx=(0, 6))
        level_spin = ttk.Spinbox(top, from_=1, to=30, textvariable=self.level_var, width=6)
        level_spin.grid(row=0, column=3, sticky="w")

        ttk.Label(top, textvariable=self.summary_var, foreground="#666").grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        hero_combo.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
        hero_combo.bind("<KeyRelease>", lambda e: self._handle_combobox_keyrelease(e, self.hero_var, self.hero_names))
        hero_combo.bind("<FocusOut>", lambda e: self._normalize_combobox_value(self.hero_var, self.hero_names))
        self.level_var.trace_add("write", lambda *_: self.recalculate())

        inventory_frame = ttk.LabelFrame(content, text="Inventory")
        inventory_frame.pack(fill="x", pady=(0, 12))

        for index, item_var in enumerate(self.inventory_vars):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(inventory_frame, text=f"Slot {index + 1}").grid(row=row, column=col, sticky="w", padx=(8, 6), pady=6)
            combo = ttk.Combobox(
                inventory_frame,
                textvariable=item_var,
                values=self.item_names,
                state="normal",
                width=28,
            )
            combo.grid(row=row, column=col + 1, sticky="w", padx=(0, 12), pady=6)
            combo.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
            combo.bind("<KeyRelease>", lambda e, var=item_var: self._handle_combobox_keyrelease(e, var, self.item_names))
            combo.bind("<FocusOut>", lambda e, var=item_var: self._normalize_combobox_value(var, self.item_names))

        adjustments_frame = ttk.LabelFrame(content, text="Manual Stat Adjustments")
        adjustments_frame.pack(fill="x", pady=(0, 12))

        header = ttk.Frame(adjustments_frame)
        header.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(
            header,
            text="Apply add / subtract / multiply / divide to any computed stat after level and item bonuses.",
            foreground="#666",
        ).pack(side="left")
        ttk.Button(header, text="+ Add Adjustment", command=self.add_adjustment_row).pack(side="right")

        self.adjustments_container = ttk.Frame(adjustments_frame)
        self.adjustments_container.pack(fill="x", padx=8, pady=(0, 8))
        self.add_adjustment_row()

        stats_frame = ttk.LabelFrame(content, text="Calculated Stats")
        stats_frame.pack(fill="x")

        grid = ttk.Frame(stats_frame)
        grid.pack(fill="x", padx=12, pady=12)

        for idx, stat_name in enumerate(DISPLAY_STAT_ORDER):
            row = idx // 2
            col = (idx % 2) * 2
            ttk.Label(grid, text=STAT_LABELS[stat_name]).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
            ttk.Label(grid, textvariable=self.stat_value_vars[stat_name], font=("Arial", 10, "bold")).grid(
                row=row,
                column=col + 1,
                sticky="w",
                padx=(0, 24),
                pady=4,
            )

    def add_adjustment_row(self):
        row = ManualAdjustmentRow(self.adjustments_container, self.recalculate, self.remove_adjustment_row)
        row.pack(fill="x", pady=4)
        self.adjustment_rows.append(row)
        self.recalculate()

    def remove_adjustment_row(self, row):
        if row in self.adjustment_rows:
            self.adjustment_rows.remove(row)
            row.destroy()
            self.recalculate()

    def _parse_level(self):
        try:
            level = int(self.level_var.get())
        except ValueError:
            level = 1
        return max(1, min(30, level))

    def _normalize_combobox_value(self, variable, values):
        current = variable.get().strip()
        if not current:
            variable.set("")
            self.recalculate()
            return

        exact = next((name for name in values if name.lower() == current.lower()), None)
        if exact is not None:
            variable.set(exact)
            self.recalculate()

    def _handle_combobox_keyrelease(self, event, variable, values):
        if event.keysym in {"Up", "Down", "Left", "Right", "Tab", "Return", "Escape"}:
            self.recalculate()
            return

        widget = event.widget
        current = widget.get()
        cursor = widget.index(tk.INSERT)
        selection = widget.selection_present()

        # Only autocomplete while typing at the end of the current text, or while replacing selected suffix text.
        should_autocomplete = selection or cursor == len(current)
        if should_autocomplete and current.strip():
            match = next((name for name in values if name.lower().startswith(current.lower())), None)
            if match and match != current:
                widget.delete(0, tk.END)
                widget.insert(0, match)
                widget.icursor(len(current))
                widget.select_range(len(current), tk.END)
                variable.set(match)
                self.recalculate()
                return

        self.recalculate()


    def _sum_item_bonuses(self, hero_general):
        bonuses = {
            "strength": 0.0,
            "agility": 0.0,
            "intelligence": 0.0,
            "move_speed_flat": 0.0,
            "move_speed_pct": 0.0,
            "armor": 0.0,
            "magic_resist": 0.0,
            "attack_speed": 0.0,
            "mana": 0.0,
            "health": 0.0,
            "mana_regen": 0.0,
            "health_regen": 0.0,
            "flat_damage": 0.0,
            "bat_reduction_pct": 0.0,
        }
        item_names = []
        attack_type = str(hero_general.get("attack_type", "")).lower()
        primary_attribute = str(hero_general.get("primary_attribute", "")).lower()

        for slot_var in self.inventory_vars:
            name = slot_var.get().strip()
            if not name:
                continue
            item = self.items.get(name)
            if not item:
                continue
            item_names.append(name)

            bonus_data = item.get("bonus") or {}
            stats_data = item.get("stats") or {}

            bonuses["strength"] += _to_float(bonus_data.get("strength"))
            bonuses["agility"] += _to_float(bonus_data.get("agility"))
            bonuses["intelligence"] += _to_float(bonus_data.get("intelligence"))
            bonuses["armor"] += _to_float(bonus_data.get("armor"))
            bonuses["magic_resist"] += _to_float(bonus_data.get("magicResistance"))
            bonuses["attack_speed"] += _to_float(bonus_data.get("attackSpeed"))
            bonuses["attack_speed"] += _to_float(bonus_data.get("baseAttackSpeed"))
            bonuses["health"] += _to_float(bonus_data.get("health"))
            bonuses["mana"] += _to_float(bonus_data.get("mana"))
            bonuses["health_regen"] += _to_float(bonus_data.get("healthRegeneration"))
            bonuses["health_regen"] += _to_float(bonus_data.get("health_regeneration"))
            bonuses["mana_regen"] += _to_float(bonus_data.get("manaRegeneration"))
            bonuses["flat_damage"] += _sum_damage_bonuses(
                bonus_data,
                stats_data,
                attack_type,
                primary_attribute,
            )

            if attack_type == "melee":
                bonuses["move_speed_flat"] += _to_float(bonus_data.get("moveSpeedMelee"))
            elif attack_type == "ranged":
                bonuses["move_speed_flat"] += _to_float(bonus_data.get("moveSpeedRanged"))

            move_speed_value = bonus_data.get("moveSpeed")
            if "%" in str(move_speed_value):
                bonuses["move_speed_pct"] += _to_float(move_speed_value) / 100.0
            else:
                bonuses["move_speed_flat"] += _to_float(move_speed_value)

        return bonuses, item_names

    def _calculate_stats(self):
        hero_name = self.hero_var.get().strip()
        hero = self.heroes.get(hero_name, {})
        general = hero.get("general", {})
        level = self._parse_level()
        item_bonuses, selected_items = self._sum_item_bonuses(general)

        strength = _to_float(general.get("strength")) + (_to_float(general.get("strength_gain")) * (level - 1)) + item_bonuses["strength"]
        agility = _to_float(general.get("agility")) + (_to_float(general.get("agility_gain")) * (level - 1)) + item_bonuses["agility"]
        intelligence = _to_float(general.get("intelligence")) + (_to_float(general.get("intelligence_gain")) * (level - 1)) + item_bonuses["intelligence"]

        health = 120 + (22 * strength) + item_bonuses["health"]
        mana = 75 + (12 * intelligence) + item_bonuses["mana"]

        base_health_regen_offset = max(0.0, (_to_float(general.get("health")) - (120 + (22 * _to_float(general.get("strength"))))) / 100.0)
        base_mana_regen_offset = max(0.0, (_to_float(general.get("mana")) - (75 + (12 * _to_float(general.get("intelligence"))))) / 100.0)
        health_regen = base_health_regen_offset + (0.1 * strength) + item_bonuses["health_regen"]
        mana_regen = base_mana_regen_offset + (0.05 * intelligence) + item_bonuses["mana_regen"]

        base_armor_offset = _to_float(general.get("armor")) - (_to_float(general.get("agility")) / 6.0)
        armor = base_armor_offset + (agility / 6.0) + item_bonuses["armor"]

        magic_resist = _to_float(general.get("magic_resist")) + item_bonuses["magic_resist"]

        move_speed = (_to_float(general.get("move_speed")) + item_bonuses["move_speed_flat"]) * (1 + item_bonuses["move_speed_pct"])

        damage_values = general.get("damage", [])
        if isinstance(damage_values, list) and damage_values:
            base_damage = sum(_to_float(value) for value in damage_values) / len(damage_values)
        else:
            base_damage = _to_float(general.get("damage_avg"))

        primary_attribute = str(general.get("primary_attribute", "")).lower()
        base_strength = _to_float(general.get("strength"))
        base_agility = _to_float(general.get("agility"))
        base_intelligence = _to_float(general.get("intelligence"))

        if primary_attribute == "strength":
            attribute_damage_gain = strength - base_strength
        elif primary_attribute == "agility":
            attribute_damage_gain = agility - base_agility
        elif primary_attribute == "intelligence":
            attribute_damage_gain = intelligence - base_intelligence
        elif primary_attribute == "universal":
            attribute_damage_gain = 0.45 * (
                (strength - base_strength)
                + (agility - base_agility)
                + (intelligence - base_intelligence)
            )
        else:
            attribute_damage_gain = 0.0

        base_damage += attribute_damage_gain
        bonus_attack_damage = item_bonuses["flat_damage"]
        total_attack_damage = base_damage + bonus_attack_damage

        attack_speed = _to_float(general.get("attack_speed")) + (agility - _to_float(general.get("agility"))) + item_bonuses["attack_speed"]

        base_attack_time = _to_float(general.get("bat"))
        if item_bonuses["bat_reduction_pct"]:
            base_attack_time *= max(0.1, 1 - item_bonuses["bat_reduction_pct"])

        stats = {
            "health": health,
            "mana": mana,
            "health_regen": health_regen,
            "mana_regen": mana_regen,
            "move_speed": move_speed,
            "armor": armor,
            "magic_resist": magic_resist,
            "strength": strength,
            "agility": agility,
            "intelligence": intelligence,
            "base_damage": base_damage,
            "bonus_attack_damage": bonus_attack_damage,
            "total_attack_damage": total_attack_damage,
            "attack_speed": attack_speed,
            "base_attack_time": base_attack_time,
            "turn_rate": _to_float(general.get("turn_rate")),
            "animation": general.get("animation", ""),
        }

        base_stats = dict(stats)

        for row in self.adjustment_rows:
            adjustment = row.apply(stats)
            if not adjustment:
                continue

            stat_name = adjustment["stat_name"]
            current = stats.get(stat_name)
            if isinstance(current, str):
                continue

            stats[stat_name] = _apply_operation(
                current,
                adjustment["operation"],
                adjustment["value"],
            )

        strength_delta = stats["strength"] - base_stats["strength"]
        agility_delta = stats["agility"] - base_stats["agility"]
        intelligence_delta = stats["intelligence"] - base_stats["intelligence"]

        if strength_delta:
            stats["health"] += 22 * strength_delta
            stats["health_regen"] += 0.1 * strength_delta

        if agility_delta:
            stats["attack_speed"] += agility_delta
            stats["armor"] += agility_delta / 6.0

        if intelligence_delta:
            stats["magic_resist"] += 0.1 * intelligence_delta
            stats["mana"] += 12 * intelligence_delta
            stats["mana_regen"] += 0.05 * intelligence_delta

        attribute_damage_delta = 0.0
        if primary_attribute == "strength":
            attribute_damage_delta = strength_delta
        elif primary_attribute == "agility":
            attribute_damage_delta = agility_delta
        elif primary_attribute == "intelligence":
            attribute_damage_delta = intelligence_delta
        elif primary_attribute == "universal":
            attribute_damage_delta = 0.45 * (strength_delta + agility_delta + intelligence_delta)

        if attribute_damage_delta:
            stats["base_damage"] += attribute_damage_delta

        stats["total_attack_damage"] = stats["base_damage"] + stats["bonus_attack_damage"]

        item_summary = ", ".join(selected_items) if selected_items else "No items selected"
        self.summary_var.set(f"Level {level} • {item_summary}")
        return stats

    def recalculate(self, *_args):
        stats = self._calculate_stats()
        for key, var in self.stat_value_vars.items():
            var.set(_format_number(stats[key]))
