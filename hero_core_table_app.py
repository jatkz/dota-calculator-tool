import copy
import json
import os
import re
import tkinter as tk
from difflib import get_close_matches
from tkinter import ttk


INVENTORY_SLOTS = 6
MAX_LEVEL = 30
TALENT_TIERS = ("10", "15", "20", "25")
TALENT_CHOICES = ("None", "Left", "Right")

ATTRIBUTE_DISPLAY = {
    "strength": "STR",
    "agility": "AGI",
    "intelligence": "INT",
    "universal": "UNI",
    "unknown": "?",
}

TABLE_COLUMNS = [
    ("row_label", "Row", 80, "center"),
    ("hero", "Hero", 180, "w"),
    ("level", "Lvl", 50, "center"),
    ("networth", "Networth", 95, "e"),
    ("primary_attribute", "Attr", 55, "center"),
    ("attack_type", "Attack", 70, "center"),
    ("roles", "Roles", 180, "w"),
    ("strength", "Str", 70, "e"),
    ("strength_gain", "Str/Lvl", 70, "e"),
    ("agility", "Agi", 70, "e"),
    ("agility_gain", "Agi/Lvl", 70, "e"),
    ("intelligence", "Int", 70, "e"),
    ("intelligence_gain", "Int/Lvl", 70, "e"),
    ("health", "Health", 80, "e"),
    ("health_regen", "HP Regen", 85, "e"),
    ("mana", "Mana", 80, "e"),
    ("mana_regen", "Mana Regen", 90, "e"),
    ("armor", "Armor", 70, "e"),
    ("magic_resist", "Magic Resist", 90, "e"),
    ("attack_damage", "Attack Damage", 95, "e"),
    ("attack_speed", "Attack Speed", 90, "e"),
    ("move_speed", "Move", 70, "e"),
    ("attack_range", "Range", 70, "e"),
    ("projectile_speed", "Projectile", 90, "e"),
    ("bat", "BAT", 60, "e"),
    ("turn_rate", "Turn", 60, "e"),
    ("talents", "Talents", 120, "w"),
    ("items", "Items", 260, "w"),
]

NUMERIC_COLUMNS = {
    "level",
    "networth",
    "strength",
    "strength_gain",
    "agility",
    "agility_gain",
    "intelligence",
    "intelligence_gain",
    "health",
    "health_regen",
    "mana",
    "mana_regen",
    "armor",
    "magic_resist",
    "attack_damage",
    "attack_speed",
    "move_speed",
    "attack_range",
    "projectile_speed",
    "bat",
    "turn_rate",
}


def _load_json_file(path, default_payload):
    if not os.path.exists(path):
        return default_payload

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_payload

    if isinstance(default_payload, dict) and isinstance(payload, dict):
        return payload
    if isinstance(default_payload, list) and isinstance(payload, list):
        return payload
    return default_payload


def _to_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or "").strip()
    if not text:
        return default

    try:
        return float(text)
    except ValueError:
        return default


def _format_number(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value

    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _format_percent_points(value):
    if value is None:
        return ""
    return _format_number(value)


def _normalize_choice(value, choices):
    text = str(value or "").strip()
    if not text:
        return ""
    return next((choice for choice in choices if choice.lower() == text.lower()), "")


def _split_tokens(text):
    return [token.strip() for token in re.split(r"[,;\n|]+", str(text or "")) if token.strip()]


def _normalize_match_text(text):
    lowered = str(text or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_compact_text(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


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
    }


def _merge_modifiers(target, source):
    for key in target:
        target[key] += source.get(key, 0.0)


def _first_numeric_value(value_text):
    text = str(value_text or "").strip()
    if not text:
        return None, False

    is_percent = "%" in text
    match = re.search(r"[+-]?\d+(?:\.\d+)?", text)
    if not match:
        return None, is_percent
    return float(match.group(0)), is_percent


class HeroCoreTableApp:
    def __init__(self, parent):
        self.parent = parent
        self.base_dir = os.path.dirname(__file__)
        self.dataset_path = os.path.join(self.base_dir, "dataset.json")

        self.dataset_payload = _load_json_file(self.dataset_path, {"heroesCore": {}, "items": {}})
        self.heroes = self._load_heroes()
        self.items = self._load_items()

        self.hero_names = sorted(self.heroes.keys())
        self.item_names = [""] + sorted(self.items.keys())
        self.item_shop_names = sorted(self.items.keys())
        self.item_name_search_index = {
            item_name: self._build_item_name_search_text(item_name)
            for item_name in self.items.keys()
        }
        self.item_detail_search_index = {
            item_name: self._build_item_detail_search_text(item_data)
            for item_name, item_data in self.items.items()
        }
        self.hero_rows = {}
        self.row_sequence = 0
        self.item_modifier_cache = {}

        self.hero_match_names = {
            hero_name: _normalize_match_text(hero_name)
            for hero_name in self.hero_names
        }
        self.hero_match_lookup = {
            normalized_name: hero_name
            for hero_name, normalized_name in self.hero_match_names.items()
            if normalized_name
        }
        self.hero_compact_lookup = {
            _normalize_compact_text(hero_name): hero_name
            for hero_name in self.hero_names
            if _normalize_compact_text(hero_name)
        }
        self.hero_match_choices = list(self.hero_match_lookup.keys())
        self.hero_compact_choices = list(self.hero_compact_lookup.keys())

        self.current_selected_row_id = None
        self.loading_editor = False
        self.sort_column = "hero"
        self.sort_reverse = False
        self.hero_pool_names = set()

        self.search_var = tk.StringVar(value="")
        self.pool_input_var = tk.StringVar(value="")
        self.use_pool_only_var = tk.BooleanVar(value=False)
        self.bulk_level_var = tk.StringVar(value="1")
        self.summary_var = tk.StringVar(value="")
        self.pool_status_var = tk.StringVar(value="Hero pool: none")
        self.data_status_var = tk.StringVar(
            value=(
                "Using heroesCore from dataset.json. "
                "Direct stat talents and item stat lines are applied automatically, and you can duplicate rows to compare builds."
            )
        )

        self.selected_hero_var = tk.StringVar(value="Select a hero row from the table.")
        self.selected_hero_meta_var = tk.StringVar(value="")
        self.selected_row_name_var = tk.StringVar(value="")
        self.selected_level_var = tk.StringVar(value="1")
        self.selected_items_vars = [tk.StringVar(value="") for _ in range(INVENTORY_SLOTS)]
        self.selected_item_display_vars = [tk.StringVar(value="Choose Item") for _ in range(INVENTORY_SLOTS)]
        self.selected_talent_vars = {
            tier: tk.StringVar(value=TALENT_CHOICES[0])
            for tier in TALENT_TIERS
        }
        self.selected_applied_summary_var = tk.StringVar(value="")
        self.shop_status_var = tk.StringVar(value="")
        self.shop_name_search_var = tk.StringVar(value="")
        self.shop_detail_search_var = tk.StringVar(value="")
        self.shop_empty_var = tk.StringVar(value="")
        self.shop_name_search_trace_id = self.shop_name_search_var.trace_add("write", self._handle_shop_search_change)
        self.shop_detail_search_trace_id = self.shop_detail_search_var.trace_add("write", self._handle_shop_search_change)

        self.table_rows_by_id = {}
        self.item_slot_buttons = []
        self.talent_meta_labels = {}
        self.duplicate_row_button = None
        self.remove_row_button = None
        self.shop_window = None
        self.shop_canvas = None
        self.shop_canvas_window_id = None
        self.shop_grid_frame = None
        self.active_item_slot_index = None

        self._initialize_hero_rows()

        self._build_ui()
        self._bind_editor_vars()
        self._refresh_table()

    def _load_heroes(self):
        heroes = self.dataset_payload.get("heroesCore", {})
        if isinstance(heroes, dict):
            return heroes
        return {}

    def _load_items(self):
        items = self.dataset_payload.get("items", {})
        if isinstance(items, dict):
            return items
        return {}

    def _build_item_name_search_text(self, item_name):
        return _normalize_match_text(item_name)

    def _build_item_detail_search_text(self, item_data):
        parts = []

        description_text = item_data.get("description")
        if description_text:
            parts.append(str(description_text))

        stats_payload = item_data.get("stats")
        if isinstance(stats_payload, dict):
            for stat_name, stat_value in stats_payload.items():
                parts.append(str(stat_name))
                parts.append(str(stat_value))

        recipe_payload = item_data.get("recipe")
        if isinstance(recipe_payload, list):
            parts.extend(str(component_name) for component_name in recipe_payload)

        abilities = item_data.get("abilities", [])
        if isinstance(abilities, list):
            for ability in abilities:
                if not isinstance(ability, dict):
                    continue
                parts.append(str(ability.get("name", "")))
                parts.append(str(ability.get("type", "")))
                parts.append(str(ability.get("description", "")))

        return _normalize_match_text(" ".join(part for part in parts if part))

    def _build_ui(self):
        container = ttk.Frame(self.parent, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Hero Core Table", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            container,
            text=(
                "Browse all heroes in a sortable table, filter to a hero pool, "
                "and edit level, items, and talents per hero."
            ),
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(container, textvariable=self.data_status_var, foreground="#666").pack(anchor="w", pady=(0, 12))

        controls = ttk.LabelFrame(container, text="Filters And Bulk Actions", padding=10)
        controls.pack(fill="x", pady=(0, 12))

        ttk.Label(controls, text="Search").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(controls, textvariable=self.search_var, width=28)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 12))

        ttk.Label(controls, text="Hero Pool").grid(row=0, column=2, sticky="w")
        pool_entry = ttk.Entry(controls, textvariable=self.pool_input_var, width=54)
        pool_entry.grid(row=0, column=3, sticky="ew", padx=(6, 8))

        ttk.Button(controls, text="Apply Pool", command=self._apply_hero_pool).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(controls, text="Pool From Selection", command=self._set_pool_from_selection).grid(row=0, column=5, padx=(0, 6))
        ttk.Button(controls, text="Clear Pool", command=self._clear_hero_pool).grid(row=0, column=6)

        ttk.Checkbutton(
            controls,
            text="Use Pool Only",
            variable=self.use_pool_only_var,
            command=self._refresh_table,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        ttk.Label(controls, textvariable=self.pool_status_var, foreground="#666").grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="w",
            padx=(6, 0),
            pady=(8, 0),
        )

        ttk.Label(controls, text="Visible Levels").grid(row=1, column=4, sticky="e", pady=(8, 0))
        ttk.Button(controls, text="-1", width=4, command=lambda: self._adjust_visible_levels(-1)).grid(
            row=1,
            column=5,
            sticky="w",
            padx=(6, 4),
            pady=(8, 0),
        )
        ttk.Button(controls, text="+1", width=4, command=lambda: self._adjust_visible_levels(1)).grid(
            row=1,
            column=5,
            sticky="w",
            padx=(54, 4),
            pady=(8, 0),
        )
        ttk.Entry(controls, textvariable=self.bulk_level_var, width=6).grid(
            row=1,
            column=6,
            sticky="w",
            padx=(6, 70),
            pady=(8, 0),
        )
        ttk.Button(controls, text="Set Visible To Level", command=self._set_visible_levels).grid(
            row=1,
            column=6,
            sticky="e",
            pady=(8, 0),
        )

        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=2)

        ttk.Label(container, textvariable=self.summary_var, foreground="#666").pack(anchor="w", pady=(0, 10))

        body = ttk.Panedwindow(container, orient="horizontal")
        body.pack(fill="both", expand=True)

        table_frame = ttk.Frame(body)
        editor_frame = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(table_frame, weight=5)
        body.add(editor_frame, weight=3)

        tree_frame = ttk.LabelFrame(table_frame, text="Hero Table")
        tree_frame.pack(fill="both", expand=True)

        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill="both", expand=True, padx=8, pady=8)

        columns = [column_id for column_id, _label, _width, _anchor in TABLE_COLUMNS]
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="extended")
        for column_id, label, width, anchor in TABLE_COLUMNS:
            self.tree.heading(column_id, text=label, command=lambda col=column_id: self._toggle_sort(col))
            self.tree.column(column_id, width=width, anchor=anchor, stretch=True)

        tree_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        tree_x = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_y.grid(row=0, column=1, sticky="ns")
        tree_x.grid(row=1, column=0, sticky="ew")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._handle_tree_selection)
        self.tree.bind("<Double-1>", lambda _event: self._set_pool_from_selection())

        editor_card = ttk.LabelFrame(editor_frame, text="Selected Hero")
        editor_card.pack(fill="both", expand=True)

        ttk.Label(editor_card, textvariable=self.selected_hero_var, font=("Arial", 14, "bold")).pack(
            anchor="w",
            padx=10,
            pady=(10, 4),
        )
        ttk.Label(editor_card, textvariable=self.selected_hero_meta_var, foreground="#666", wraplength=520).pack(
            anchor="w",
            padx=10,
            pady=(0, 10),
        )

        row_name_frame = ttk.Frame(editor_card)
        row_name_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(row_name_frame, text="Row Name").pack(side="left")
        ttk.Entry(row_name_frame, textvariable=self.selected_row_name_var).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(8, 8),
        )
        ttk.Button(row_name_frame, text="Reset Name", command=self._reset_selected_row_name).pack(side="left")

        level_row = ttk.Frame(editor_card)
        level_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(level_row, text="Level").pack(side="left")
        ttk.Button(level_row, text="-", width=3, command=lambda: self._adjust_selected_level(-1)).pack(side="left", padx=(8, 4))
        ttk.Entry(level_row, textvariable=self.selected_level_var, width=6).pack(side="left")
        ttk.Button(level_row, text="+", width=3, command=lambda: self._adjust_selected_level(1)).pack(side="left", padx=(4, 0))
        ttk.Button(level_row, text="Reset Hero", command=self._reset_selected_hero).pack(side="left", padx=(12, 6))
        ttk.Button(level_row, text="Clear Items", command=self._clear_selected_items).pack(side="left")

        row_actions = ttk.Frame(editor_card)
        row_actions.pack(fill="x", padx=10, pady=(0, 10))
        self.duplicate_row_button = ttk.Button(
            row_actions,
            text="Duplicate Row",
            command=self._duplicate_selected_row,
            state="disabled",
        )
        self.duplicate_row_button.pack(side="left", padx=(0, 6))
        self.remove_row_button = ttk.Button(
            row_actions,
            text="Remove Extra Row",
            command=self._remove_selected_row,
            state="disabled",
        )
        self.remove_row_button.pack(side="left")

        items_frame = ttk.LabelFrame(editor_card, text="Items")
        items_frame.pack(fill="x", padx=10, pady=(0, 10))

        for index, _item_var in enumerate(self.selected_items_vars):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(items_frame, text=f"Slot {index + 1}").grid(row=row, column=column, sticky="w", padx=(8, 6), pady=6)
            button = ttk.Button(
                items_frame,
                textvariable=self.selected_item_display_vars[index],
                command=lambda slot_index=index: self._open_shop_window(slot_index),
                width=28,
            )
            button.grid(row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=6)
            self.item_slot_buttons.append(button)

        items_frame.columnconfigure(1, weight=1)
        items_frame.columnconfigure(3, weight=1)
        ttk.Label(
            items_frame,
            text="Click a slot to open the shop window. Each pick fills the active slot and advances to the next one.",
            foreground="#666",
            wraplength=520,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 8))

        talents_frame = ttk.LabelFrame(editor_card, text="Talents")
        talents_frame.pack(fill="x", padx=10, pady=(0, 10))

        for row, tier in enumerate(TALENT_TIERS):
            ttk.Label(talents_frame, text=f"Level {tier}").grid(row=row, column=0, sticky="w", padx=(8, 8), pady=6)
            combo = ttk.Combobox(
                talents_frame,
                textvariable=self.selected_talent_vars[tier],
                values=TALENT_CHOICES,
                state="readonly",
                width=10,
            )
            combo.grid(row=row, column=1, sticky="w", padx=(0, 10), pady=6)
            combo.bind("<<ComboboxSelected>>", lambda _event: self._handle_editor_change())

            meta_label = ttk.Label(talents_frame, text="", wraplength=380, foreground="#666", justify="left")
            meta_label.grid(row=row, column=2, sticky="w", pady=6)
            self.talent_meta_labels[tier] = meta_label

        talents_frame.columnconfigure(2, weight=1)

        ttk.Label(
            editor_card,
            text=(
                "Auto-applies only direct stat-like talents. Spell-specific talents stay informational. "
                "Base rows stay in the master list; duplicate a row when you want an alternate build."
            ),
            foreground="#666",
            wraplength=520,
        ).pack(anchor="w", padx=10, pady=(0, 6))
        ttk.Label(
            editor_card,
            textvariable=self.selected_applied_summary_var,
            foreground="#666",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        self.search_var.trace_add("write", lambda *_args: self._refresh_table())

    def _bind_editor_vars(self):
        self.selected_row_name_var.trace_add("write", lambda *_args: self._handle_row_name_change())
        self.selected_level_var.trace_add("write", lambda *_args: self._handle_editor_change())
        for item_var in self.selected_items_vars:
            item_var.trace_add("write", lambda *_args: self._handle_item_slot_var_change())
        for talent_var in self.selected_talent_vars.values():
            talent_var.trace_add("write", lambda *_args: self._handle_editor_change())

    def _handle_item_slot_var_change(self):
        self._refresh_item_slot_labels()
        if not self.loading_editor:
            self._handle_editor_change()

    def _refresh_item_slot_labels(self):
        for index, item_var in enumerate(self.selected_items_vars):
            item_name = str(item_var.get()).strip()
            display_text = item_name or "Choose Item"
            if self.shop_window and self.active_item_slot_index == index:
                display_text = f"[Active] {display_text}"
            self.selected_item_display_vars[index].set(display_text)

    def _shop_title_text(self):
        if (
            self.active_item_slot_index is None
            or self.current_selected_row_id not in self.hero_rows
        ):
            return "Item Shop"

        row_entry = self.hero_rows[self.current_selected_row_id]
        hero_name = row_entry["hero_name"]
        row_label = self._row_label(self.current_selected_row_id)
        return f"Item Shop - {hero_name} ({row_label}) Slot {self.active_item_slot_index + 1}"

    def _filtered_shop_item_names(self):
        name_query = _normalize_match_text(self.shop_name_search_var.get())
        detail_query = _normalize_match_text(self.shop_detail_search_var.get())

        visible_items = []
        for item_name in self.item_shop_names:
            if name_query and name_query not in self.item_name_search_index.get(item_name, ""):
                continue
            if detail_query and detail_query not in self.item_detail_search_index.get(item_name, ""):
                continue
            visible_items.append(item_name)

        return visible_items

    def _render_shop_items(self):
        if not self.shop_grid_frame:
            return

        for child in self.shop_grid_frame.winfo_children():
            child.destroy()

        visible_items = self._filtered_shop_item_names()
        if not visible_items:
            self.shop_empty_var.set("No items match the current item-name and stat/effect filters.")
            self.shop_grid_frame.columnconfigure(0, weight=1)
            ttk.Label(
                self.shop_grid_frame,
                textvariable=self.shop_empty_var,
                foreground="#666",
                wraplength=620,
                justify="left",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        else:
            self.shop_empty_var.set("")
            for column in range(4):
                self.shop_grid_frame.columnconfigure(column, weight=1)

            for index, item_name in enumerate(visible_items):
                row = index // 4
                column = index % 4
                ttk.Button(
                    self.shop_grid_frame,
                    text=item_name,
                    command=lambda selected_item=item_name: self._choose_shop_item(selected_item),
                    width=20,
                ).grid(row=row, column=column, sticky="ew", padx=4, pady=4)

        self._sync_shop_scroll_region()
        if self.shop_canvas:
            self.shop_canvas.yview_moveto(0)

    def _handle_shop_search_change(self, *_args):
        self._render_shop_items()

    def _update_shop_status(self):
        if (
            self.active_item_slot_index is None
            or self.current_selected_row_id not in self.hero_rows
        ):
            self.shop_status_var.set("Select a hero row and item slot.")
            return

        row_entry = self.hero_rows[self.current_selected_row_id]
        hero_name = row_entry["hero_name"]
        row_label = self._row_label(self.current_selected_row_id)
        self.shop_status_var.set(
            f"Choosing an item for {hero_name} ({row_label}) slot {self.active_item_slot_index + 1}. "
            "Click an item to fill the slot, then keep picking for the next slot. "
            "Click outside the shop or use X to close it."
        )
        if self.shop_window and self.shop_window.winfo_exists():
            self.shop_window.title(self._shop_title_text())

    def _position_shop_window(self, anchor_widget=None):
        if not self.shop_window or not self.shop_window.winfo_exists():
            return

        root = self.parent.winfo_toplevel()
        root.update_idletasks()
        self.shop_window.update_idletasks()

        width = max(680, self.shop_window.winfo_reqwidth())
        height = max(460, self.shop_window.winfo_reqheight())

        if anchor_widget is not None:
            x = anchor_widget.winfo_rootx() + 24
            y = anchor_widget.winfo_rooty() + 24
        else:
            x = root.winfo_rootx() + 120
            y = root.winfo_rooty() + 120

        max_x = root.winfo_rootx() + max(0, root.winfo_width() - width - 20)
        max_y = root.winfo_rooty() + max(0, root.winfo_height() - height - 20)
        x = max(root.winfo_rootx() + 20, min(x, max_x))
        y = max(root.winfo_rooty() + 20, min(y, max_y))
        self.shop_window.geometry(f"{width}x{height}+{x}+{y}")

    def _sync_shop_scroll_region(self):
        if not self.shop_canvas or not self.shop_grid_frame:
            return
        self.shop_canvas.configure(scrollregion=self.shop_canvas.bbox("all"))

    def _match_focus_to_shop_window(self):
        if not self.shop_window or not self.shop_window.winfo_exists():
            return
        try:
            focus_widget = self.shop_window.focus_get()
        except tk.TclError:
            self._close_shop_window()
            return

        if focus_widget is None:
            self._close_shop_window()
            return

        try:
            if focus_widget.winfo_toplevel() != self.shop_window:
                self._close_shop_window()
        except tk.TclError:
            self._close_shop_window()

    def _handle_shop_focus_out(self, _event=None):
        if not self.shop_window or not self.shop_window.winfo_exists():
            return
        self.shop_window.after(40, self._match_focus_to_shop_window)

    def _close_shop_window(self):
        if self.shop_window and self.shop_window.winfo_exists():
            self.shop_window.destroy()

        self.shop_window = None
        self.shop_canvas = None
        self.shop_canvas_window_id = None
        self.shop_grid_frame = None
        self.active_item_slot_index = None
        self.shop_name_search_var.set("")
        self.shop_detail_search_var.set("")
        self.shop_empty_var.set("")
        self._refresh_item_slot_labels()

    def _clear_shop_filters(self):
        self.shop_name_search_var.set("")
        self.shop_detail_search_var.set("")

    def _clear_active_shop_slot(self):
        if self.active_item_slot_index is None:
            return
        self.selected_items_vars[self.active_item_slot_index].set("")

    def _choose_shop_item(self, item_name):
        if self.active_item_slot_index is None:
            return

        self.selected_items_vars[self.active_item_slot_index].set(item_name)
        if self.active_item_slot_index < INVENTORY_SLOTS - 1:
            self.active_item_slot_index += 1

        self._refresh_item_slot_labels()
        self._update_shop_status()

    def _open_shop_window(self, slot_index):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        self.active_item_slot_index = slot_index
        self._refresh_item_slot_labels()
        self._update_shop_status()

        if self.shop_window and self.shop_window.winfo_exists():
            self._position_shop_window(self.item_slot_buttons[slot_index])
            self.shop_window.deiconify()
            self.shop_window.lift()
            self.shop_window.focus_set()
            return

        root = self.parent.winfo_toplevel()
        self.shop_window = tk.Toplevel(root)
        self.shop_window.title(self._shop_title_text())
        self.shop_window.transient(root)
        self.shop_window.resizable(True, True)
        self.shop_window.protocol("WM_DELETE_WINDOW", self._close_shop_window)
        self.shop_window.bind("<FocusOut>", self._handle_shop_focus_out)
        self.shop_window.bind("<Escape>", lambda _event: self._close_shop_window())

        shell = ttk.Frame(self.shop_window, padding=10)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="Item Shop", font=("Arial", 14, "bold")).pack(anchor="w")
        ttk.Label(shell, textvariable=self.shop_status_var, foreground="#666", wraplength=640).pack(
            anchor="w",
            pady=(4, 8),
        )

        search_row = ttk.Frame(shell)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="Item Name").grid(row=0, column=0, sticky="w")
        name_search_entry = ttk.Entry(search_row, textvariable=self.shop_name_search_var)
        name_search_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Label(search_row, text="Stat / Effect").grid(row=1, column=0, sticky="w", pady=(6, 0))
        detail_search_entry = ttk.Entry(search_row, textvariable=self.shop_detail_search_var)
        detail_search_entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(6, 0))
        ttk.Button(search_row, text="Clear Filters", command=self._clear_shop_filters).grid(
            row=0,
            column=2,
            rowspan=2,
            sticky="ns",
        )
        search_row.columnconfigure(1, weight=1)

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="Clear Active Slot", command=self._clear_active_shop_slot).pack(side="left")

        shop_body = ttk.Frame(shell)
        shop_body.pack(fill="both", expand=True)

        self.shop_canvas = tk.Canvas(shop_body, highlightthickness=0)
        shop_scrollbar = ttk.Scrollbar(shop_body, orient="vertical", command=self.shop_canvas.yview)
        self.shop_canvas.configure(yscrollcommand=shop_scrollbar.set)

        self.shop_canvas.pack(side="left", fill="both", expand=True)
        shop_scrollbar.pack(side="right", fill="y")

        self.shop_grid_frame = ttk.Frame(self.shop_canvas)
        self.shop_canvas_window_id = self.shop_canvas.create_window((0, 0), window=self.shop_grid_frame, anchor="nw")
        self.shop_grid_frame.bind("<Configure>", lambda _event: self._sync_shop_scroll_region())
        self.shop_canvas.bind(
            "<Configure>",
            lambda event: self.shop_canvas.itemconfigure(self.shop_canvas_window_id, width=event.width),
        )

        self._render_shop_items()

        self._position_shop_window(self.item_slot_buttons[slot_index])
        self.shop_window.lift()
        name_search_entry.focus_set()

    def _default_hero_state(self):
        return {
            "level": 1,
            "items": ["" for _ in range(INVENTORY_SLOTS)],
            "talents": {tier: "none" for tier in TALENT_TIERS},
        }

    def _copy_hero_state(self, state=None):
        source = state or self._default_hero_state()
        items = [str(item or "").strip() for item in list(source.get("items", []))[:INVENTORY_SLOTS]]
        if len(items) < INVENTORY_SLOTS:
            items.extend([""] * (INVENTORY_SLOTS - len(items)))

        talent_source = source.get("talents", {})
        if not isinstance(talent_source, dict):
            talent_source = {}

        return {
            "level": self._parse_level_value(source.get("level", 1)),
            "items": items,
            "talents": {
                tier: (
                    str(talent_source.get(tier, "none")).strip().lower()
                    if str(talent_source.get(tier, "none")).strip().lower() in {"none", "left", "right"}
                    else "none"
                )
                for tier in TALENT_TIERS
            },
        }

    def _initialize_hero_rows(self):
        self.hero_rows = {}
        self.row_sequence = 0
        for hero_name in self.hero_names:
            self._create_hero_row(hero_name, is_base=True)

    def _create_hero_row(self, hero_name, state=None, is_base=False):
        self.row_sequence += 1
        row_id = f"hero_row_{self.row_sequence}"
        self.hero_rows[row_id] = {
            "hero_name": hero_name,
            "state": self._copy_hero_state(state),
            "is_base": bool(is_base),
            "custom_label": "",
        }
        return row_id

    def _default_row_label(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            return "-"
        if row_entry.get("is_base"):
            return "Base"

        hero_name = row_entry["hero_name"]
        copy_number = 0
        for current_row_id, current_entry in self.hero_rows.items():
            if current_entry["hero_name"] != hero_name or current_entry.get("is_base"):
                continue
            copy_number += 1
            if current_row_id == row_id:
                return f"Copy {copy_number}"
        return "Copy"

    def _row_label(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            return "-"

        custom_label = str(row_entry.get("custom_label", "") or "").strip()
        if custom_label:
            return custom_label
        return self._default_row_label(row_id)

    def _refresh_selected_row_heading(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            self.selected_hero_var.set("Select a hero row from the table.")
            self.selected_hero_meta_var.set("")
            return

        hero_name = row_entry["hero_name"]
        hero_data = self.heroes.get(hero_name, {})
        primary_attribute = self._infer_primary_attribute(hero_name, hero_data)
        role_text = ", ".join(str(role) for role in hero_data.get("roles", []) if isinstance(role, str)) or "-"
        row_label = self._row_label(row_id)
        fallback_label = self._default_row_label(row_id)

        self.selected_hero_var.set(f"{hero_name} ({row_label})")
        if row_label != fallback_label:
            self.selected_hero_meta_var.set(
                f"Default: {fallback_label} • {ATTRIBUTE_DISPLAY.get(primary_attribute, '?')} primary • "
                f"{hero_data.get('attackType', 'Unknown')} • Roles: {role_text}"
            )
        else:
            self.selected_hero_meta_var.set(
                f"{row_label} • {ATTRIBUTE_DISPLAY.get(primary_attribute, '?')} primary • "
                f"{hero_data.get('attackType', 'Unknown')} • Roles: {role_text}"
            )

    def _update_row_action_state(self, row_id=None):
        if self.duplicate_row_button is None or self.remove_row_button is None:
            return

        row_entry = self.hero_rows.get(row_id) if row_id else None
        has_row = row_entry is not None
        self.duplicate_row_button.configure(state="normal" if has_row else "disabled")
        self.remove_row_button.configure(
            state="normal" if has_row and not row_entry.get("is_base") else "disabled"
        )

    def _match_hero_name(self, token):
        normalized = _normalize_match_text(token)
        compact = _normalize_compact_text(token)
        if not normalized and not compact:
            return None

        if normalized in self.hero_match_lookup:
            return self.hero_match_lookup[normalized]
        if compact in self.hero_compact_lookup:
            return self.hero_compact_lookup[compact]

        if normalized:
            close_normalized = get_close_matches(normalized, self.hero_match_choices, n=1, cutoff=0.72)
            if close_normalized:
                return self.hero_match_lookup[close_normalized[0]]

        if compact:
            close_compact = get_close_matches(compact, self.hero_compact_choices, n=1, cutoff=0.78)
            if close_compact:
                return self.hero_compact_lookup[close_compact[0]]

        return None

    def _apply_hero_pool(self):
        hero_names = []
        unmatched = []
        for token in _split_tokens(self.pool_input_var.get()):
            hero_name = self._match_hero_name(token)
            if hero_name:
                if hero_name not in hero_names:
                    hero_names.append(hero_name)
            else:
                unmatched.append(token)

        self.hero_pool_names = set(hero_names)
        if unmatched:
            self.pool_status_var.set(
                f"Hero pool: {len(hero_names)} matched hero(es). Unmatched: {', '.join(unmatched[:8])}"
            )
        elif hero_names:
            self.pool_status_var.set(f"Hero pool: {len(hero_names)} hero(es) loaded.")
        else:
            self.pool_status_var.set("Hero pool: none")
        self._refresh_table()

    def _set_pool_from_selection(self):
        selection = self.tree.selection()
        hero_names = [
            self.hero_rows[row_id]["hero_name"]
            for row_id in selection
            if row_id in self.hero_rows
        ]
        if not hero_names:
            self.pool_status_var.set("Hero pool: select one or more heroes from the table first.")
            return

        hero_names = sorted(dict.fromkeys(hero_names))
        self.hero_pool_names = set(hero_names)
        self.pool_input_var.set(", ".join(hero_names))
        self.pool_status_var.set(f"Hero pool: {len(hero_names)} hero(es) loaded from table selection.")
        self._refresh_table()

    def _clear_hero_pool(self):
        self.hero_pool_names.clear()
        self.pool_input_var.set("")
        self.pool_status_var.set("Hero pool: none")
        self._refresh_table()

    def _filtered_row_ids(self):
        query = self.search_var.get().strip().lower()
        visible_row_ids = []

        for row_id, row_entry in self.hero_rows.items():
            hero_name = row_entry["hero_name"]
            if self.use_pool_only_var.get() and self.hero_pool_names and hero_name not in self.hero_pool_names:
                continue

            hero_data = self.heroes.get(hero_name, {})
            haystack = " ".join(
                [
                    hero_name.lower(),
                    self._row_label(row_id).lower(),
                    str(hero_data.get("attackType", "")).lower(),
                    " ".join(str(role).lower() for role in hero_data.get("roles", []) if isinstance(role, str)),
                    str(hero_data.get("description", "")).lower(),
                ]
            )
            if query and query not in haystack:
                continue
            visible_row_ids.append(row_id)

        return visible_row_ids

    def _toggle_sort(self, column_id):
        if self.sort_column == column_id:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column_id
            self.sort_reverse = False
        self._refresh_table()

    def _sort_table_rows(self, rows):
        column_id = self.sort_column

        def sort_key(row):
            raw = row.get("_raw", {})
            if column_id in NUMERIC_COLUMNS:
                value = row.get(column_id) if column_id == "level" else raw.get(column_id, row.get(column_id))
                if isinstance(value, (int, float)):
                    return (0, float(value), row["hero"].lower())
                parsed_numeric = _to_float(value, default=None)
                if parsed_numeric is not None:
                    return (0, float(parsed_numeric), row["hero"].lower())
                return (1, str(value or "").lower(), row["hero"].lower())

            value = row.get(column_id)
            return (0, str(value or "").lower(), row["hero"].lower())

        rows.sort(key=sort_key, reverse=self.sort_reverse)

    def _refresh_table(self, refresh_editor=True):
        previous_selection = [iid for iid in self.tree.selection() if iid in self.hero_rows]
        current_focus = self.tree.focus()

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        visible_row_ids = self._filtered_row_ids()
        rows = [self._build_table_row(row_id) for row_id in visible_row_ids]
        self._sort_table_rows(rows)
        self.table_rows_by_id = {row["row_id"]: row for row in rows}

        for row in rows:
            values = [row.get(column_id, "") for column_id, _label, _width, _anchor in TABLE_COLUMNS]
            self.tree.insert("", "end", iid=row["row_id"], values=values)

        restored_selection = [row_id for row_id in previous_selection if row_id in self.table_rows_by_id]
        if restored_selection:
            self.tree.selection_set(restored_selection)
            focus_row_id = current_focus if current_focus in restored_selection else restored_selection[0]
            self.tree.focus(focus_row_id)
            self.tree.see(focus_row_id)
        elif self.current_selected_row_id and self.current_selected_row_id in self.table_rows_by_id:
            self.tree.selection_set(self.current_selected_row_id)
            self.tree.focus(self.current_selected_row_id)
            self.tree.see(self.current_selected_row_id)
        elif rows:
            self.tree.selection_set(rows[0]["row_id"])
            self.tree.focus(rows[0]["row_id"])
            self.tree.see(rows[0]["row_id"])

        visible_hero_count = len({row["hero"] for row in rows})
        extra_copy_count = max(0, len(self.hero_rows) - len(self.hero_names))
        self.summary_var.set(
            f"Showing {len(rows)} row(s) across {visible_hero_count} hero(es). "
            f"Total rows: {len(self.hero_rows)} with {extra_copy_count} extra copy row(s). "
            f"Sorted by {self.sort_column}{' desc' if self.sort_reverse else ' asc'}."
        )
        if refresh_editor:
            self._handle_tree_selection()

    def _handle_tree_selection(self, _event=None):
        selection = [iid for iid in self.tree.selection() if iid in self.hero_rows]
        if not selection:
            if self.current_selected_row_id and self.current_selected_row_id in self.hero_rows:
                self._populate_editor(self.current_selected_row_id)
            else:
                self.current_selected_row_id = None
                self._update_row_action_state(None)
            return

        focus_row_id = self.tree.focus()
        row_id = focus_row_id if focus_row_id in selection else selection[0]
        self.current_selected_row_id = row_id
        self._populate_editor(row_id)

    def _populate_editor(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            self.current_selected_row_id = None
            self._update_row_action_state(None)
            return

        hero_name = row_entry["hero_name"]
        state = row_entry["state"]
        self.loading_editor = True

        self._refresh_selected_row_heading(row_id)
        self.selected_row_name_var.set(str(row_entry.get("custom_label", "") or ""))
        self.selected_level_var.set(str(state["level"]))

        for index, item_var in enumerate(self.selected_items_vars):
            item_var.set(state["items"][index])

        hero_data = self.heroes.get(hero_name, {})
        for tier in TALENT_TIERS:
            selection = state["talents"].get(tier, "none")
            display_value = {
                "none": "None",
                "left": "Left",
                "right": "Right",
            }.get(selection, "None")
            self.selected_talent_vars[tier].set(display_value)
            self.talent_meta_labels[tier].configure(text=self._talent_option_summary(hero_data, tier))

        self.loading_editor = False
        self._update_row_action_state(row_id)
        self._refresh_selected_hero_summary(row_id)

    def _handle_row_name_change(self):
        if self.loading_editor or not self.current_selected_row_id:
            return

        row_entry = self.hero_rows.get(self.current_selected_row_id)
        if not row_entry:
            return

        row_entry["custom_label"] = str(self.selected_row_name_var.get() or "").strip()
        self._refresh_selected_row_heading(self.current_selected_row_id)
        self._update_shop_status()
        self._refresh_selected_hero_summary(self.current_selected_row_id)
        self._refresh_table(refresh_editor=False)

    def _talent_option_summary(self, hero_data, tier):
        tier_data = hero_data.get("talents", {}).get(tier, {})
        left_text = str(tier_data.get("left", "") or "").strip() or "-"
        right_text = str(tier_data.get("right", "") or "").strip() or "-"
        return f"Left: {left_text} | Right: {right_text}"

    def _handle_editor_change(self, *_args):
        if self.loading_editor or not self.current_selected_row_id:
            return

        row_entry = self.hero_rows.get(self.current_selected_row_id)
        if not row_entry:
            return

        state = row_entry["state"]
        state["level"] = self._parse_level_value(self.selected_level_var.get())
        state["items"] = [str(item_var.get()).strip() for item_var in self.selected_items_vars]
        state["talents"] = {
            tier: {
                "None": "none",
                "Left": "left",
                "Right": "right",
            }.get(self.selected_talent_vars[tier].get(), "none")
            for tier in TALENT_TIERS
        }

        self._refresh_selected_hero_summary(self.current_selected_row_id)
        self._refresh_table(refresh_editor=False)

    def _normalize_item_name(self, value):
        normalized = _normalize_choice(value, self.item_names)
        return normalized or ""

    def _parse_level_value(self, value):
        try:
            parsed = int(float(str(value or "").strip()))
        except ValueError:
            parsed = 1
        return max(1, min(MAX_LEVEL, parsed))

    def _adjust_selected_level(self, delta):
        if not self.current_selected_row_id:
            return
        current_level = self._parse_level_value(self.selected_level_var.get())
        self.selected_level_var.set(str(max(1, min(MAX_LEVEL, current_level + delta))))

    def _reset_selected_hero(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return
        self.hero_rows[self.current_selected_row_id]["state"] = self._default_hero_state()
        self._populate_editor(self.current_selected_row_id)
        self._refresh_table()

    def _reset_selected_row_name(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return
        self.selected_row_name_var.set("")

    def _clear_selected_items(self):
        if not self.current_selected_row_id:
            return
        for item_var in self.selected_items_vars:
            item_var.set("")

    def _duplicate_selected_row(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        source_entry = self.hero_rows[self.current_selected_row_id]
        new_row_id = self._create_hero_row(
            source_entry["hero_name"],
            state=copy.deepcopy(source_entry["state"]),
            is_base=False,
        )
        self.current_selected_row_id = new_row_id
        self._refresh_table()

    def _remove_selected_row(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        row_entry = self.hero_rows[self.current_selected_row_id]
        if row_entry.get("is_base"):
            return

        hero_name = row_entry["hero_name"]
        del self.hero_rows[self.current_selected_row_id]
        self.current_selected_row_id = next(
            (row_id for row_id, entry in self.hero_rows.items() if entry["hero_name"] == hero_name),
            None,
        )
        self._refresh_table()

    def _visible_row_ids_for_bulk(self):
        return list(self.table_rows_by_id.keys())

    def _adjust_visible_levels(self, delta):
        visible_row_ids = self._visible_row_ids_for_bulk()
        if not visible_row_ids:
            return

        for row_id in visible_row_ids:
            state = self.hero_rows[row_id]["state"]
            state["level"] = max(1, min(MAX_LEVEL, state["level"] + delta))

        if self.current_selected_row_id:
            self._populate_editor(self.current_selected_row_id)
        self._refresh_table()

    def _set_visible_levels(self):
        visible_row_ids = self._visible_row_ids_for_bulk()
        if not visible_row_ids:
            return

        level = self._parse_level_value(self.bulk_level_var.get())
        for row_id in visible_row_ids:
            state = self.hero_rows[row_id]["state"]
            state["level"] = level

        if self.current_selected_row_id:
            self._populate_editor(self.current_selected_row_id)
        self._refresh_table()

    def _build_table_row(self, row_id):
        row_entry = self.hero_rows[row_id]
        hero_name = row_entry["hero_name"]
        hero_data = self.heroes.get(hero_name, {})
        state = row_entry["state"]
        computed = self._compute_hero_stats(hero_name, hero_data, state)

        return {
            "row_id": row_id,
            "row_label": self._row_label(row_id),
            "hero": hero_name,
            "level": state["level"],
            "networth": _format_number(computed["networth"]),
            "primary_attribute": ATTRIBUTE_DISPLAY.get(computed["primary_attribute"], "?"),
            "attack_type": str(hero_data.get("attackType", "")),
            "roles": ", ".join(str(role) for role in hero_data.get("roles", []) if isinstance(role, str)),
            "strength": _format_number(computed["strength"]),
            "strength_gain": _format_number(computed["strength_gain"]),
            "agility": _format_number(computed["agility"]),
            "agility_gain": _format_number(computed["agility_gain"]),
            "intelligence": _format_number(computed["intelligence"]),
            "intelligence_gain": _format_number(computed["intelligence_gain"]),
            "health": _format_number(computed["health"]),
            "health_regen": _format_number(computed["health_regen"]),
            "mana": _format_number(computed["mana"]),
            "mana_regen": _format_number(computed["mana_regen"]),
            "armor": _format_number(computed["armor"]),
            "magic_resist": _format_percent_points(computed["magic_resist"]),
            "attack_damage": _format_number(computed["attack_damage"]),
            "attack_speed": _format_number(computed["attack_speed"]),
            "move_speed": _format_number(computed["move_speed"]),
            "attack_range": _format_number(computed["attack_range"]),
            "projectile_speed": _format_number(computed["projectile_speed"]),
            "bat": _format_number(computed["bat"]),
            "turn_rate": _format_number(computed["turn_rate"]),
            "talents": computed["talents_display"],
            "items": computed["items_display"],
            "_raw": computed,
        }

    def _infer_primary_attribute(self, hero_name, hero_data):
        explicit_candidates = [
            hero_data.get("primary_attribute"),
            hero_data.get("primaryAttribute"),
            hero_data.get("attribute_type"),
            hero_data.get("general", {}).get("primary_attribute") if isinstance(hero_data.get("general"), dict) else "",
        ]
        for candidate in explicit_candidates:
            normalized = self._normalize_primary_attribute(candidate)
            if normalized != "unknown":
                return normalized

        attribute_gains = hero_data.get("attributeGains", {})
        stat_gains = hero_data.get("statGains", {})
        main_attack_damage = stat_gains.get("mainAttackDamage")

        if main_attack_damage is not None:
            main_attack_damage = _to_float(main_attack_damage, default=None)
            if main_attack_damage is not None:
                strength_gain = _to_float(attribute_gains.get("strength"))
                agility_gain = _to_float(attribute_gains.get("agility"))
                intelligence_gain = _to_float(attribute_gains.get("intelligence"))
                universal_gain = 0.45 * (strength_gain + agility_gain + intelligence_gain)
                scores = {
                    "strength": abs(main_attack_damage - strength_gain),
                    "agility": abs(main_attack_damage - agility_gain),
                    "intelligence": abs(main_attack_damage - intelligence_gain),
                    "universal": abs(main_attack_damage - universal_gain),
                }
                return min(scores, key=scores.get)

        ranked_gains = sorted(
            [
                ("strength", _to_float(attribute_gains.get("strength"))),
                ("agility", _to_float(attribute_gains.get("agility"))),
                ("intelligence", _to_float(attribute_gains.get("intelligence"))),
            ],
            key=lambda item: (item[1], item[0]),
            reverse=True,
        )
        if ranked_gains and ranked_gains[0][1] > 0:
            return ranked_gains[0][0]
        return "unknown"

    def _normalize_primary_attribute(self, value):
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

    def _compute_hero_stats(self, hero_name, hero_data, state):
        level = state["level"]
        stats = hero_data.get("stats", {})
        attributes = hero_data.get("attributes", {})
        attribute_gains = hero_data.get("attributeGains", {})
        stat_gains = hero_data.get("statGains", {})
        primary_attribute = self._infer_primary_attribute(hero_name, hero_data)

        item_modifiers, selected_items = self._collect_state_item_modifiers(state)
        networth = sum(self._item_cost_value(item_name) for item_name in selected_items)
        talent_modifiers, selected_talent_codes, applied_talent_labels = self._collect_state_talent_modifiers(
            hero_data,
            state,
            level,
        )

        total_modifiers = _empty_modifiers()
        _merge_modifiers(total_modifiers, item_modifiers)
        _merge_modifiers(total_modifiers, talent_modifiers)

        strength_base = _to_float(attributes.get("strength"))
        agility_base = _to_float(attributes.get("agility"))
        intelligence_base = _to_float(attributes.get("intelligence"))
        strength_gain = _to_float(attribute_gains.get("strength"))
        agility_gain = _to_float(attribute_gains.get("agility"))
        intelligence_gain = _to_float(attribute_gains.get("intelligence"))
        level_factor = max(0, level - 1)

        strength = strength_base + (strength_gain * level_factor) + total_modifiers["strength"]
        agility = agility_base + (agility_gain * level_factor) + total_modifiers["agility"]
        intelligence = intelligence_base + (intelligence_gain * level_factor) + total_modifiers["intelligence"]

        health = _to_float(stats.get("health")) + (_to_float(stat_gains.get("health")) * level_factor)
        health += 22.0 * total_modifiers["strength"]
        health += total_modifiers["health_flat"]
        if total_modifiers["health_pct"]:
            health *= max(0.0, 1 + total_modifiers["health_pct"])

        health_regen = _to_float(stats.get("healthRegen")) + (_to_float(stat_gains.get("healthRegen")) * level_factor)
        health_regen += 0.1 * total_modifiers["strength"]
        health_regen += total_modifiers["health_regen_flat"]
        if total_modifiers["max_hp_regen_pct"]:
            health_regen += health * total_modifiers["max_hp_regen_pct"]

        mana = _to_float(stats.get("mana")) + (_to_float(stat_gains.get("mana")) * level_factor)
        mana += 12.0 * total_modifiers["intelligence"]
        mana += total_modifiers["mana_flat"]
        if total_modifiers["mana_pct"]:
            mana *= max(0.0, 1 + total_modifiers["mana_pct"])

        mana_regen = _to_float(stats.get("manaRegen")) + (_to_float(stat_gains.get("manaRegen")) * level_factor)
        mana_regen += 0.05 * total_modifiers["intelligence"]
        mana_regen += total_modifiers["mana_regen_flat"]

        armor = _to_float(stats.get("armor")) + (_to_float(stat_gains.get("armor")) * level_factor)
        armor += total_modifiers["agility"] / 6.0
        armor += total_modifiers["armor_flat"]

        magic_resist = _to_float(stats.get("magicResistance")) + (_to_float(stat_gains.get("magicResistance")) * level_factor)
        magic_resist += total_modifiers["magic_resist_flat"]

        base_damage = _to_float(stats.get("damageAverage"))
        base_damage += self._base_attack_damage_gain(hero_data, primary_attribute) * level_factor
        base_damage += self._bonus_attribute_damage(primary_attribute, total_modifiers)
        attack_damage = base_damage + total_modifiers["attack_damage_flat"]

        attack_speed = _to_float(stats.get("totalAttackSpeed", stats.get("attackSpeed")))
        attack_speed += _to_float(stat_gains.get("attackSpeed")) * level_factor
        attack_speed += total_modifiers["agility"]
        attack_speed += total_modifiers["attack_speed_flat"]
        if total_modifiers["attack_speed_pct"]:
            attack_speed *= max(0.0, 1 + total_modifiers["attack_speed_pct"])

        move_speed = _to_float(stats.get("moveSpeed")) + total_modifiers["move_speed_flat"]
        if total_modifiers["move_speed_pct"]:
            move_speed *= max(0.0, 1 + total_modifiers["move_speed_pct"])

        attack_range = _to_float(stats.get("attackRange")) + total_modifiers["attack_range_flat"]
        projectile_speed = stats.get("projectileSpeed")
        if isinstance(projectile_speed, (int, float)):
            projectile_speed = float(projectile_speed) + total_modifiers["projectile_speed_flat"]
        else:
            projectile_speed = str(projectile_speed or "")

        return {
            "primary_attribute": primary_attribute,
            "strength": strength,
            "strength_gain": strength_gain,
            "agility": agility,
            "agility_gain": agility_gain,
            "intelligence": intelligence,
            "intelligence_gain": intelligence_gain,
            "health": health,
            "health_regen": health_regen,
            "mana": mana,
            "mana_regen": mana_regen,
            "armor": armor,
            "magic_resist": magic_resist,
            "attack_damage": attack_damage,
            "attack_speed": attack_speed,
            "move_speed": move_speed,
            "attack_range": attack_range,
            "projectile_speed": projectile_speed,
            "bat": _to_float(stats.get("bat")),
            "turn_rate": _to_float(stats.get("turnRate")),
            "networth": networth,
            "talents_display": ", ".join(selected_talent_codes) if selected_talent_codes else "-",
            "items_display": ", ".join(selected_items) if selected_items else "-",
            "applied_talent_labels": applied_talent_labels,
            "selected_items": selected_items,
        }

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

    def _collect_state_item_modifiers(self, state):
        modifiers = _empty_modifiers()
        selected_items = []

        for item_name in state["items"]:
            normalized_name = self._normalize_item_name(item_name)
            if not normalized_name or normalized_name not in self.items:
                continue
            selected_items.append(normalized_name)
            _merge_modifiers(modifiers, self._get_item_modifiers(normalized_name))

        return modifiers, selected_items

    def _item_cost_value(self, item_name):
        if not item_name or item_name not in self.items:
            return 0.0

        item_data = self.items.get(item_name, {})
        parsed_cost = _to_float(item_data.get("cost"), default=None)
        if parsed_cost is None:
            return 0.0
        return parsed_cost

    def _get_item_modifiers(self, item_name):
        if item_name in self.item_modifier_cache:
            cached = self.item_modifier_cache[item_name]
            fresh = _empty_modifiers()
            _merge_modifiers(fresh, cached)
            return fresh

        item_data = self.items.get(item_name, {})
        modifiers = _empty_modifiers()
        has_explicit_stats = False

        stats_payload = item_data.get("stats")
        if isinstance(stats_payload, dict) and stats_payload:
            has_explicit_stats = self._apply_stats_payload(modifiers, stats_payload)

        if not has_explicit_stats:
            parsed_passive_modifiers = self._parse_item_passive_bonuses(item_data)
            if self._modifiers_have_value(parsed_passive_modifiers):
                _merge_modifiers(modifiers, parsed_passive_modifiers)
                if not self._passive_stats_are_complete(item_data):
                    self._merge_recipe_modifiers(modifiers, item_data.get("recipe"), seen={item_name})
            else:
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

    def _apply_stats_payload(self, modifiers, stats_payload):
        applied = False
        for stat_name, stat_value in stats_payload.items():
            if self._apply_named_stat_bonus(modifiers, stat_name, stat_value):
                applied = True
        return applied

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
        if normalized_name in {"mana"}:
            if is_percent:
                modifiers["mana_pct"] += value / 100.0
            else:
                modifiers["mana_flat"] += value
            return True
        if normalized_name in {"health regeneration", "health regen"}:
            modifiers["health_regen_flat"] += value
            return True
        if normalized_name in {"mana regeneration", "mana regen"}:
            modifiers["mana_regen_flat"] += value
            return True
        if normalized_name in {"armor", "bonus armor", "bonus magic resistance"}:
            if normalized_name in {"armor", "bonus armor"}:
                modifiers["armor_flat"] += value
            else:
                modifiers["magic_resist_flat"] += value
            return True
        if normalized_name in {"magic resistance"}:
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

    def _passive_stats_are_complete(self, item_data):
        abilities = item_data.get("abilities", [])
        if not isinstance(abilities, list):
            return False
        return any(
            str(ability.get("type", "")).strip().lower() == "passive"
            and str(ability.get("description", "") or "").strip().startswith("+")
            for ability in abilities
            if isinstance(ability, dict)
        )

    def _modifiers_have_value(self, modifiers):
        return any(abs(value) > 1e-9 for value in modifiers.values())

    def _collect_state_talent_modifiers(self, hero_data, state, level):
        modifiers = _empty_modifiers()
        selected_codes = []
        applied_labels = []
        talent_payload = hero_data.get("talents", {})

        for tier in TALENT_TIERS:
            selection = state["talents"].get(tier, "none")
            if selection not in {"left", "right"}:
                continue

            selected_codes.append(f"{tier}{selection[0].upper()}")
            if level < int(tier):
                continue

            label = str(talent_payload.get(tier, {}).get(selection, "") or "").strip()
            if not label:
                continue

            talent_modifiers, parsed_text = self._parse_talent_stat_bonus(label)
            if self._modifiers_have_value(talent_modifiers):
                _merge_modifiers(modifiers, talent_modifiers)
                applied_labels.append(parsed_text)

        return modifiers, selected_codes, applied_labels

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
        if "attack damage" in remainder or "attack damage bonus" in remainder:
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
        if self._is_direct_health_talent(remainder):
            if is_percent:
                modifiers["health_pct"] += value / 100.0
            else:
                modifiers["health_flat"] += value
            return modifiers, text
        if self._is_direct_mana_talent(remainder):
            if is_percent:
                modifiers["mana_pct"] += value / 100.0
            else:
                modifiers["mana_flat"] += value
            return modifiers, text
        if "attack range" in remainder:
            modifiers["attack_range_flat"] += value
            return modifiers, text

        return modifiers, ""

    def _is_direct_health_talent(self, remainder):
        if "health" not in remainder:
            return False
        if any(
            blocked in remainder
            for blocked in (
                "regen",
                "threshold",
                "restore",
                "restore amp",
                "health/damage",
                "max health as damage",
                "missing health",
                "kill threshold",
                "damage",
            )
        ):
            return False
        return remainder == "health" or remainder.endswith(" health") or "max health" in remainder

    def _is_direct_mana_talent(self, remainder):
        if "mana" not in remainder:
            return False
        if any(
            blocked in remainder
            for blocked in (
                "regen",
                "cost",
                "void",
                "shock",
                "break",
                "restore",
                "damage",
                "radius",
            )
        ):
            return False
        return remainder == "mana" or remainder.endswith(" mana") or "max mana" in remainder

    def _refresh_selected_hero_summary(self, row_id):
        if row_id not in self.hero_rows:
            self.selected_applied_summary_var.set("")
            return

        row = self._build_table_row(row_id)
        raw = row["_raw"]
        applied_talents = raw.get("applied_talent_labels", [])
        if applied_talents:
            applied_talent_text = "Applied stat talents: " + "; ".join(applied_talents)
        else:
            applied_talent_text = "Applied stat talents: none"

        self.selected_applied_summary_var.set(
            f"{row['row_label']} row current stats: {row['health']} HP, {row['mana']} Mana, {row['armor']} Armor, "
            f"{row['networth']} Networth, "
            f"{row['attack_damage']} Attack Damage, {row['attack_speed']} Attack Speed, {row['move_speed']} Move Speed.\n"
            f"{applied_talent_text}"
        )
