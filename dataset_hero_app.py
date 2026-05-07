import json
import math
import os
import re
import tkinter as tk
from difflib import SequenceMatcher
from tkinter import ttk

from attack_calculations import apply_magic_resistance, apply_physical_reduction


DEFAULT_INVENTORY_SLOTS = 6
DEFAULT_ACTION_SLOTS = 10
MAX_SKILL_BUILD_LEVEL = 30
DEFAULT_TIMELINE_SECONDS = 20
HERO_GRID_COLUMNS = 6
HERO_SEARCH_RESULT_LIMIT = 60
HERO_PICKER_BUTTON_PIXEL_WIDTH = 96
HERO_PICKER_BUTTON_PIXEL_HEIGHT = 54
HERO_PICKER_BUTTON_WRAP = 88
MAX_ATTRIBUTE_BONUS_POINTS = 7
ATTRIBUTE_BONUS_PER_POINT = 2
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
    "attacks_per_second",
    "attack_interval",
    "attack_range",
    "projectile_speed",
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
    "attacks_per_second": "Attacks / Second",
    "attack_interval": "Attack Interval",
    "attack_range": "Attack Range",
    "projectile_speed": "Projectile Speed",
    "turn_rate": "Turn Rate",
    "animation": "Animation",
}

TALENT_TIERS = ("10", "15", "20", "25")
TALENT_EXTRA_UNLOCK_LEVELS = {
    "10": 27,
    "15": 28,
    "20": 29,
    "25": 30,
}
TALENT_CHOICES = ("None", "Left", "Right")
ACTION_AUTO_ATTACK = "Auto Attack"
ACTION_STOP = "Stop"
ACTION_EMPTY = "-"
TARGET_NONE = "None"
TARGET_MANUAL = "Manual Unit"
TARGET_HERO = "Hero"


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


def _round_attribute(value):
    return float(int(float(value) + 0.5))


def _first_numeric_value(value_text):
    text = str(value_text or "").strip()
    if not text:
        return None, False

    is_percent = "%" in text
    match = re.search(r"[+-]?\d+(?:\.\d+)?", text)
    if not match:
        return None, is_percent
    return float(match.group(0)), is_percent


def _empty_modifiers():
    return {
        "strength": 0.0,
        "agility": 0.0,
        "intelligence": 0.0,
        "health_flat": 0.0,
        "health_pct": 0.0,
        "health_regen_flat": 0.0,
        "mana_flat": 0.0,
        "mana_pct": 0.0,
        "mana_regen_flat": 0.0,
        "armor_flat": 0.0,
        "magic_resist_flat": 0.0,
        "attack_damage_flat": 0.0,
        "attack_speed_flat": 0.0,
        "attack_speed_pct": 0.0,
        "move_speed_flat": 0.0,
        "move_speed_pct": 0.0,
        "attack_range_flat": 0.0,
        "projectile_speed_flat": 0.0,
        "max_hp_regen_pct": 0.0,
        "bat_reduction_pct": 0.0,
    }


def _merge_modifiers(target, source):
    for key in target:
        target[key] += source.get(key, 0.0)


def _normalize_primary_attribute(value):
    lowered = str(value or "").strip().lower()
    mapping = {
        "str": "strength",
        "strength": "strength",
        "agi": "agility",
        "agility": "agility",
        "int": "intelligence",
        "intelligence": "intelligence",
        "uni": "universal",
        "universal": "universal",
    }
    return mapping.get(lowered, "unknown")


def _attack_interval(attack_speed, bat):
    if attack_speed <= 0 or bat <= 0:
        return math.inf
    return (100.0 * bat) / attack_speed


def _effective_attack_animation(base_attack_point, base_attack_backswing, attack_speed, attack_point_manip=0.0):
    if attack_speed <= 0:
        return math.inf, math.inf
    speed_factor = 100.0 / attack_speed
    effective_attack_point = base_attack_point * speed_factor * (1.0 + attack_point_manip)
    effective_attack_backswing = base_attack_backswing * speed_factor
    return effective_attack_point, effective_attack_backswing


def _damage_type_label(value):
    text = str(value or "").strip().lower()
    if text.startswith("phys"):
        return "Physical"
    if text.startswith("mag"):
        return "Magical"
    if text.startswith("pure"):
        return "Pure"
    return "Magical"


def _timeline_time_label(seconds):
    rounded = round(float(seconds), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{int(round(rounded))}s"
    return f"{rounded:.2f}s"


def _clamp(value, low, high):
    return max(low, min(high, value))


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
        self.item_modifier_cache = {}
        self.adjustment_rows = []
        self.stat_value_vars = {key: tk.StringVar(value="") for key in DISPLAY_STAT_ORDER}

        self.hero_names = sorted(self.heroes.keys())
        self.item_names = [""] + sorted(self.items.keys())

        self.hero_var = tk.StringVar(value=self.hero_names[0] if self.hero_names else "")
        self.hero_search_var = tk.StringVar(value="")
        self.hero_filter_status_var = tk.StringVar(value="")
        self.hero_selection_summary_var = tk.StringVar(value="")
        self.level_var = tk.StringVar(value="1")
        self.attribute_bonus_summary_var = tk.StringVar(value="")
        self.inventory_vars = [tk.StringVar(value="") for _ in range(DEFAULT_INVENTORY_SLOTS)]
        self.summary_var = tk.StringVar(value="")
        self.ability_summary_var = tk.StringVar(value="")
        self.simulation_summary_var = tk.StringVar(value="")
        self.target_summary_var = tk.StringVar(value="")

        self.skill_build_vars = [tk.StringVar(value="") for _ in range(MAX_SKILL_BUILD_LEVEL)]
        self.skill_option_map = {}
        self.skill_option_values = []
        self.talent_choice_vars = {tier: tk.StringVar(value="Left") for tier in TALENT_TIERS}
        self.talent_left_text_vars = {tier: tk.StringVar(value="") for tier in TALENT_TIERS}
        self.talent_right_text_vars = {tier: tk.StringVar(value="") for tier in TALENT_TIERS}
        self._syncing_skill_build = False

        self.target_mode_var = tk.StringVar(value=TARGET_MANUAL)
        self.target_hero_var = tk.StringVar(value=self.hero_names[1] if len(self.hero_names) > 1 else (self.hero_names[0] if self.hero_names else ""))
        self.target_level_var = tk.StringVar(value="1")
        self.target_health_var = tk.StringVar(value="1000")
        self.target_armor_var = tk.StringVar(value="0")
        self.target_magic_resist_var = tk.StringVar(value="25")
        self.target_health_regen_var = tk.StringVar(value="0")
        self.timeline_seconds_var = tk.StringVar(value=str(DEFAULT_TIMELINE_SECONDS))

        self.action_time_vars = [tk.StringVar(value=str(index * 2)) for index in range(DEFAULT_ACTION_SLOTS)]
        self.action_choice_vars = [tk.StringVar(value=ACTION_EMPTY) for _ in range(DEFAULT_ACTION_SLOTS)]
        if self.action_choice_vars:
            self.action_choice_vars[0].set(ACTION_AUTO_ATTACK)

        self.current_stats = {}
        self.current_skill_state = {}
        self.current_ability_rows = []
        self.current_simulation = None
        self._widgets_ready = False
        self.hero_picker_window = None
        self.hero_grid_canvas = None
        self.hero_grid_frame = None
        self.hero_picker_image_cache = {}
        self.hero_picker_icon_missing = set()
        self.hero_search_var.trace_add("write", lambda *_: self._refresh_hero_grid())

        self._create_widgets()
        self._update_hero_dependent_options(reset_build=True)
        self._widgets_ready = True
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
        merged = {}
        for key in ("items", "neutrals"):
            items = self.dataset_payload.get(key, {})
            if isinstance(items, dict):
                merged.update(items)
        return merged

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
        ttk.Label(top, textvariable=self.hero_selection_summary_var, font=("Arial", 10, "bold")).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 8),
        )
        ttk.Button(top, text="Choose Hero", command=self._open_hero_picker).grid(row=0, column=2, sticky="w", padx=(0, 18))

        ttk.Label(top, text="Level").grid(row=0, column=3, sticky="w", padx=(0, 6))
        level_spin = ttk.Spinbox(top, from_=1, to=30, textvariable=self.level_var, width=6)
        level_spin.grid(row=0, column=4, sticky="w")

        ttk.Label(top, textvariable=self.attribute_bonus_summary_var, foreground="#666").grid(
            row=1,
            column=0,
            columnspan=6,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Label(top, textvariable=self.summary_var, foreground="#666").grid(
            row=2,
            column=0,
            columnspan=6,
            sticky="w",
            pady=(4, 0),
        )

        self.level_var.trace_add("write", lambda *_: self.recalculate())
        self._update_hero_selector_summary()

        skill_frame = ttk.LabelFrame(content, text="Skill Build Order")
        skill_frame.pack(fill="x", pady=(0, 12))

        skill_header = ttk.Frame(skill_frame)
        skill_header.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(
            skill_header,
            text="Each level can learn an ability or attribute bonus. Talent choices unlock separately by hero level.",
            foreground="#666",
        ).pack(side="left")
        ttk.Button(skill_header, text="Auto Fill To Level", command=self._auto_fill_skill_build).pack(side="right")
        ttk.Button(skill_header, text="Clear", command=self._clear_skill_build).pack(side="right", padx=(0, 8))

        self.skill_build_grid = ttk.Frame(skill_frame)
        self.skill_build_grid.pack(fill="x", padx=8, pady=(0, 8))
        self.skill_build_combos = []
        for index, build_var in enumerate(self.skill_build_vars):
            row = index // 5
            col = (index % 5) * 2
            ttk.Label(self.skill_build_grid, text=f"{index + 1:02d}").grid(
                row=row,
                column=col,
                sticky="e",
                padx=(0, 4),
                pady=3,
            )
            combo = ttk.Combobox(
                self.skill_build_grid,
                textvariable=build_var,
                values=[],
                state="readonly",
                width=26,
            )
            combo.grid(row=row, column=col + 1, sticky="w", padx=(0, 10), pady=3)
            combo.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
            self.skill_build_combos.append(combo)

        talent_frame = ttk.LabelFrame(content, text="Talent Choices")
        talent_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(
            talent_frame,
            text="Selected talents unlock at 10/15/20/25. The unchosen talents unlock at 27/28/29/30.",
            foreground="#666",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4))
        for row_index, tier in enumerate(TALENT_TIERS, start=1):
            ttk.Label(talent_frame, text=f"Level {tier}").grid(row=row_index, column=0, sticky="w", padx=(8, 6), pady=3)
            combo = ttk.Combobox(
                talent_frame,
                textvariable=self.talent_choice_vars[tier],
                values=TALENT_CHOICES,
                state="readonly",
                width=8,
            )
            combo.grid(row=row_index, column=1, sticky="w", padx=(0, 12), pady=3)
            combo.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
            ttk.Label(talent_frame, textvariable=self.talent_left_text_vars[tier], foreground="#555").grid(
                row=row_index,
                column=2,
                sticky="w",
                padx=(0, 12),
                pady=3,
            )
            ttk.Label(talent_frame, textvariable=self.talent_right_text_vars[tier], foreground="#555").grid(
                row=row_index,
                column=3,
                sticky="w",
                padx=(0, 8),
                pady=3,
            )

        abilities_frame = ttk.LabelFrame(content, text="Loaded Abilities")
        abilities_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(abilities_frame, textvariable=self.ability_summary_var, foreground="#666").pack(
            anchor="w",
            padx=8,
            pady=(8, 4),
        )
        self.ability_tree = ttk.Treeview(
            abilities_frame,
            columns=("level", "type", "damage", "cooldown", "mana", "duration", "notes"),
            show="tree headings",
            height=7,
        )
        self.ability_tree.heading("#0", text="Ability")
        self.ability_tree.heading("level", text="Lvl")
        self.ability_tree.heading("type", text="Type")
        self.ability_tree.heading("damage", text="Damage")
        self.ability_tree.heading("cooldown", text="CD")
        self.ability_tree.heading("mana", text="Mana")
        self.ability_tree.heading("duration", text="Duration")
        self.ability_tree.heading("notes", text="Effects")
        self.ability_tree.column("#0", width=190, anchor="w")
        self.ability_tree.column("level", width=45, anchor="center")
        self.ability_tree.column("type", width=70, anchor="center")
        self.ability_tree.column("damage", width=110, anchor="e")
        self.ability_tree.column("cooldown", width=65, anchor="e")
        self.ability_tree.column("mana", width=65, anchor="e")
        self.ability_tree.column("duration", width=80, anchor="e")
        self.ability_tree.column("notes", width=320, anchor="w")
        self.ability_tree.pack(fill="x", padx=8, pady=(0, 8))

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

        lower_level_frame = ttk.Frame(content)
        lower_level_frame.pack(fill="x", pady=(12, 0))
        lower_level_controls = ttk.Frame(lower_level_frame)
        lower_level_controls.pack(anchor="center")
        ttk.Label(lower_level_controls, text="Level").pack(side="left", padx=(0, 6))
        ttk.Spinbox(
            lower_level_controls,
            from_=1,
            to=30,
            textvariable=self.level_var,
            width=6,
        ).pack(side="left")

        simulator_frame = ttk.LabelFrame(content, text="Action Line Simulator")
        simulator_frame.pack(fill="x", pady=(12, 0))

        sim_top = ttk.Frame(simulator_frame)
        sim_top.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(sim_top, text="Duration").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Spinbox(sim_top, from_=1, to=90, textvariable=self.timeline_seconds_var, width=6).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 12),
        )
        ttk.Label(sim_top, text="Target").grid(row=0, column=2, sticky="w", padx=(0, 6))
        target_mode = ttk.Combobox(
            sim_top,
            textvariable=self.target_mode_var,
            values=[TARGET_NONE, TARGET_MANUAL, TARGET_HERO],
            state="readonly",
            width=14,
        )
        target_mode.grid(row=0, column=3, sticky="w", padx=(0, 12))
        ttk.Label(sim_top, text="Hero Target").grid(row=0, column=4, sticky="w", padx=(0, 6))
        target_hero = ttk.Combobox(
            sim_top,
            textvariable=self.target_hero_var,
            values=self.hero_names,
            state="normal",
            width=28,
        )
        target_hero.grid(row=0, column=5, sticky="w", padx=(0, 12))
        ttk.Label(sim_top, text="Lvl").grid(row=0, column=6, sticky="w", padx=(0, 6))
        ttk.Spinbox(sim_top, from_=1, to=30, textvariable=self.target_level_var, width=6).grid(
            row=0,
            column=7,
            sticky="w",
        )

        manual_target = ttk.Frame(simulator_frame)
        manual_target.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(manual_target, text="Manual HP").pack(side="left", padx=(0, 6))
        ttk.Entry(manual_target, textvariable=self.target_health_var, width=10).pack(side="left", padx=(0, 12))
        ttk.Label(manual_target, text="Armor").pack(side="left", padx=(0, 6))
        ttk.Entry(manual_target, textvariable=self.target_armor_var, width=8).pack(side="left", padx=(0, 12))
        ttk.Label(manual_target, text="Magic Res %").pack(side="left", padx=(0, 6))
        ttk.Entry(manual_target, textvariable=self.target_magic_resist_var, width=8).pack(side="left", padx=(0, 12))
        ttk.Label(manual_target, text="HP Regen").pack(side="left", padx=(0, 6))
        ttk.Entry(manual_target, textvariable=self.target_health_regen_var, width=8).pack(side="left", padx=(0, 12))
        ttk.Label(manual_target, textvariable=self.target_summary_var, foreground="#666").pack(side="left")

        action_frame = ttk.Frame(simulator_frame)
        action_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.action_combos = []
        for index in range(DEFAULT_ACTION_SLOTS):
            row = index // 5
            column = (index % 5) * 2
            ttk.Label(action_frame, text=f"{index + 1} @").grid(row=row, column=column, sticky="e", padx=(0, 3), pady=3)
            slot = ttk.Frame(action_frame)
            slot.grid(row=row, column=column + 1, sticky="w", padx=(0, 8), pady=3)
            ttk.Entry(slot, textvariable=self.action_time_vars[index], width=5).pack(side="left")
            combo = ttk.Combobox(
                slot,
                textvariable=self.action_choice_vars[index],
                values=[ACTION_EMPTY, ACTION_AUTO_ATTACK, ACTION_STOP],
                state="readonly",
                width=24,
            )
            combo.pack(side="left", padx=(4, 0))
            combo.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
            self.action_combos.append(combo)

        self.timeline_canvas = tk.Canvas(simulator_frame, height=190, bg="white", highlightthickness=1, highlightbackground="#d0d0d0")
        timeline_scroll = ttk.Scrollbar(simulator_frame, orient="horizontal", command=self.timeline_canvas.xview)
        self.timeline_canvas.configure(xscrollcommand=timeline_scroll.set)
        self.timeline_canvas.pack(fill="x", padx=8, pady=(0, 0))
        timeline_scroll.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(simulator_frame, textvariable=self.simulation_summary_var, foreground="#355070").pack(
            anchor="w",
            padx=8,
            pady=(0, 4),
        )
        self.simulation_log = tk.Text(simulator_frame, height=9, wrap="word")
        self.simulation_log.pack(fill="x", padx=8, pady=(0, 8))
        self.simulation_log.configure(state="disabled")

        target_mode.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
        target_hero.bind("<<ComboboxSelected>>", lambda e: self.recalculate())
        target_hero.bind("<KeyRelease>", lambda e: self._handle_combobox_keyrelease(e, self.target_hero_var, self.hero_names))
        target_hero.bind("<FocusOut>", lambda e: self._normalize_combobox_value(self.target_hero_var, self.hero_names))

        for var in (
            self.target_mode_var,
            self.target_level_var,
            self.target_health_var,
            self.target_armor_var,
            self.target_magic_resist_var,
            self.target_health_regen_var,
            self.timeline_seconds_var,
            *self.action_time_vars,
        ):
            var.trace_add("write", lambda *_: self.recalculate())

    def add_adjustment_row(self):
        row = ManualAdjustmentRow(self.adjustments_container, self.recalculate, self.remove_adjustment_row)
        row.pack(fill="x", pady=4)
        self.adjustment_rows.append(row)
        if self._widgets_ready:
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

    def _resolve_attribute_bonus_points(self, skill_state=None):
        manual_points = 0
        build_points = 0
        if isinstance(skill_state, dict):
            build_points = int(skill_state.get("attribute_bonus_points", 0) or 0)
        total_points = min(MAX_ATTRIBUTE_BONUS_POINTS, build_points)
        return manual_points, build_points, total_points

    def _normalize_combobox_value(self, variable, values, on_exact=None):
        current = variable.get().strip()
        if not current:
            variable.set("")
            self.recalculate()
            return

        exact = next((name for name in values if name.lower() == current.lower()), None)
        if exact is not None:
            variable.set(exact)
            if callable(on_exact):
                on_exact()
            else:
                self.recalculate()

    def _handle_combobox_keyrelease(self, event, variable, values, on_exact=None):
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
                if callable(on_exact):
                    on_exact()
                else:
                    self.recalculate()
                return

        self.recalculate()


    def _clear_hero_search(self):
        self.hero_search_var.set("")

    def _update_hero_selector_summary(self):
        hero_name = self.hero_var.get().strip()
        self.hero_selection_summary_var.set(hero_name or "No hero selected")

    def _open_hero_picker(self):
        if self.hero_picker_window is not None and self.hero_picker_window.winfo_exists():
            self.hero_picker_window.lift()
            self.hero_picker_window.focus_force()
            return

        window = tk.Toplevel(self.parent)
        self.hero_picker_window = window
        window.title("Choose Hero")
        window.geometry("760x620")
        window.minsize(620, 460)
        window.transient(self.parent.winfo_toplevel())
        window.protocol("WM_DELETE_WINDOW", self._close_hero_picker)

        header = ttk.Frame(window, padding=(12, 12, 12, 6))
        header.pack(fill="x")
        ttk.Label(header, text="Search").pack(side="left", padx=(0, 6))
        search_entry = ttk.Entry(header, textvariable=self.hero_search_var, width=34)
        search_entry.pack(side="left", padx=(0, 10))
        search_entry.bind("<Return>", lambda _event: self._select_first_visible_hero())
        ttk.Button(header, text="Clear", command=self._clear_hero_search).pack(side="left", padx=(0, 10))
        ttk.Label(header, textvariable=self.hero_filter_status_var, foreground="#666").pack(side="left")

        grid_outer = ttk.Frame(window, padding=(12, 0, 12, 12))
        grid_outer.pack(fill="both", expand=True)
        self.hero_grid_canvas = tk.Canvas(grid_outer, highlightthickness=1, highlightbackground="#d0d0d0")
        hero_grid_scroll = ttk.Scrollbar(grid_outer, orient="vertical", command=self.hero_grid_canvas.yview)
        self.hero_grid_frame = ttk.Frame(self.hero_grid_canvas)
        self.hero_grid_frame.bind(
            "<Configure>",
            lambda _event: self.hero_grid_canvas.configure(scrollregion=self.hero_grid_canvas.bbox("all")),
        )
        self.hero_grid_canvas.create_window((0, 0), window=self.hero_grid_frame, anchor="nw")
        self.hero_grid_canvas.configure(yscrollcommand=hero_grid_scroll.set)
        self.hero_grid_canvas.pack(side="left", fill="both", expand=True)
        hero_grid_scroll.pack(side="right", fill="y")

        search_entry.focus_set()
        self._refresh_hero_grid()
        try:
            window.grab_set()
        except tk.TclError:
            pass

    def _close_hero_picker(self):
        if self.hero_picker_window is not None and self.hero_picker_window.winfo_exists():
            try:
                self.hero_picker_window.grab_release()
            except tk.TclError:
                pass
            self.hero_picker_window.destroy()
        self.hero_picker_window = None
        self.hero_grid_canvas = None
        self.hero_grid_frame = None

    def _compact_search_text(self, text):
        return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())

    def _hero_initials(self, hero_name):
        words = re.findall(r"[A-Za-z0-9]+", str(hero_name or ""))
        return "".join(word[0].lower() for word in words if word)

    def _hero_search_score(self, hero_name, query):
        query_text = str(query or "").strip().lower()
        if not query_text:
            return 1.0

        hero_text = str(hero_name or "").strip().lower()
        query_compact = self._compact_search_text(query_text)
        hero_compact = self._compact_search_text(hero_text)
        initials = self._hero_initials(hero_name)
        query_tokens = [token for token in re.split(r"\s+", query_text) if token]

        if hero_text == query_text or hero_compact == query_compact:
            return 10.0
        if hero_text.startswith(query_text):
            return 9.0
        if hero_compact.startswith(query_compact):
            return 8.5
        if query_compact and initials.startswith(query_compact):
            return 8.25
        if query_text in hero_text:
            return 8.0
        if query_compact and query_compact in hero_compact:
            return 7.5
        if query_tokens and all(token in hero_text for token in query_tokens):
            return 6.5

        return max(
            SequenceMatcher(None, query_text, hero_text).ratio(),
            SequenceMatcher(None, query_compact, hero_compact).ratio(),
        )

    def _filtered_hero_names(self):
        query = self.hero_search_var.get().strip()
        if not query:
            return list(self.hero_names), len(self.hero_names)

        scored = [
            (self._hero_search_score(hero_name, query), hero_name)
            for hero_name in self.hero_names
        ]
        matches = [
            (score, hero_name)
            for score, hero_name in scored
            if score >= 0.34
        ]
        matches.sort(key=lambda item: (-item[0], item[1]))
        hero_names = [hero_name for _score, hero_name in matches]
        return hero_names[:HERO_SEARCH_RESULT_LIMIT], len(hero_names)

    def _refresh_hero_grid(self):
        if self.hero_grid_frame is None or self.hero_grid_canvas is None:
            return

        for child in self.hero_grid_frame.winfo_children():
            child.destroy()

        visible_heroes, total_matches = self._filtered_hero_names()
        for index, hero_name in enumerate(visible_heroes):
            row = index // HERO_GRID_COLUMNS
            column = index % HERO_GRID_COLUMNS
            button_host = tk.Frame(
                self.hero_grid_frame,
                width=HERO_PICKER_BUTTON_PIXEL_WIDTH,
                height=HERO_PICKER_BUTTON_PIXEL_HEIGHT,
                bd=0,
                highlightthickness=0,
            )
            button_host.grid_propagate(False)
            button_host.grid(row=row, column=column, sticky="w", padx=0, pady=0)
            button = tk.Button(
                button_host,
                wraplength=HERO_PICKER_BUTTON_WRAP,
                justify="center",
                padx=0,
                pady=0,
                font=("Arial", 9),
                borderwidth=1,
                highlightthickness=0,
                command=lambda selected_hero=hero_name: self._select_hero_from_picker(selected_hero),
            )
            button.place(x=0, y=0, relwidth=1, relheight=1)
            self._apply_hero_picker_button_visual(button, hero_name)

        for column in range(HERO_GRID_COLUMNS):
            self.hero_grid_frame.columnconfigure(column, weight=0)

        if not visible_heroes:
            ttk.Label(self.hero_grid_frame, text="No heroes matched.").grid(row=0, column=0, sticky="w", padx=4, pady=4)

        if self.hero_search_var.get().strip():
            if total_matches > len(visible_heroes):
                status = f"{len(visible_heroes)} of {total_matches} matches"
            else:
                status = f"{total_matches} matches"
        else:
            status = f"{len(self.hero_names)} heroes"
        selected = self.hero_var.get().strip()
        if selected:
            status = f"{status} | Selected: {selected}"
        self.hero_filter_status_var.set(status)

        self.hero_grid_canvas.yview_moveto(0)

    def _select_first_visible_hero(self):
        visible_heroes, _total_matches = self._filtered_hero_names()
        if visible_heroes:
            self._select_hero_from_picker(visible_heroes[0])

    def _hero_picker_icon_path(self, hero_name):
        filename = f"{str(hero_name).replace(' ', '_')}_icon_dota2_gameasset.png"
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "hero-icons", filename)
        if os.path.exists(icon_path):
            return icon_path
        return None

    def _center_crop_photoimage(self, source_image, target_width, target_height):
        source_width = int(source_image.width())
        source_height = int(source_image.height())
        subsample_factor = max(
            1,
            min(
                max(1, source_width // max(1, int(target_width))),
                max(1, source_height // max(1, int(target_height))),
            ),
        )
        working_image = (
            source_image.subsample(subsample_factor, subsample_factor)
            if subsample_factor > 1
            else source_image
        )

        source_width = int(working_image.width())
        source_height = int(working_image.height())
        copy_width = min(source_width, int(target_width))
        copy_height = min(source_height, int(target_height))

        source_x0 = max(0, (source_width - copy_width) // 2)
        source_y0 = max(0, (source_height - copy_height) // 2)
        source_x1 = source_x0 + copy_width
        source_y1 = source_y0 + copy_height

        target_x = max(0, (int(target_width) - copy_width) // 2)
        target_y = max(0, (int(target_height) - copy_height) // 2)

        cropped_image = tk.PhotoImage(
            master=self.parent.winfo_toplevel(),
            width=target_width,
            height=target_height,
        )
        cropped_image.tk.call(
            str(cropped_image),
            "copy",
            str(working_image),
            "-from",
            source_x0,
            source_y0,
            source_x1,
            source_y1,
            "-to",
            target_x,
            target_y,
        )
        return cropped_image

    def _get_hero_picker_image(self, hero_name):
        cached_image = self.hero_picker_image_cache.get(hero_name)
        if cached_image is not None:
            return cached_image
        if hero_name in self.hero_picker_icon_missing:
            return None

        icon_path = self._hero_picker_icon_path(hero_name)
        if not icon_path:
            self.hero_picker_icon_missing.add(hero_name)
            return None

        try:
            source_image = tk.PhotoImage(master=self.parent.winfo_toplevel(), file=icon_path)
            image = self._center_crop_photoimage(
                source_image,
                HERO_PICKER_BUTTON_PIXEL_WIDTH,
                HERO_PICKER_BUTTON_PIXEL_HEIGHT,
            )
        except tk.TclError:
            self.hero_picker_icon_missing.add(hero_name)
            return None

        self.hero_picker_image_cache[hero_name] = image
        return image

    def _apply_hero_picker_button_visual(self, button, hero_name):
        selected = hero_name == self.hero_var.get().strip()
        bg = "#0f7c46" if selected else "#1f1f1f"
        active_bg = "#18b866" if selected else "#2c2c2c"
        fg = "#f4fff8" if selected else "#ffffff"
        button.configure(
            text=hero_name,
            bg=bg,
            activebackground=active_bg,
            fg=fg,
            activeforeground=fg,
            disabledforeground=fg,
        )

        image = self._get_hero_picker_image(hero_name)
        if image is not None:
            button.configure(image=image, compound="center")
            button.image = image
        else:
            button.configure(image="", compound="none")
            button.image = None

    def _select_hero_from_picker(self, hero_name):
        self.hero_var.set(hero_name)
        self._update_hero_selector_summary()
        self._close_hero_picker()
        self._on_hero_changed()

    def _on_hero_changed(self):
        self._update_hero_selector_summary()
        self._update_hero_dependent_options(reset_build=True)
        self.recalculate()

    def _selected_hero_data(self):
        hero_name = self.hero_var.get().strip()
        return hero_name, self.heroes.get(hero_name, {})

    def _hero_abilities(self, hero_data=None):
        if hero_data is None:
            _name, hero_data = self._selected_hero_data()
        abilities = hero_data.get("abilities", [])
        return abilities if isinstance(abilities, list) else []

    def _ability_max_level(self, ability):
        max_level = 1
        for payload in (ability.get("values", {}),):
            if not isinstance(payload, dict):
                continue
            for entries in payload.values():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    values = entry.get("values")
                    if isinstance(values, list) and values:
                        max_level = max(max_level, len(values))
        return max(1, min(10, max_level))

    def _ability_slot_label(self, index):
        labels = ("Q", "W", "E", "R", "D", "F", "Innate", "Extra")
        if index < len(labels):
            return labels[index]
        return str(index + 1)

    def _build_skill_option_records(self, hero_data):
        records = []
        for index, ability in enumerate(self._hero_abilities(hero_data)):
            name = str(ability.get("name") or f"Ability {index + 1}").strip()
            if not name:
                continue
            label = f"{self._ability_slot_label(index)}: {name}"
            records.append({"label": label, "kind": "ability", "index": index})

        records.append({"label": "Attribute Bonus (+2 all)", "kind": "attribute_bonus"})
        return records

    def _talent_text(self, hero_data, tier, side):
        talents = hero_data.get("talents", {})
        if not isinstance(talents, dict):
            return ""
        tier_payload = talents.get(tier, {})
        if not isinstance(tier_payload, dict):
            return ""
        return str(tier_payload.get(side, "") or "").strip()

    def _refresh_talent_texts(self, hero_data):
        for tier in TALENT_TIERS:
            left_text = self._talent_text(hero_data, tier, "left")
            right_text = self._talent_text(hero_data, tier, "right")
            self.talent_left_text_vars[tier].set(f"L: {left_text}" if left_text else "L: -")
            self.talent_right_text_vars[tier].set(f"R: {right_text}" if right_text else "R: -")

    def _update_hero_dependent_options(self, reset_build=False):
        _hero_name, hero_data = self._selected_hero_data()
        records = self._build_skill_option_records(hero_data)
        self.skill_option_map = {record["label"]: record for record in records}
        self.skill_option_values = [""] + [record["label"] for record in records]
        for combo in getattr(self, "skill_build_combos", []):
            combo["values"] = self.skill_option_values
        self._refresh_talent_texts(hero_data)

        action_values = [ACTION_EMPTY, ACTION_AUTO_ATTACK, ACTION_STOP]
        self.action_option_map = {}
        for index, ability in enumerate(self._hero_abilities(hero_data)):
            if str(ability.get("type", "")).strip().lower() != "active":
                continue
            label = f"Cast: {ability.get('name')}"
            action_values.append(label)
            self.action_option_map[label] = {"kind": "ability", "index": index}
        for combo in getattr(self, "action_combos", []):
            combo["values"] = action_values

        if reset_build:
            self._auto_fill_skill_build(recalculate=False)
            for action_var in self.action_choice_vars:
                if action_var.get() not in action_values:
                    action_var.set(ACTION_EMPTY)

    def _clear_skill_build(self):
        self._syncing_skill_build = True
        for build_var in self.skill_build_vars:
            build_var.set("")
        self._syncing_skill_build = False
        self.recalculate()

    def _auto_fill_skill_build(self, recalculate=True):
        _hero_name, hero_data = self._selected_hero_data()
        abilities = self._hero_abilities(hero_data)
        ability_labels = []
        for index, ability in enumerate(abilities):
            if self._ability_max_level(ability) <= 1:
                continue
            label = f"{self._ability_slot_label(index)}: {ability.get('name')}"
            if label in self.skill_option_map:
                ability_labels.append(label)

        learned = {label: 0 for label in ability_labels}
        max_by_label = {}
        for label in ability_labels:
            record = self.skill_option_map[label]
            max_by_label[label] = self._ability_max_level(abilities[record["index"]])

        self._syncing_skill_build = True
        for build_var in self.skill_build_vars:
            build_var.set("")

        cursor = 0
        for level_index in range(self._parse_level()):
            chosen = ""
            if ability_labels:
                for _ in range(len(ability_labels)):
                    candidate = ability_labels[cursor % len(ability_labels)]
                    cursor += 1
                    if learned[candidate] < max_by_label[candidate]:
                        chosen = candidate
                        learned[candidate] += 1
                        break
            if not chosen:
                chosen = "Attribute Bonus (+2 all)"
            self.skill_build_vars[level_index].set(chosen)
        self._syncing_skill_build = False

        if recalculate:
            self.recalculate()

    def _active_talent_sides_for_tier(self, tier, level):
        if int(level) < int(tier):
            return []

        choice = self.talent_choice_vars[tier].get().strip().lower()
        if choice not in {"left", "right"}:
            return []

        sides = [choice]
        if int(level) >= TALENT_EXTRA_UNLOCK_LEVELS[tier]:
            sides.append("right" if choice == "left" else "left")
        return sides

    def _get_active_talents(self, hero_data, level):
        selected_talent_ids = set()
        selected_talent_labels = []

        for tier in TALENT_TIERS:
            for side in self._active_talent_sides_for_tier(tier, level):
                selected_talent_ids.add(f"{tier}_{side}")
                text = self._talent_text(hero_data, tier, side)
                if text:
                    selected_talent_labels.append(text)

        return selected_talent_ids, selected_talent_labels

    def _get_skill_build_state(self, hero_data=None, level=None):
        if hero_data is None:
            _hero_name, hero_data = self._selected_hero_data()
        if level is None:
            level = self._parse_level()
        abilities = self._hero_abilities(hero_data)
        ability_levels = [0 for _ in abilities]
        max_levels = [self._ability_max_level(ability) for ability in abilities]
        selected_talent_ids, selected_talent_labels = self._get_active_talents(hero_data, int(level))
        attribute_bonus_points = 0

        for build_var in self.skill_build_vars[:max(0, min(MAX_SKILL_BUILD_LEVEL, int(level)))]:
            record = self.skill_option_map.get(build_var.get())
            if not record:
                continue
            kind = record.get("kind")
            if kind == "ability":
                index = int(record["index"])
                if 0 <= index < len(ability_levels) and ability_levels[index] < max_levels[index]:
                    ability_levels[index] += 1
            elif kind == "attribute_bonus":
                attribute_bonus_points += 1

        return {
            "ability_levels": ability_levels,
            "selected_talent_ids": selected_talent_ids,
            "selected_talent_labels": selected_talent_labels,
            "attribute_bonus_points": min(MAX_ATTRIBUTE_BONUS_POINTS, attribute_bonus_points),
        }

    def _selected_item_names(self):
        item_names = []
        for slot_var in self.inventory_vars:
            name = slot_var.get().strip()
            if name and name in self.items:
                item_names.append(name)
        return item_names

    def _collect_item_modifiers_from_names(self, item_names):
        modifiers = _empty_modifiers()
        selected_items = []
        for item_name in item_names:
            if item_name not in self.items:
                continue
            selected_items.append(item_name)
            _merge_modifiers(modifiers, self._get_item_modifiers(item_name))
        return modifiers, selected_items

    def _get_item_modifiers(self, item_name):
        if item_name in self.item_modifier_cache:
            fresh = _empty_modifiers()
            _merge_modifiers(fresh, self.item_modifier_cache[item_name])
            return fresh

        item_data = self.items.get(item_name, {})
        modifiers = _empty_modifiers()
        stats_payload = item_data.get("stats")
        has_explicit_stats = False
        if isinstance(stats_payload, dict):
            for stat_name, stat_value in stats_payload.items():
                if self._apply_named_stat_bonus(modifiers, stat_name, stat_value):
                    has_explicit_stats = True

        if not has_explicit_stats:
            _merge_modifiers(modifiers, self._parse_item_passive_bonuses(item_data))
            if not self._modifiers_have_value(modifiers):
                self._merge_recipe_modifiers(modifiers, item_data.get("recipe"), seen={item_name})

        self.item_modifier_cache[item_name] = modifiers
        fresh = _empty_modifiers()
        _merge_modifiers(fresh, modifiers)
        return fresh

    def _merge_recipe_modifiers(self, modifiers, recipe_payload, seen):
        if not isinstance(recipe_payload, list):
            return
        for recipe_item_name in recipe_payload:
            if recipe_item_name in seen or recipe_item_name not in self.items:
                continue
            seen.add(recipe_item_name)
            _merge_modifiers(modifiers, self._get_item_modifiers(recipe_item_name))

    def _apply_named_stat_bonus(self, modifiers, stat_name, stat_value):
        value, is_percent = _first_numeric_value(stat_value)
        if value is None:
            return False

        normalized_name = str(stat_name or "").strip().lower()
        normalized_name = normalized_name.replace("+", "").replace("  ", " ")

        if normalized_name in {"strength", "bonus strength"}:
            modifiers["strength"] += value
            return True
        if normalized_name in {"agility", "bonus agility"}:
            modifiers["agility"] += value
            return True
        if normalized_name in {"intelligence", "bonus intelligence"}:
            modifiers["intelligence"] += value
            return True
        if normalized_name in {"all attributes", "attributes"}:
            modifiers["strength"] += value
            modifiers["agility"] += value
            modifiers["intelligence"] += value
            return True
        if normalized_name in {"health", "bonus health"}:
            if is_percent:
                modifiers["health_pct"] += value / 100.0
            else:
                modifiers["health_flat"] += value
            return True
        if normalized_name in {"mana", "bonus mana"}:
            if is_percent:
                modifiers["mana_pct"] += value / 100.0
            else:
                modifiers["mana_flat"] += value
            return True
        if normalized_name in {"health regeneration", "health regen"}:
            modifiers["health_regen_flat"] += value
            return True
        if normalized_name in {"mana regeneration", "mana regen", "bonus mana regeneration"}:
            modifiers["mana_regen_flat"] += value
            return True
        if normalized_name in {"armor", "bonus armor"}:
            modifiers["armor_flat"] += value
            return True
        if normalized_name in {"magic resistance", "bonus magic resistance"}:
            modifiers["magic_resist_flat"] += value
            return True
        if normalized_name in {"attack damage", "bonus attack damage"}:
            modifiers["attack_damage_flat"] += value
            return True
        if normalized_name in {"attack speed"}:
            if is_percent:
                modifiers["attack_speed_pct"] += value / 100.0
            else:
                modifiers["attack_speed_flat"] += value
            return True
        if normalized_name in {"base attack speed"}:
            modifiers["attack_speed_pct"] += value / 100.0
            return True
        if normalized_name in {"move speed", "bonus move speed"}:
            if is_percent:
                modifiers["move_speed_pct"] += value / 100.0
            else:
                modifiers["move_speed_flat"] += value
            return True
        if normalized_name == "attack range":
            modifiers["attack_range_flat"] += value
            return True
        if normalized_name == "projectile speed":
            modifiers["projectile_speed_flat"] += value
            return True
        if normalized_name == "max hp health regen":
            modifiers["max_hp_regen_pct"] += value / 100.0
            return True
        return False

    def _parse_item_passive_bonuses(self, item_data):
        modifiers = _empty_modifiers()
        abilities = item_data.get("abilities", [])
        if not isinstance(abilities, list):
            return modifiers

        for ability in abilities:
            if not isinstance(ability, dict):
                continue
            if str(ability.get("type", "")).strip().lower() != "passive":
                continue
            description = str(ability.get("description", "") or "").strip()
            if not description:
                continue
            if description.startswith("+"):
                for value_text, label in re.findall(
                    r"([+-]\d+(?:\.\d+)?%?)\s+([A-Za-z][A-Za-z ]+?)(?=(?:\s+[+-]\d)|[.;]|$)",
                    description,
                ):
                    self._apply_named_stat_bonus(modifiers, label.strip(), value_text)
                continue

            for label, modifier_key, as_percent in (
                ("Armor Bonus", "armor_flat", False),
                ("Attack Speed Bonus", "attack_speed_flat", False),
                ("Mana Regeneration Bonus", "mana_regen_flat", False),
                ("Health Regeneration Bonus", "health_regen_flat", False),
                ("Move Speed Bonus", "move_speed_pct", True),
                ("Agility Bonus", "agility", False),
                ("Strength Bonus", "strength", False),
                ("Intelligence Bonus", "intelligence", False),
                ("Attack Range Bonus", "attack_range_flat", False),
            ):
                for match in re.finditer(
                    rf"{re.escape(label)}:\s*([+-]?\d+(?:\.\d+)?)%?",
                    description,
                    flags=re.IGNORECASE,
                ):
                    value = _to_float(match.group(1), default=None)
                    if value is None:
                        continue
                    if as_percent:
                        modifiers[modifier_key] += value / 100.0
                    else:
                        modifiers[modifier_key] += value
        return modifiers

    def _modifiers_have_value(self, modifiers):
        return any(abs(value) > 1e-9 for value in modifiers.values())

    def _collect_skill_talent_modifiers(self, hero_data, skill_state):
        modifiers = _empty_modifiers()
        applied_labels = []
        talents = hero_data.get("talents", {})
        if not isinstance(talents, dict):
            return modifiers, applied_labels

        selected_ids = skill_state.get("selected_talent_ids", set())
        for tier in TALENT_TIERS:
            tier_payload = talents.get(tier, {})
            if not isinstance(tier_payload, dict):
                continue
            for side in ("left", "right"):
                talent_id = f"{tier}_{side}"
                if talent_id not in selected_ids:
                    continue
                label = str(tier_payload.get(side, "") or "").strip()
                talent_modifiers, parsed_text = self._parse_talent_stat_bonus(label)
                if self._modifiers_have_value(talent_modifiers):
                    _merge_modifiers(modifiers, talent_modifiers)
                    applied_labels.append(parsed_text or label)
        return modifiers, applied_labels

    def _parse_talent_stat_bonus(self, label):
        modifiers = _empty_modifiers()
        text = str(label or "").strip()
        if not text:
            return modifiers, ""

        match = re.match(r"^([+-])\s*(\d+(?:\.\d+)?)(%?)\s*(.+)$", text)
        if not match:
            return modifiers, ""

        sign = -1.0 if match.group(1) == "-" else 1.0
        value = sign * _to_float(match.group(2))
        is_percent = bool(match.group(3))
        remainder = match.group(4).strip().lower()

        if "all attributes" in remainder:
            modifiers["strength"] += value
            modifiers["agility"] += value
            modifiers["intelligence"] += value
            return modifiers, text
        if "health regen" in remainder or "health regeneration" in remainder:
            modifiers["health_regen_flat"] += value
            return modifiers, text
        if "mana regen" in remainder or "mana regeneration" in remainder:
            modifiers["mana_regen_flat"] += value
            return modifiers, text
        if "attack speed" in remainder:
            modifiers["attack_speed_flat"] += value
            return modifiers, text
        if "attack damage" in remainder:
            modifiers["attack_damage_flat"] += value
            return modifiers, text
        if "move speed" in remainder and "slow" not in remainder:
            if is_percent:
                modifiers["move_speed_pct"] += value / 100.0
            else:
                modifiers["move_speed_flat"] += value
            return modifiers, text
        if "magic resistance" in remainder and "reduction" not in remainder:
            modifiers["magic_resist_flat"] += value
            return modifiers, text
        if "armor" in remainder and "reduction" not in remainder and "reduced" not in remainder and "steal" not in remainder:
            modifiers["armor_flat"] += value
            return modifiers, text
        if "strength" in remainder and "damage" not in remainder:
            modifiers["strength"] += value
            return modifiers, text
        if "agility" in remainder and "damage" not in remainder:
            modifiers["agility"] += value
            return modifiers, text
        if "intelligence" in remainder and "damage" not in remainder:
            modifiers["intelligence"] += value
            return modifiers, text
        if "attack range" in remainder:
            modifiers["attack_range_flat"] += value
            return modifiers, text
        if remainder in {"health", "hp"} or remainder.startswith("health "):
            if is_percent:
                modifiers["health_pct"] += value / 100.0
            else:
                modifiers["health_flat"] += value
            return modifiers, text
        if remainder in {"mana"} or remainder.startswith("mana "):
            if is_percent:
                modifiers["mana_pct"] += value / 100.0
            else:
                modifiers["mana_flat"] += value
            return modifiers, text
        return modifiers, ""

    def _infer_primary_attribute(self, hero_name, hero_data):
        explicit_candidates = [
            hero_data.get("primaryAttribute"),
            hero_data.get("primary_attribute"),
            hero_data.get("attribute_type"),
        ]
        for candidate in explicit_candidates:
            normalized = _normalize_primary_attribute(candidate)
            if normalized != "unknown":
                return normalized

        gains = hero_data.get("attributeGains", {})
        ranked = sorted(
            [
                ("strength", _to_float(gains.get("strength"))),
                ("agility", _to_float(gains.get("agility"))),
                ("intelligence", _to_float(gains.get("intelligence"))),
            ],
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        return ranked[0][0] if ranked and ranked[0][1] > 0 else "unknown"

    def _base_attack_damage_gain(self, hero_data, primary_attribute):
        stat_gains = hero_data.get("statGains", {})
        explicit_gain = stat_gains.get("mainAttackDamage")
        if explicit_gain is not None:
            return _to_float(explicit_gain)
        attribute_gains = hero_data.get("attributeGains", {})
        if primary_attribute == "strength":
            return _to_float(attribute_gains.get("strength"))
        if primary_attribute == "agility":
            return _to_float(attribute_gains.get("agility"))
        if primary_attribute == "intelligence":
            return _to_float(attribute_gains.get("intelligence"))
        if primary_attribute == "universal":
            return 0.45 * (
                _to_float(attribute_gains.get("strength"))
                + _to_float(attribute_gains.get("agility"))
                + _to_float(attribute_gains.get("intelligence"))
            )
        return 0.0

    def _bonus_attribute_damage(self, primary_attribute, modifiers):
        if primary_attribute == "strength":
            return modifiers["strength"]
        if primary_attribute == "agility":
            return modifiers["agility"]
        if primary_attribute == "intelligence":
            return modifiers["intelligence"]
        if primary_attribute == "universal":
            return 0.45 * (modifiers["strength"] + modifiers["agility"] + modifiers["intelligence"])
        return 0.0

    def _compute_stats_for(self, hero_name, hero_data, level, item_names=None, skill_state=None, apply_adjustments=False):
        item_names = item_names if item_names is not None else []
        skill_state = skill_state if isinstance(skill_state, dict) else {
            "selected_talent_ids": set(),
            "attribute_bonus_points": 0,
        }
        stats_payload = hero_data.get("stats", {})
        attributes = hero_data.get("attributes", {})
        attribute_gains = hero_data.get("attributeGains", {})
        stat_gains = hero_data.get("statGains", {})
        primary_attribute = self._infer_primary_attribute(hero_name, hero_data)
        level_factor = max(0, int(level) - 1)

        item_modifiers, selected_items = self._collect_item_modifiers_from_names(item_names)
        talent_modifiers, applied_talent_labels = self._collect_skill_talent_modifiers(hero_data, skill_state)

        total_modifiers = _empty_modifiers()
        _merge_modifiers(total_modifiers, item_modifiers)
        _merge_modifiers(total_modifiers, talent_modifiers)

        manual_attribute_points, build_attribute_points, total_attribute_points = self._resolve_attribute_bonus_points(skill_state)
        attribute_bonus_total = total_attribute_points * ATTRIBUTE_BONUS_PER_POINT
        total_modifiers["strength"] += attribute_bonus_total
        total_modifiers["agility"] += attribute_bonus_total
        total_modifiers["intelligence"] += attribute_bonus_total

        strength_base = _to_float(attributes.get("strength"))
        agility_base = _to_float(attributes.get("agility"))
        intelligence_base = _to_float(attributes.get("intelligence"))
        strength_gain = _to_float(attribute_gains.get("strength"))
        agility_gain = _to_float(attribute_gains.get("agility"))
        intelligence_gain = _to_float(attribute_gains.get("intelligence"))

        strength = strength_base + (strength_gain * level_factor) + total_modifiers["strength"]
        agility = agility_base + (agility_gain * level_factor) + total_modifiers["agility"]
        intelligence = intelligence_base + (intelligence_gain * level_factor) + total_modifiers["intelligence"]

        health = _to_float(stats_payload.get("health")) + (_to_float(stat_gains.get("health")) * level_factor)
        health += 22.0 * total_modifiers["strength"] + total_modifiers["health_flat"]
        if total_modifiers["health_pct"]:
            health *= max(0.0, 1 + total_modifiers["health_pct"])

        health_regen = _to_float(stats_payload.get("healthRegen")) + (_to_float(stat_gains.get("healthRegen")) * level_factor)
        health_regen += 0.1 * total_modifiers["strength"] + total_modifiers["health_regen_flat"]
        if total_modifiers["max_hp_regen_pct"]:
            health_regen += health * total_modifiers["max_hp_regen_pct"]

        mana = _to_float(stats_payload.get("mana")) + (_to_float(stat_gains.get("mana")) * level_factor)
        mana += 12.0 * total_modifiers["intelligence"] + total_modifiers["mana_flat"]
        if total_modifiers["mana_pct"]:
            mana *= max(0.0, 1 + total_modifiers["mana_pct"])

        mana_regen = _to_float(stats_payload.get("manaRegen")) + (_to_float(stat_gains.get("manaRegen")) * level_factor)
        mana_regen += 0.05 * total_modifiers["intelligence"] + total_modifiers["mana_regen_flat"]

        armor = _to_float(stats_payload.get("armor")) + (_to_float(stat_gains.get("armor")) * level_factor)
        armor += total_modifiers["agility"] / 6.0 + total_modifiers["armor_flat"]

        magic_resist = _to_float(stats_payload.get("magicResistance")) + (_to_float(stat_gains.get("magicResistance")) * level_factor)
        magic_resist += total_modifiers["magic_resist_flat"]

        base_damage_gain = self._base_attack_damage_gain(hero_data, primary_attribute) * level_factor
        attribute_damage_bonus = self._bonus_attribute_damage(primary_attribute, total_modifiers)
        base_damage = _to_float(stats_payload.get("damageAverage")) + base_damage_gain + attribute_damage_bonus
        bonus_attack_damage = total_modifiers["attack_damage_flat"]
        total_attack_damage = base_damage + bonus_attack_damage

        attack_speed = _to_float(stats_payload.get("totalAttackSpeed", stats_payload.get("attackSpeed")))
        attack_speed += _to_float(stat_gains.get("attackSpeed")) * level_factor
        attack_speed += total_modifiers["agility"] + total_modifiers["attack_speed_flat"]
        if total_modifiers["attack_speed_pct"]:
            attack_speed *= max(0.0, 1 + total_modifiers["attack_speed_pct"])

        move_speed = _to_float(stats_payload.get("moveSpeed")) + total_modifiers["move_speed_flat"]
        if total_modifiers["move_speed_pct"]:
            move_speed *= max(0.0, 1 + total_modifiers["move_speed_pct"])

        base_attack_time = _to_float(stats_payload.get("bat"))
        if total_modifiers["bat_reduction_pct"]:
            base_attack_time *= max(0.05, 1 - min(0.95, max(0.0, total_modifiers["bat_reduction_pct"])))

        animation_point = _to_float(stats_payload.get("animationPoint"), default=0.0)
        animation_backswing = _to_float(stats_payload.get("animationBackswing"), default=0.0)
        attack_interval = _attack_interval(attack_speed, base_attack_time)
        attacks_per_second = 0.0 if math.isinf(attack_interval) else 1.0 / attack_interval
        effective_attack_point, effective_attack_backswing = _effective_attack_animation(
            animation_point,
            animation_backswing,
            attack_speed,
        )

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
            "attacks_per_second": attacks_per_second,
            "attack_interval": attack_interval,
            "attack_range": _to_float(stats_payload.get("attackRange")) + total_modifiers["attack_range_flat"],
            "projectile_speed": stats_payload.get("projectileSpeed", ""),
            "turn_rate": _to_float(stats_payload.get("turnRate")),
            "animation": (
                f"{_format_number(effective_attack_point)}s / {_format_number(effective_attack_backswing)}s "
                f"(base {_format_number(animation_point)}s / {_format_number(animation_backswing)}s)"
            ),
            "animation_point": animation_point,
            "animation_backswing": animation_backswing,
            "effective_attack_point": effective_attack_point,
            "effective_attack_backswing": effective_attack_backswing,
            "attack_point_manip": 0.0,
            "primary_attribute": primary_attribute,
            "selected_items": selected_items,
            "applied_talent_labels": applied_talent_labels,
            "attribute_bonus": {
                "manual": manual_attribute_points,
                "build": build_attribute_points,
                "total": total_attribute_points,
                "flat": attribute_bonus_total,
            },
        }

        if apply_adjustments:
            self._apply_manual_adjustments(stats, primary_attribute)

        stats["attack_interval"] = _attack_interval(_to_float(stats["attack_speed"]), _to_float(stats["base_attack_time"]))
        stats["attacks_per_second"] = 0.0 if math.isinf(stats["attack_interval"]) else 1.0 / stats["attack_interval"]
        stats["effective_attack_point"], stats["effective_attack_backswing"] = _effective_attack_animation(
            _to_float(stats.get("animation_point"), default=0.0),
            _to_float(stats.get("animation_backswing"), default=0.0),
            _to_float(stats.get("attack_speed"), default=0.0),
            _to_float(stats.get("attack_point_manip"), default=0.0),
        )
        stats["animation"] = (
            f"{_format_number(stats['effective_attack_point'])}s / {_format_number(stats['effective_attack_backswing'])}s "
            f"(base {_format_number(stats['animation_point'])}s / {_format_number(stats['animation_backswing'])}s)"
        )
        return stats

    def _apply_manual_adjustments(self, stats, primary_attribute):
        base_stats = dict(stats)
        for row in self.adjustment_rows:
            adjustment = row.apply(stats)
            if not adjustment:
                continue
            stat_name = adjustment["stat_name"]
            current = stats.get(stat_name)
            if isinstance(current, str) or current is None:
                continue
            stats[stat_name] = _apply_operation(current, adjustment["operation"], adjustment["value"])

        strength_delta = stats["strength"] - base_stats["strength"]
        agility_delta = stats["agility"] - base_stats["agility"]
        intelligence_delta = stats["intelligence"] - base_stats["intelligence"]

        if strength_delta:
            stats["health"] += 22.0 * strength_delta
            stats["health_regen"] += 0.1 * strength_delta
        if agility_delta:
            stats["attack_speed"] += agility_delta
            stats["armor"] += agility_delta / 6.0
        if intelligence_delta:
            stats["mana"] += 12.0 * intelligence_delta
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
        stats["base_damage"] += attribute_damage_delta
        stats["total_attack_damage"] = stats["base_damage"] + stats["bonus_attack_damage"]

    def _calculate_stats(self):
        hero_name, hero_data = self._selected_hero_data()
        level = self._parse_level()
        skill_state = self._get_skill_build_state(hero_data, level)
        selected_items = self._selected_item_names()
        stats = self._compute_stats_for(
            hero_name,
            hero_data,
            level,
            item_names=selected_items,
            skill_state=skill_state,
            apply_adjustments=True,
        )

        attribute_summary = stats.get("attribute_bonus", {})
        self.attribute_bonus_summary_var.set(
            f"Attribute bonus: {attribute_summary.get('total', 0)}/{MAX_ATTRIBUTE_BONUS_POINTS} level-slot points "
            f"(+{attribute_summary.get('flat', 0)} to each stat)"
        )
        item_summary = ", ".join(stats["selected_items"]) if stats["selected_items"] else "No items selected"
        talent_summary = ", ".join(stats["applied_talent_labels"]) if stats["applied_talent_labels"] else "No stat talents applied"
        self.summary_var.set(f"Level {level} | {item_summary} | {talent_summary}")
        self.current_skill_state = skill_state
        return stats

    def recalculate(self, *_args):
        if getattr(self, "_syncing_skill_build", False):
            return
        stats = self._calculate_stats()
        self.current_stats = stats
        for key, var in self.stat_value_vars.items():
            value = stats.get(key, "")
            var.set("Inf" if isinstance(value, float) and math.isinf(value) else _format_number(value))
        if self._widgets_ready:
            self._refresh_ability_tree()
            self._refresh_simulation()

    def _ability_metric_entry(self, ability, metric_key):
        values_payload = ability.get("values", {})
        if isinstance(values_payload, dict):
            entries = values_payload.get(metric_key)
            if isinstance(entries, list) and entries:
                first = entries[0]
                if isinstance(first, dict):
                    return first
        for metric in ability.get("metrics", []) or []:
            if isinstance(metric, dict) and metric.get("key") == metric_key:
                return metric
        return None

    def _ability_metric_value(self, ability, metric_key, ability_level, selected_talent_ids=None, default=None):
        if ability_level <= 0:
            return default
        entry = self._ability_metric_entry(ability, metric_key)
        if not entry:
            return default

        values = entry.get("values")
        value = default
        if isinstance(values, list) and values:
            index = max(0, min(len(values) - 1, ability_level - 1))
            value = values[index]
        elif "value" in entry:
            value = entry.get("value")

        numeric_value = _to_float(value, default=None)
        if numeric_value is None:
            return value

        selected_talent_ids = selected_talent_ids or set()
        upgrades = ability.get("upgrades", {})
        talent_upgrades = upgrades.get("talents", []) if isinstance(upgrades, dict) else []
        for talent in talent_upgrades:
            if not isinstance(talent, dict) or talent.get("id") not in selected_talent_ids:
                continue
            for modifier in talent.get("modifiers", []) or []:
                if not isinstance(modifier, dict):
                    continue
                matches = set(modifier.get("matches", []) or [])
                metric_matches = modifier.get("metricKey") == metric_key or metric_key in matches
                if not metric_matches:
                    continue
                modifier_value = _to_float(modifier.get("value"), default=0.0)
                op = str(modifier.get("op") or "add").lower()
                if op == "add":
                    numeric_value += modifier_value
                elif op in {"subtract", "sub"}:
                    numeric_value -= modifier_value
                elif op == "multiply":
                    numeric_value *= modifier_value
                elif op == "divide" and modifier_value:
                    numeric_value /= modifier_value
        return numeric_value

    def _ability_metric_text(self, ability, metric_key, ability_level, default="-"):
        value = self._ability_metric_value(
            ability,
            metric_key,
            ability_level,
            self.current_skill_state.get("selected_talent_ids", set()),
            default=None,
        )
        return default if value is None else _format_number(value)

    def _duration_for_ability(self, ability, ability_level):
        selected_talents = self.current_skill_state.get("selected_talent_ids", set())
        for key in (
            "duration",
            "debuffDuration",
            "slowDuration",
            "stunDuration",
            "silenceDuration",
            "rootDuration",
            "buffDuration",
            "maxChannelTime",
        ):
            value = self._ability_metric_value(ability, key, ability_level, selected_talents, default=None)
            if value is not None:
                return _to_float(value, default=0.0)
        return 0.0

    def _infer_ability_damage_type(self, ability, payload=None):
        text = " ".join(
            [
                str(ability.get("name", "")),
                str(ability.get("description", "")),
                " ".join(str(effect) for effect in ability.get("effects", []) or []),
            ]
        ).lower()
        if "pure damage" in text or " pure " in f" {text} ":
            return "Pure"
        if "physical damage" in text or (payload and payload.get("uses_attack_damage")):
            return "Physical"
        if "magical damage" in text or "magic damage" in text:
            return "Magical"
        if str(ability.get("type", "")).strip().lower() == "passive":
            return "Physical"
        return "Magical"

    def _ability_damage_payload(self, ability, ability_level, caster_stats):
        selected_talents = self.current_skill_state.get("selected_talent_ids", set())
        payload = {
            "instant": 0.0,
            "dot_dps": 0.0,
            "dot_duration": 0.0,
            "damage_type": "Magical",
            "uses_attack_damage": False,
            "notes": [],
        }
        if ability_level <= 0:
            return payload

        instant_factor = self._ability_metric_value(ability, "instantAttackFactor", ability_level, selected_talents, default=None)
        if instant_factor is not None:
            factor = _to_float(instant_factor)
            if abs(factor) > 3:
                factor /= 100.0
            payload["instant"] += _to_float(caster_stats.get("total_attack_damage")) * factor
            payload["uses_attack_damage"] = True
            payload["notes"].append(f"{_format_number(factor * 100)}% attack")

        attack_damage_bonus = self._ability_metric_value(ability, "attackDamageBonus", ability_level, selected_talents, default=None)
        if attack_damage_bonus is not None:
            payload["instant"] += _to_float(attack_damage_bonus)
            payload["notes"].append(f"+{_format_number(attack_damage_bonus)} attack bonus")

        if instant_factor is None:
            for key in ("damage", "firstDamage", "damageDealt", "totalDamage", "baseDamage", "maxDamage"):
                value = self._ability_metric_value(ability, key, ability_level, selected_talents, default=None)
                if value is not None:
                    payload["instant"] += _to_float(value)
                    payload["notes"].append(f"{key} {_format_number(value)}")
                    break

        instance_damage = self._ability_metric_value(ability, "damagePerInstance", ability_level, selected_talents, default=None)
        if instance_damage is not None:
            instances = 1.0
            for key in ("numberOfInstances", "hitCount", "numberOfAttacks"):
                count = self._ability_metric_value(ability, key, ability_level, selected_talents, default=None)
                if count is not None:
                    instances = max(1.0, _to_float(count))
                    break
            payload["instant"] += _to_float(instance_damage) * instances
            payload["notes"].append(f"{_format_number(instance_damage)} x {_format_number(instances)}")

        dps = self._ability_metric_value(ability, "damagePerSecond", ability_level, selected_talents, default=None)
        if dps is not None:
            duration = self._duration_for_ability(ability, ability_level)
            payload["dot_dps"] = _to_float(dps)
            payload["dot_duration"] = duration
            payload["notes"].append(f"{_format_number(dps)}/s")

        payload["damage_type"] = self._infer_ability_damage_type(ability, payload)
        return payload

    def _refresh_ability_tree(self):
        for row_id in self.ability_tree.get_children():
            self.ability_tree.delete(row_id)

        hero_name, hero_data = self._selected_hero_data()
        abilities = self._hero_abilities(hero_data)
        ability_levels = self.current_skill_state.get("ability_levels", [0 for _ in abilities])
        learned = sum(1 for level in ability_levels if level > 0)
        self.ability_summary_var.set(
            f"{hero_name}: {len(abilities)} abilities loaded, {learned} currently leveled from the skill build."
        )

        rows = []
        for index, ability in enumerate(abilities):
            level = ability_levels[index] if index < len(ability_levels) else 0
            max_level = self._ability_max_level(ability)
            damage_payload = self._ability_damage_payload(ability, level, self.current_stats)
            damage_text = "-"
            if damage_payload["instant"] or damage_payload["dot_dps"]:
                parts = []
                if damage_payload["instant"]:
                    parts.append(_format_number(damage_payload["instant"]))
                if damage_payload["dot_dps"]:
                    duration = damage_payload["dot_duration"]
                    if duration:
                        parts.append(f"{_format_number(damage_payload['dot_dps'])}/s x {_format_number(duration)}s")
                    else:
                        parts.append(f"{_format_number(damage_payload['dot_dps'])}/s")
                damage_text = f"{' + '.join(parts)} {damage_payload['damage_type']}"

            effects = ", ".join(str(effect) for effect in (ability.get("effects", []) or [])[:8])
            row = (
                f"{level}/{max_level}",
                str(ability.get("type", "") or "-"),
                damage_text,
                self._ability_metric_text(ability, "cooldown", level),
                self._ability_metric_text(ability, "manaCost", level),
                _format_number(self._duration_for_ability(ability, level)) if self._duration_for_ability(ability, level) else "-",
                effects,
            )
            rows.append(row)
            self.ability_tree.insert("", "end", text=str(ability.get("name", f"Ability {index + 1}")), values=row)
        self.current_ability_rows = rows

    def _parse_timeline_seconds(self):
        try:
            seconds = int(float(self.timeline_seconds_var.get()))
        except ValueError:
            seconds = DEFAULT_TIMELINE_SECONDS
        return max(1, min(90, seconds))

    def _parse_action_events(self, duration):
        actions = []
        for time_var, choice_var in zip(self.action_time_vars, self.action_choice_vars):
            choice = choice_var.get().strip()
            if not choice or choice == ACTION_EMPTY:
                continue
            time_value = _to_float(time_var.get(), default=None)
            if time_value is None:
                continue
            time_value = _clamp(time_value, 0.0, float(duration))
            actions.append({"time": time_value, "choice": choice})
        return sorted(actions, key=lambda action: action["time"])

    def _build_target_snapshot(self):
        mode = self.target_mode_var.get()
        if mode == TARGET_NONE:
            self.target_summary_var.set("No target selected.")
            return None
        if mode == TARGET_HERO:
            hero_name = self.target_hero_var.get().strip()
            hero_data = self.heroes.get(hero_name)
            if not hero_data:
                self.target_summary_var.set("Hero target not found.")
                return None
            try:
                level = int(self.target_level_var.get())
            except ValueError:
                level = 1
            level = max(1, min(30, level))
            empty_skill_state = {
                "selected_talent_ids": set(),
                "attribute_bonus_points": 0,
            }
            computed = self._compute_stats_for(hero_name, hero_data, level, item_names=[], skill_state=empty_skill_state)
            target = {
                "name": f"{hero_name} L{level}",
                "max_health": computed["health"],
                "health": computed["health"],
                "health_regen": computed["health_regen"],
                "armor": computed["armor"],
                "magic_resist": computed["magic_resist"],
            }
        else:
            health = max(0.0, _to_float(self.target_health_var.get(), default=1000.0))
            target = {
                "name": "Manual Unit",
                "max_health": health,
                "health": health,
                "health_regen": _to_float(self.target_health_regen_var.get(), default=0.0),
                "armor": _to_float(self.target_armor_var.get(), default=0.0),
                "magic_resist": _to_float(self.target_magic_resist_var.get(), default=25.0),
            }
        self.target_summary_var.set(
            f"{target['name']}: {_format_number(target['health'])} HP, "
            f"{_format_number(target['armor'])} armor, {_format_number(target['magic_resist'])}% MR, "
            f"{_format_number(target['health_regen'])} regen"
        )
        return target

    def _active_effects(self, effects, current_time):
        return [effect for effect in effects if effect.get("expires", math.inf) > current_time + 1e-9]

    def _effective_target_armor(self, target, effects, current_time):
        return _to_float(target.get("armor")) + sum(effect.get("armor_delta", 0.0) for effect in self._active_effects(effects, current_time))

    def _effective_target_magic_resist(self, target, effects, current_time):
        magic_resist = _to_float(target.get("magic_resist")) + sum(
            effect.get("magic_resist_delta", 0.0) for effect in self._active_effects(effects, current_time)
        )
        return _clamp(magic_resist, -100.0, 95.0)

    def _apply_damage_to_target(self, raw_damage, damage_type, target, target_effects, current_time):
        if target is None or raw_damage <= 0:
            return 0.0
        damage_type = _damage_type_label(damage_type)
        if damage_type == "Physical":
            effective_damage = apply_physical_reduction(raw_damage, self._effective_target_armor(target, target_effects, current_time))
        elif damage_type == "Magical":
            effective_damage = apply_magic_resistance(
                raw_damage,
                self._effective_target_magic_resist(target, target_effects, current_time) / 100.0,
            )
        else:
            effective_damage = raw_damage
        actual_damage = min(max(0.0, target["health"]), max(0.0, effective_damage))
        target["health"] = max(0.0, target["health"] - actual_damage)
        return actual_damage

    def _current_attack_timing(self, stats, caster_effects, current_time):
        attack_speed = _to_float(stats.get("attack_speed"))
        for effect in self._active_effects(caster_effects, current_time):
            attack_speed += effect.get("attack_speed_bonus", 0.0)
            if effect.get("attack_speed_pct"):
                attack_speed *= max(0.0, 1 + effect["attack_speed_pct"])
        attack_interval = _attack_interval(attack_speed, _to_float(stats.get("base_attack_time")))
        attack_point, attack_backswing = _effective_attack_animation(
            _to_float(stats.get("animation_point"), default=0.0),
            _to_float(stats.get("animation_backswing"), default=0.0),
            attack_speed,
            _to_float(stats.get("attack_point_manip"), default=0.0),
        )
        return {
            "attack_speed": attack_speed,
            "attack_interval": attack_interval,
            "attack_point": attack_point,
            "attack_backswing": attack_backswing,
        }

    def _expected_attack_multiplier(self, hero_data, skill_state):
        multiplier = 1.0
        notes = []
        selected_talents = skill_state.get("selected_talent_ids", set())
        for index, ability in enumerate(self._hero_abilities(hero_data)):
            ability_levels = skill_state.get("ability_levels", [])
            level = ability_levels[index] if index < len(ability_levels) else 0
            if level <= 0:
                continue
            proc = self._ability_metric_value(ability, "procChance", level, selected_talents, default=None)
            crit = self._ability_metric_value(ability, "critDamage", level, selected_talents, default=None)
            if proc is None or crit is None:
                continue
            proc_fraction = _to_float(proc) / 100.0
            crit_fraction = _to_float(crit) / 100.0
            multiplier *= 1.0 + (proc_fraction * max(0.0, crit_fraction - 1.0))
            notes.append(f"{ability.get('name')} expected crit")

        for item_name in self._selected_item_names():
            item = self.items.get(item_name, {})
            for ability in item.get("abilities", []) or []:
                description = str(ability.get("description", "") or "")
                proc_match = re.search(r"Proc Chance:\s*(\d+(?:\.\d+)?)%", description, flags=re.IGNORECASE)
                crit_match = re.search(r"Critical Damage:\s*(\d+(?:\.\d+)?)%", description, flags=re.IGNORECASE)
                if not proc_match or not crit_match:
                    continue
                proc_fraction = _to_float(proc_match.group(1)) / 100.0
                crit_fraction = _to_float(crit_match.group(1)) / 100.0
                multiplier *= 1.0 + (proc_fraction * max(0.0, crit_fraction - 1.0))
                notes.append(f"{item_name} expected crit")
        return multiplier, notes

    def _apply_attack_debuffs(self, target_effects, current_time):
        for item_name in self._selected_item_names():
            item = self.items.get(item_name, {})
            for ability in item.get("abilities", []) or []:
                if str(ability.get("type", "")).strip().lower() != "passive":
                    continue
                description = str(ability.get("description", "") or "")
                armor_match = re.search(r"Armor Reduction:\s*(\d+(?:\.\d+)?)", description, flags=re.IGNORECASE)
                if not armor_match:
                    continue
                duration_match = re.search(r"Duration:\s*(\d+(?:\.\d+)?)", description, flags=re.IGNORECASE)
                duration = _to_float(duration_match.group(1), default=7.0) if duration_match else 7.0
                effect_name = f"{item_name} armor reduction"
                target_effects[:] = [effect for effect in target_effects if effect.get("name") != effect_name]
                target_effects.append({
                    "name": effect_name,
                    "expires": current_time + duration,
                    "armor_delta": -_to_float(armor_match.group(1)),
                })

    def _apply_spell_status_effects(self, ability, ability_level, current_time, target, target_effects, caster_effects):
        selected_talents = self.current_skill_state.get("selected_talent_ids", set())
        duration = self._duration_for_ability(ability, ability_level)
        if target is not None and duration > 0:
            armor_reduction = self._ability_metric_value(ability, "armorReduction", ability_level, selected_talents, default=None)
            magic_reduction = self._ability_metric_value(ability, "magicResistReduction", ability_level, selected_talents, default=None)
            restore_reduction = self._ability_metric_value(ability, "healthRestoreReduction", ability_level, selected_talents, default=None)
            effect = {
                "name": str(ability.get("name", "Spell")),
                "expires": current_time + duration,
            }
            if armor_reduction is not None:
                effect["armor_delta"] = -_to_float(armor_reduction)
            if magic_reduction is not None:
                effect["magic_resist_delta"] = -_to_float(magic_reduction)
            if restore_reduction is not None:
                effect["hp_regen_delta"] = -_to_float(target.get("health_regen")) * (_to_float(restore_reduction) / 100.0)
            if len(effect) > 2:
                target_effects.append(effect)

        attack_speed_bonus = self._ability_metric_value(ability, "attackSpeedBonus", ability_level, selected_talents, default=None)
        if attack_speed_bonus is not None and duration > 0:
            caster_effects.append({
                "name": str(ability.get("name", "Buff")),
                "expires": current_time + duration,
                "attack_speed_bonus": _to_float(attack_speed_bonus),
            })

    def _advance_simulation_time(self, target, target_effects, current_time, next_time, damage_events):
        if target is None or next_time <= current_time:
            return 0.0
        delta = next_time - current_time
        total_effective = 0.0
        active_effects = self._active_effects(target_effects, current_time)

        if target["health"] > 0:
            regen = _to_float(target.get("health_regen")) + sum(effect.get("hp_regen_delta", 0.0) for effect in active_effects)
            if regen:
                target["health"] = min(target["max_health"], max(0.0, target["health"] + regen * delta))

        for effect in active_effects:
            dot_dps = effect.get("dot_dps", 0.0)
            if dot_dps <= 0 or target["health"] <= 0:
                continue
            raw_damage = dot_dps * delta
            effective = self._apply_damage_to_target(
                raw_damage,
                effect.get("damage_type", "Magical"),
                target,
                target_effects,
                current_time,
            )
            total_effective += effective
            damage_events.append({
                "time": next_time,
                "label": effect.get("name", "DoT"),
                "kind": "dot",
                "raw": raw_damage,
                "damage": effective,
                "target_hp": target["health"],
            })
        return total_effective

    def _simulate_action_line(self, stats, skill_state):
        hero_name, hero_data = self._selected_hero_data()
        abilities = self._hero_abilities(hero_data)
        duration = self._parse_timeline_seconds()
        actions = self._parse_action_events(duration)
        target = self._build_target_snapshot()
        target_effects = []
        caster_effects = []
        cooldowns = {}
        mana = _to_float(stats.get("mana"))
        current_time = 0.0
        next_tick = 0
        action_index = 0
        auto_attacking = False
        next_attack_start = None
        pending_hits = []
        samples = []
        event_markers = []
        damage_events = []
        logs = []
        total_effective_damage = 0.0
        loop_guard = 0
        eps = 1e-7

        def add_log(time_value, text):
            logs.append(f"{_timeline_time_label(time_value)}: {text}")

        while current_time <= duration + eps and loop_guard < 20000:
            loop_guard += 1
            candidates = [float(duration)]
            if next_tick <= duration:
                candidates.append(float(next_tick))
            if action_index < len(actions):
                candidates.append(actions[action_index]["time"])
            if auto_attacking and next_attack_start is not None:
                candidates.append(next_attack_start)
            if pending_hits:
                candidates.append(min(hit["time"] for hit in pending_hits))

            future_candidates = [time_value for time_value in candidates if time_value >= current_time - eps]
            if not future_candidates:
                break
            next_time = min(future_candidates)

            if next_time > current_time + eps:
                total_effective_damage += self._advance_simulation_time(
                    target,
                    target_effects,
                    current_time,
                    next_time,
                    damage_events,
                )
                current_time = next_time
                target_effects = self._active_effects(target_effects, current_time)
                caster_effects = self._active_effects(caster_effects, current_time)

            while action_index < len(actions) and actions[action_index]["time"] <= current_time + eps:
                choice = actions[action_index]["choice"]
                if choice == ACTION_AUTO_ATTACK:
                    auto_attacking = True
                    next_attack_start = current_time
                    add_log(current_time, "Auto attack started.")
                    event_markers.append({"time": current_time, "label": "Attack", "kind": "action"})
                elif choice == ACTION_STOP:
                    auto_attacking = False
                    next_attack_start = None
                    add_log(current_time, "Actions stopped.")
                    event_markers.append({"time": current_time, "label": "Stop", "kind": "action"})
                elif choice in self.action_option_map:
                    ability_index = self.action_option_map[choice]["index"]
                    if ability_index >= len(abilities):
                        add_log(current_time, f"{choice} skipped; ability is unavailable for the selected hero.")
                        action_index += 1
                        continue
                    ability = abilities[ability_index]
                    ability_levels = skill_state.get("ability_levels", [])
                    ability_level = ability_levels[ability_index] if ability_index < len(ability_levels) else 0
                    name = str(ability.get("name", "Ability"))
                    if ability_level <= 0:
                        add_log(current_time, f"{name} skipped; ability is not leveled.")
                    elif cooldowns.get(name, 0.0) > current_time + eps:
                        add_log(current_time, f"{name} skipped; cooldown ready at {_timeline_time_label(cooldowns[name])}.")
                    else:
                        mana_cost = self._ability_metric_value(
                            ability,
                            "manaCost",
                            ability_level,
                            skill_state.get("selected_talent_ids", set()),
                            default=0.0,
                        )
                        mana_cost = _to_float(mana_cost)
                        if mana < mana_cost:
                            add_log(current_time, f"{name} skipped; not enough mana.")
                        else:
                            mana -= mana_cost
                            cooldown = self._ability_metric_value(
                                ability,
                                "cooldown",
                                ability_level,
                                skill_state.get("selected_talent_ids", set()),
                                default=0.0,
                            )
                            cooldowns[name] = current_time + _to_float(cooldown)
                            impact_time = current_time + _to_float(stats.get("animation_point"), default=0.0)
                            pending_hits.append({
                                "time": impact_time,
                                "kind": "spell",
                                "ability_index": ability_index,
                                "ability_level": ability_level,
                            })
                            if auto_attacking and next_attack_start is not None:
                                next_attack_start = max(next_attack_start, impact_time)
                            add_log(current_time, f"Cast {name} L{ability_level} (-{_format_number(mana_cost)} mana).")
                            event_markers.append({"time": current_time, "label": name, "kind": "spell_cast"})
                action_index += 1

            if auto_attacking and next_attack_start is not None and next_attack_start <= current_time + eps:
                attack_timing = self._current_attack_timing(stats, caster_effects, current_time)
                interval = attack_timing["attack_interval"]
                attack_point = attack_timing["attack_point"]
                if not math.isinf(interval) and interval > 0:
                    pending_hits.append({
                        "time": current_time + attack_point,
                        "kind": "attack",
                        "attack_point": attack_point,
                        "attack_speed": attack_timing["attack_speed"],
                    })
                    next_attack_start = current_time + interval
                else:
                    next_attack_start = None

            ready_hits = [hit for hit in pending_hits if hit["time"] <= current_time + eps]
            pending_hits = [hit for hit in pending_hits if hit["time"] > current_time + eps]
            for hit in ready_hits:
                if hit["kind"] == "attack":
                    multiplier, notes = self._expected_attack_multiplier(hero_data, skill_state)
                    raw_damage = _to_float(stats.get("total_attack_damage")) * multiplier
                    effective = self._apply_damage_to_target(raw_damage, "Physical", target, target_effects, current_time)
                    total_effective_damage += effective
                    self._apply_attack_debuffs(target_effects, current_time)
                    label = "Attack"
                    event_markers.append({"time": current_time, "label": label, "kind": "attack", "damage": effective})
                    damage_events.append({
                        "time": current_time,
                        "label": label,
                        "kind": "attack",
                        "raw": raw_damage,
                        "damage": effective,
                        "target_hp": target["health"] if target else None,
                    })
                    note_text = f" ({', '.join(notes)})" if notes else ""
                    if target is not None:
                        add_log(current_time, f"Attack hit for {_format_number(effective)} physical{note_text}; target HP {_format_number(target['health'])}.")
                    else:
                        add_log(current_time, f"Attack animated{note_text}; no target.")
                elif hit["kind"] == "spell":
                    ability = abilities[hit["ability_index"]]
                    ability_level = hit["ability_level"]
                    name = str(ability.get("name", "Spell"))
                    payload = self._ability_damage_payload(ability, ability_level, stats)
                    effective = self._apply_damage_to_target(
                        payload["instant"],
                        payload["damage_type"],
                        target,
                        target_effects,
                        current_time,
                    )
                    total_effective_damage += effective
                    if payload["dot_dps"] and payload["dot_duration"] and target is not None:
                        target_effects.append({
                            "name": name,
                            "expires": current_time + payload["dot_duration"],
                            "dot_dps": payload["dot_dps"],
                            "damage_type": payload["damage_type"],
                        })
                    self._apply_spell_status_effects(ability, ability_level, current_time, target, target_effects, caster_effects)
                    event_markers.append({"time": current_time, "label": name, "kind": "spell_hit", "damage": effective})
                    damage_events.append({
                        "time": current_time,
                        "label": name,
                        "kind": "spell",
                        "raw": payload["instant"],
                        "damage": effective,
                        "target_hp": target["health"] if target else None,
                    })
                    if target is not None and (payload["instant"] or payload["dot_dps"]):
                        dot_text = ""
                        if payload["dot_dps"]:
                            dot_text = f" and applied {_format_number(payload['dot_dps'])}/s for {_format_number(payload['dot_duration'])}s"
                        add_log(
                            current_time,
                            f"{name} landed for {_format_number(effective)} {payload['damage_type'].lower()}{dot_text}; "
                            f"target HP {_format_number(target['health'])}.",
                        )
                    else:
                        add_log(current_time, f"{name} resolved.")

            while next_tick <= duration and next_tick <= current_time + eps:
                samples.append({
                    "time": next_tick,
                    "target_hp": target["health"] if target else None,
                    "mana": mana,
                    "active_effects": len(target_effects) + len(caster_effects),
                })
                next_tick += 1

            if current_time >= duration - eps:
                break

        return {
            "duration": duration,
            "target": target,
            "samples": samples,
            "events": event_markers,
            "damage_events": damage_events,
            "logs": logs,
            "total_effective_damage": total_effective_damage,
            "remaining_mana": mana,
        }

    def _refresh_simulation(self):
        simulation = self._simulate_action_line(self.current_stats, self.current_skill_state)
        self.current_simulation = simulation
        target = simulation.get("target")
        if target is None:
            self.simulation_summary_var.set(
                f"{simulation['duration']}s timeline | No target | Remaining mana {_format_number(simulation['remaining_mana'])}"
            )
        else:
            self.simulation_summary_var.set(
                f"{simulation['duration']}s timeline | Total damage {_format_number(simulation['total_effective_damage'])} | "
                f"{target['name']} remaining HP {_format_number(target['health'])} | "
                f"Remaining mana {_format_number(simulation['remaining_mana'])}"
            )
        self._write_simulation_log(simulation.get("logs", []))
        self._draw_timeline(simulation)

    def _write_simulation_log(self, logs):
        if not hasattr(self, "simulation_log"):
            return
        self.simulation_log.configure(state="normal")
        self.simulation_log.delete("1.0", tk.END)
        if logs:
            self.simulation_log.insert("1.0", "\n".join(logs))
        else:
            self.simulation_log.insert("1.0", "No actions scheduled.")
        self.simulation_log.configure(state="disabled")

    def _draw_timeline(self, simulation):
        if not hasattr(self, "timeline_canvas"):
            return
        canvas = self.timeline_canvas
        canvas.delete("all")
        duration = max(1, simulation.get("duration", DEFAULT_TIMELINE_SECONDS))
        margin_left = 70
        margin_right = 40
        scale = 70
        width = margin_left + margin_right + (duration * scale)
        height = 185
        canvas.configure(scrollregion=(0, 0, width, height))

        canvas.create_text(8, 28, text="Actions", anchor="w", fill="#555")
        canvas.create_text(8, 82, text="Damage", anchor="w", fill="#555")
        canvas.create_text(8, 138, text="Target HP", anchor="w", fill="#555")

        for second in range(duration + 1):
            x = margin_left + second * scale
            canvas.create_line(x, 18, x, 164, fill="#e5e5e5")
            canvas.create_text(x, 8, text=str(second), anchor="n", fill="#666", font=("Arial", 8))
        canvas.create_line(margin_left, 52, width - margin_right, 52, fill="#c9d6df")
        canvas.create_line(margin_left, 104, width - margin_right, 104, fill="#f0c2b8")
        canvas.create_line(margin_left, 160, width - margin_right, 160, fill="#cbd8c1")

        kind_colors = {
            "action": "#457b9d",
            "attack": "#a44a3f",
            "spell_cast": "#6d597a",
            "spell_hit": "#b56576",
        }
        for event in simulation.get("events", []):
            x = margin_left + event["time"] * scale
            color = kind_colors.get(event.get("kind"), "#555")
            y = 52 if event.get("kind") in {"action", "spell_cast"} else 104
            canvas.create_line(x, y - 18, x, y + 18, fill=color, width=2)
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=color, outline=color)
            label = str(event.get("label", ""))[:14]
            if label:
                canvas.create_text(x + 5, y - 18, text=label, anchor="sw", fill=color, font=("Arial", 8))

        target = simulation.get("target")
        samples = simulation.get("samples", [])
        if target is not None and samples:
            max_health = max(1.0, _to_float(target.get("max_health"), default=1.0))
            points = []
            for sample in samples:
                hp = sample.get("target_hp")
                if hp is None:
                    continue
                x = margin_left + sample["time"] * scale
                pct = _clamp(_to_float(hp) / max_health, 0.0, 1.0)
                y = 160 - (pct * 46)
                points.extend([x, y])
                canvas.create_text(x, 171, text=_format_number(hp), anchor="n", fill="#4a6f39", font=("Arial", 8))
            if len(points) >= 4:
                canvas.create_line(*points, fill="#4a7c59", width=2, smooth=True)
            elif len(points) == 2:
                canvas.create_oval(points[0] - 3, points[1] - 3, points[0] + 3, points[1] + 3, fill="#4a7c59", outline="")
        else:
            canvas.create_text(margin_left, 138, text="No target HP track", anchor="w", fill="#777")
