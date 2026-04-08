import copy
import json
import math
import os
import re
import tkinter as tk
import uuid
from datetime import datetime
from difflib import get_close_matches
from tkinter import ttk

from attack_calculations import (
    apply_magic_resistance,
    apply_physical_reduction,
    calculate_attack_rate,
    calculate_dps,
    calculate_hits_to_kill,
    calculate_time_to_kill,
)
from modifiers import Modifier
from utils import safe_eval


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

SETTINGS_FILENAME = "hero-core-table-settings.json"
TARGETS_FILENAME = "hero-core-targets.json"
TARGET_METRIC_COLUMN_IDS = [
    "target_damage_per_hit",
    "target_dps",
    "target_attacks_to_kill",
    "target_time_to_kill",
]
TARGET_SPELL_DAMAGE_TYPES = ("Physical", "Magical", "Pure")
HERO_CORE_MODIFIER_TYPES = tuple(
    modifier_type
    for modifier_type in (
        "Flat Damage",
        "Percentage Damage",
        "Strength",
        "Agility",
        "Intelligence",
        "Armor",
        "Magic Resistance",
        "Attack Speed",
        "BAT Reduction %",
        "HP",
        "Mana",
        "HP Regen Flat",
        "Mana Regen Flat",
        "Movespeed Flat",
        "Movespeed Percent",
    )
    if modifier_type in Modifier.get_available_types()
)
HERO_CORE_MODIFIER_TYPE_SET = set(HERO_CORE_MODIFIER_TYPES)

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
    ("damage_min", "Damage Min", 95, "e"),
    ("damage_max", "Damage Max", 95, "e"),
    ("attack_speed", "Attack Speed", 90, "e"),
    ("target_damage_per_hit", "Vs Dmg/Hit", 95, "e"),
    ("target_dps", "Vs DPS", 90, "e"),
    ("target_attacks_to_kill", "Vs Hits", 80, "e"),
    ("target_time_to_kill", "Vs TTK", 80, "e"),
    ("move_speed", "Move", 70, "e"),
    ("attack_range", "Range", 70, "e"),
    ("projectile_speed", "Projectile", 90, "e"),
    ("bat", "BAT", 60, "e"),
    ("animation_point", "Anim Point", 85, "e"),
    ("animation_backswing", "Backswing", 85, "e"),
    ("turn_rate", "Turn", 60, "e"),
    ("collision_size", "Collision", 85, "e"),
    ("vision_day", "Day Vision", 90, "e"),
    ("vision_night", "Night Vision", 95, "e"),
    ("talents", "Talents", 120, "w"),
    ("items", "Items", 260, "w"),
]

TABLE_COLUMN_IDS = [column_id for column_id, _label, _width, _anchor in TABLE_COLUMNS]
TABLE_COLUMN_ID_SET = set(TABLE_COLUMN_IDS)
DEFAULT_VISIBLE_COLUMNS = [
    column_id for column_id in TABLE_COLUMN_IDS
    if column_id not in TARGET_METRIC_COLUMN_IDS
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
    "damage_min",
    "damage_max",
    "attack_speed",
    "target_damage_per_hit",
    "target_dps",
    "target_attacks_to_kill",
    "target_time_to_kill",
    "move_speed",
    "attack_range",
    "projectile_speed",
    "bat",
    "animation_point",
    "animation_backswing",
    "turn_rate",
    "collision_size",
    "vision_day",
    "vision_night",
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


def _write_json_file(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


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


def _format_table_metric(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value

    numeric = float(value)
    if math.isnan(numeric):
        return ""
    if math.isinf(numeric):
        return "Inf"
    return _format_number(numeric)


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
        "bat_reduction_pct": 0.0,
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


def _normalize_visible_columns(value):
    if not isinstance(value, list):
        return list(DEFAULT_VISIBLE_COLUMNS)

    visible_columns = []
    seen = set()
    for raw_column_id in value:
        column_id = str(raw_column_id or "").strip()
        if column_id in TABLE_COLUMN_ID_SET and column_id not in seen:
            visible_columns.append(column_id)
            seen.add(column_id)

    return visible_columns or list(DEFAULT_VISIBLE_COLUMNS)


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    lowered = str(value or "").strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off", ""}:
        return False
    return default


class HeroCoreTableApp:
    def __init__(self, parent):
        self.parent = parent
        self.base_dir = os.path.dirname(__file__)
        self.dataset_path = os.path.join(self.base_dir, "dataset.json")
        self.settings_path = os.path.join(self.base_dir, SETTINGS_FILENAME)
        self.targets_path = os.path.join(self.base_dir, TARGETS_FILENAME)

        self.dataset_payload = _load_json_file(self.dataset_path, {"heroesCore": {}, "items": {}})
        self.settings_payload = self._load_settings()
        self.heroes = self._load_heroes()
        self.items = self._load_items()
        self.hero_names = sorted(self.heroes.keys())
        self.item_names = [""] + sorted(self.items.keys())
        self.item_shop_names = sorted(self.items.keys())
        self.saved_targets_data = self._load_saved_targets_data()
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
        self.suppress_tree_selection_events = False
        self.skip_editor_sync_row_id = None
        self.sort_column = "hero"
        self.sort_reverse = False
        self.hero_pool_names = set()
        self.visible_column_ids = _normalize_visible_columns(self.settings_payload.get("visibleColumns"))
        self.saved_targets = list(self.saved_targets_data.get("targets", []))
        self.active_saved_target_id = str(self.settings_payload.get("activeSavedTargetId", "") or "").strip()
        self.live_target_row_id = None
        self.saved_target_choice_to_id = {}
        self.saved_target_id_to_choice = {}

        self.search_var = tk.StringVar(value="")
        self.pool_input_var = tk.StringVar(value="")
        self.use_pool_only_var = tk.BooleanVar(value=False)
        self.bulk_level_var = tk.StringVar(value="1")
        self.summary_var = tk.StringVar(value="")
        self.pool_status_var = tk.StringVar(value="Hero pool: none")
        self.column_status_var = tk.StringVar(value="")
        self.column_picker_button_var = tk.StringVar(value="Choose Columns")
        self.target_name_var = tk.StringVar(value="")
        self.active_saved_target_choice_var = tk.StringVar(value="")
        self.target_editor_saved_target_choice_var = tk.StringVar(value="")
        self.active_target_status_var = tk.StringVar(value="")
        self.saved_target_editor_name_var = tk.StringVar(value="")
        self.saved_target_editor_hero_var = tk.StringVar(value="")
        self.saved_target_editor_level_var = tk.StringVar(value="1")
        self.saved_target_editor_items_vars = [tk.StringVar(value="") for _ in range(INVENTORY_SLOTS)]
        self.saved_target_item_display_vars = [tk.StringVar(value="Choose Item") for _ in range(INVENTORY_SLOTS)]
        self.saved_target_modifier_type_var = tk.StringVar(
            value=HERO_CORE_MODIFIER_TYPES[0] if HERO_CORE_MODIFIER_TYPES else ""
        )
        self.saved_target_spell_type_var = tk.StringVar(value=TARGET_SPELL_DAMAGE_TYPES[0])
        self.saved_target_editor_talent_vars = {
            tier: tk.StringVar(value="None")
            for tier in TALENT_TIERS
        }
        self.saved_target_editor_meta_var = tk.StringVar(value="Select a saved target to edit.")
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
        self.selected_modifier_type_var = tk.StringVar(
            value=HERO_CORE_MODIFIER_TYPES[0] if HERO_CORE_MODIFIER_TYPES else ""
        )
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
        self.selected_modifiers = []
        self.saved_target_modifiers = []
        self.saved_target_spell_rows = []
        self.talent_meta_labels = {}
        self.duplicate_row_button = None
        self.remove_row_button = None
        self.shop_window = None
        self.shop_canvas = None
        self.shop_canvas_window_id = None
        self.shop_grid_frame = None
        self.active_item_slot_index = None
        self.active_shop_owner = None
        self.tree = None
        self.column_picker_button = None
        self.column_picker_frame = None
        self.column_picker_visible = False
        self.column_visibility_vars = {}
        self.active_saved_target_combo = None
        self.target_editor_saved_target_combo = None
        self.clear_target_button = None
        self.delete_saved_target_button = None
        self.use_live_target_button = None
        self.save_target_button = None
        self.saved_target_name_entry = None
        self.saved_target_hero_combo = None
        self.saved_target_level_entry = None
        self.saved_target_item_buttons = []
        self.selected_modifiers_container = None
        self.saved_target_modifiers_container = None
        self.selected_modifier_combo = None
        self.saved_target_modifier_combo = None
        self.selected_modifier_add_button = None
        self.saved_target_modifier_add_button = None
        self.saved_target_spells_container = None
        self.saved_target_spell_type_combo = None
        self.saved_target_spell_add_button = None
        self.saved_target_talent_combos = {}
        self.update_saved_target_button = None
        self.refresh_saved_target_from_row_button = None

        self._initialize_hero_rows()

        self._build_ui()
        self._load_saved_target_into_editor(self._get_saved_target_by_id(self.active_saved_target_id))
        if self._active_target_snapshot():
            self._ensure_target_metric_columns_visible()
        self._bind_editor_vars()
        self._refresh_table()

    def _load_settings(self):
        payload = _load_json_file(
            self.settings_path,
            {
                "visibleColumns": list(DEFAULT_VISIBLE_COLUMNS),
                "activeSavedTargetId": "",
            },
        )
        if isinstance(payload, dict):
            return payload
        return {
            "visibleColumns": list(DEFAULT_VISIBLE_COLUMNS),
            "activeSavedTargetId": "",
        }

    def _save_settings(self):
        payload = {
            "visibleColumns": list(self.visible_column_ids),
            "activeSavedTargetId": str(getattr(self, "active_saved_target_id", "") or "").strip(),
        }
        self.settings_payload = payload
        _write_json_file(self.settings_path, payload)

    def _parse_target_items_display(self, items_display):
        items = []
        for token in _split_tokens(items_display):
            item_name = str(token or "").strip()
            if not item_name or item_name == "-":
                continue
            items.append(item_name)
        return items

    def _parse_target_talent_codes(self, talents_display):
        talents = {tier: "none" for tier in TALENT_TIERS}
        for token in _split_tokens(talents_display):
            match = re.match(r"^(10|15|20|25)\s*([lLrR])$", str(token or "").strip())
            if not match:
                continue
            talents[match.group(1)] = "left" if match.group(2).lower() == "l" else "right"
        return talents

    def _build_saved_target_state_from_record(self, record):
        state_source = record.get("state")
        if isinstance(state_source, dict):
            return self._copy_hero_state(state_source)

        items_source = record.get("items")
        if not isinstance(items_source, list):
            items_source = self._parse_target_items_display(record.get("items_display"))

        talents_source = record.get("talents")
        if not isinstance(talents_source, dict):
            talents_source = self._parse_target_talent_codes(record.get("talents_display"))

        return self._copy_hero_state(
            {
                "level": record.get("level", 1),
                "items": items_source,
                "talents": talents_source,
            }
        )

    def _normalize_target_spell_payload(self, spell_data):
        if not isinstance(spell_data, dict):
            return None

        damage_type = str(
            spell_data.get("damage_type")
            or spell_data.get("type")
            or TARGET_SPELL_DAMAGE_TYPES[0]
        ).strip().title()
        if damage_type == "Magic":
            damage_type = "Magical"
        if damage_type not in TARGET_SPELL_DAMAGE_TYPES:
            damage_type = TARGET_SPELL_DAMAGE_TYPES[0]

        return {
            "label": str(spell_data.get("label") or spell_data.get("name") or "").strip(),
            "damage": str(spell_data.get("damage") or spell_data.get("value") or "").strip(),
            "damage_type": damage_type,
            "enabled": _as_bool(spell_data.get("enabled"), default=True),
        }

    def _copy_target_spell_payloads(self, spells):
        if not isinstance(spells, list):
            return []

        normalized_spells = []
        for spell_data in spells:
            normalized_spell = self._normalize_target_spell_payload(spell_data)
            if normalized_spell:
                normalized_spells.append(normalized_spell)
        return normalized_spells

    def _normalize_saved_target_record(self, record):
        if not isinstance(record, dict):
            return None

        hero_name = _normalize_choice(record.get("hero_name"), self.hero_names)
        if not hero_name:
            return None

        state = self._build_saved_target_state_from_record(record)

        return {
            "id": str(record.get("id") or uuid.uuid4().hex),
            "name": str(record.get("name") or "Saved Target").strip() or "Saved Target",
            "hero_name": hero_name,
            "state": state,
            "incoming_spells": self._copy_target_spell_payloads(
                record.get("incoming_spells")
                if isinstance(record.get("incoming_spells"), list)
                else record.get("spells")
            ),
            "source_row_label": str(record.get("source_row_label") or record.get("row_label") or "").strip(),
            "saved_at": str(record.get("saved_at") or _timestamp()).strip() or _timestamp(),
        }

    def _load_saved_targets_data(self):
        payload = _load_json_file(self.targets_path, {"targets": []})
        source_targets = payload.get("targets", [])
        if not isinstance(source_targets, list):
            source_targets = []

        normalized_targets = []
        seen_ids = set()
        for record in source_targets:
            normalized = self._normalize_saved_target_record(record)
            if not normalized:
                continue
            if normalized["id"] in seen_ids:
                normalized["id"] = uuid.uuid4().hex
            seen_ids.add(normalized["id"])
            normalized_targets.append(normalized)

        normalized_payload = {"targets": normalized_targets}
        if normalized_payload != payload:
            _write_json_file(self.targets_path, normalized_payload)
        return normalized_payload

    def _save_saved_targets_data(self):
        payload = {"targets": list(self.saved_targets)}
        self.saved_targets_data = payload
        _write_json_file(self.targets_path, payload)

    def _ordered_visible_columns(self, visible_column_ids):
        visible_set = set(visible_column_ids)
        return [column_id for column_id in TABLE_COLUMN_IDS if column_id in visible_set]

    def _apply_visible_columns(self, save=True, note=None):
        self.visible_column_ids = _normalize_visible_columns(self._ordered_visible_columns(self.visible_column_ids))

        if self.tree is not None:
            self.tree.configure(displaycolumns=tuple(self.visible_column_ids))

        visible_set = set(self.visible_column_ids)
        for column_id, variable in self.column_visibility_vars.items():
            should_be_visible = column_id in visible_set
            if bool(variable.get()) != should_be_visible:
                variable.set(should_be_visible)

        if save:
            self._save_settings()

        total_columns = len(TABLE_COLUMNS)
        visible_columns = len(self.visible_column_ids)
        if self.column_picker_button is not None:
            prefix = "Hide Columns" if self.column_picker_visible else "Choose Columns"
            self.column_picker_button_var.set(f"{prefix} ({visible_columns}/{total_columns})")

        status_text = (
            f"Visible columns: {visible_columns}/{total_columns}. "
            f"Column picks save to {SETTINGS_FILENAME}."
        )
        if note:
            status_text = f"{note} {status_text}"
        self.column_status_var.set(status_text)

    def _toggle_column_visibility(self, column_id):
        variable = self.column_visibility_vars.get(column_id)
        if variable is None:
            return

        should_show = bool(variable.get())
        visible_set = set(self.visible_column_ids)

        if should_show:
            visible_set.add(column_id)
        else:
            if column_id in visible_set and len(visible_set) == 1:
                variable.set(True)
                self._apply_visible_columns(save=False, note="Keep at least one column visible.")
                return
            visible_set.discard(column_id)

        self.visible_column_ids = self._ordered_visible_columns(visible_set)
        self._apply_visible_columns()

    def _show_all_columns(self):
        self.visible_column_ids = list(TABLE_COLUMN_IDS)
        self._apply_visible_columns()

    def _reset_visible_columns(self):
        self.visible_column_ids = list(DEFAULT_VISIBLE_COLUMNS)
        self._apply_visible_columns()

    def _show_column_picker(self):
        if self.column_picker_frame is None:
            return

        self.column_picker_visible = True
        self.column_picker_frame.grid()
        self._apply_visible_columns(save=False)

    def _hide_column_picker(self):
        if self.column_picker_frame is None:
            return

        self.column_picker_visible = False
        self.column_picker_frame.grid_remove()
        self._apply_visible_columns(save=False)

    def _toggle_column_picker(self):
        if self.column_picker_visible:
            self._hide_column_picker()
        else:
            self._show_column_picker()

    def _build_column_picker(self, parent):
        self.column_visibility_vars = {}
        self.column_picker_frame = ttk.LabelFrame(parent, text="Visible Columns", padding=8)

        ttk.Label(
            self.column_picker_frame,
            text="Toggle any number of columns here. The picker stays open until you hide it.",
            foreground="#666",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=(0, 0), pady=(0, 8))

        checkbox_grid = ttk.Frame(self.column_picker_frame)
        checkbox_grid.grid(row=1, column=0, columnspan=4, sticky="ew")

        for index, (column_id, label, _width, _anchor) in enumerate(TABLE_COLUMNS):
            variable = tk.BooleanVar(value=column_id in self.visible_column_ids)
            self.column_visibility_vars[column_id] = variable
            ttk.Checkbutton(
                checkbox_grid,
                text=label,
                variable=variable,
                command=lambda current_column_id=column_id: self._toggle_column_visibility(current_column_id),
            ).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 18), pady=2)

        for column in range(4):
            checkbox_grid.columnconfigure(column, weight=1)

        actions = ttk.Frame(self.column_picker_frame)
        actions.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Button(actions, text="Show All Columns", command=self._show_all_columns).pack(side="left")
        ttk.Button(actions, text="Reset Defaults", command=self._reset_visible_columns).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Hide Picker", command=self._hide_column_picker).pack(side="left", padx=(8, 0))

        self.column_picker_frame.columnconfigure(0, weight=1)
        self.column_picker_frame.grid_remove()

    def _get_saved_target_by_id(self, target_id):
        target_key = str(target_id or "").strip()
        if not target_key:
            return None
        return next((target for target in self.saved_targets if target.get("id") == target_key), None)

    def _evaluate_target_spell(self, spell_payload, target_snapshot):
        normalized_spell = self._normalize_target_spell_payload(spell_payload)
        if not normalized_spell or not normalized_spell.get("enabled", True):
            return None

        raw_damage = safe_eval(normalized_spell.get("damage", ""), None)
        if raw_damage is None:
            return {
                "label": normalized_spell["label"],
                "damage": normalized_spell["damage"],
                "damage_type": normalized_spell["damage_type"],
                "raw_damage": None,
                "effective_damage": None,
            }

        raw_damage = float(raw_damage)
        damage_type = normalized_spell["damage_type"]
        if damage_type == "Physical":
            effective_damage = apply_physical_reduction(raw_damage, _to_float(target_snapshot.get("armor"), default=0.0))
        elif damage_type == "Magical":
            effective_damage = apply_magic_resistance(
                raw_damage,
                _to_float(target_snapshot.get("magic_resist"), default=0.0) / 100.0,
            )
        else:
            effective_damage = raw_damage

        return {
            "label": normalized_spell["label"],
            "damage": normalized_spell["damage"],
            "damage_type": damage_type,
            "raw_damage": raw_damage,
            "effective_damage": effective_damage,
        }

    def _evaluate_target_spells(self, spell_payloads, target_snapshot):
        entries = []
        total_raw_damage = 0.0
        total_effective_damage = 0.0

        for spell_payload in spell_payloads or []:
            entry = self._evaluate_target_spell(spell_payload, target_snapshot)
            if not entry:
                continue
            entries.append(entry)
            if entry["raw_damage"] is not None:
                total_raw_damage += entry["raw_damage"]
            if entry["effective_damage"] is not None:
                total_effective_damage += entry["effective_damage"]

        return {
            "incoming_spell_entries": entries,
            "incoming_spell_count": len(entries),
            "incoming_spell_raw_damage": total_raw_damage,
            "incoming_spell_effective_damage": total_effective_damage,
        }

    def _build_target_snapshot_from_template(self, target_record, source_type):
        if not isinstance(target_record, dict):
            return None

        hero_name = _normalize_choice(target_record.get("hero_name"), self.hero_names)
        if not hero_name or hero_name not in self.heroes:
            return None

        state = self._copy_hero_state(target_record.get("state"))
        incoming_spells = self._copy_target_spell_payloads(target_record.get("incoming_spells"))
        hero_data = self.heroes.get(hero_name, {})
        computed = self._compute_hero_stats(hero_name, hero_data, state)

        snapshot = {
            "id": str(target_record.get("id") or ""),
            "name": str(target_record.get("name") or "Saved Target").strip() or "Saved Target",
            "hero_name": hero_name,
            "row_label": str(target_record.get("source_row_label") or "").strip(),
            "level": state["level"],
            "health": computed["health"],
            "health_regen": computed["health_regen"],
            "armor": computed["armor"],
            "magic_resist": computed["magic_resist"],
            "evasion": 0.0,
            "items_display": computed["items_display"],
            "talents_display": computed["talents_display"],
            "state": state,
            "incoming_spells": incoming_spells,
            "saved_at": str(target_record.get("saved_at") or "").strip(),
            "_source_type": source_type,
        }
        spell_totals = self._evaluate_target_spells(incoming_spells, snapshot)
        snapshot.update(spell_totals)
        snapshot["remaining_health_after_spells"] = max(
            0.0,
            snapshot["health"] - snapshot["incoming_spell_effective_damage"],
        )
        return snapshot

    def _saved_target_choice_label(self, target):
        snapshot = self._build_target_snapshot_from_template(target, source_type="saved")
        if not snapshot:
            return str(target.get("name") or "Saved Target")
        return (
            f"{snapshot['name']} • {snapshot['hero_name']} Lv{snapshot['level']} • "
            f"{_format_number(snapshot['health'])} HP • {_format_number(snapshot['armor'])} Armor"
        )

    def _default_target_name_for_row(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            return "Saved Target"

        hero_name = row_entry["hero_name"]
        row_label = self._row_label(row_id)
        level = row_entry["state"]["level"]
        return f"{hero_name} ({row_label}) Lv{level}"

    def _build_target_snapshot_from_row(self, row_id):
        row_entry = self.hero_rows.get(row_id)
        if not row_entry:
            return None

        return self._build_target_snapshot_from_template(
            {
                "id": "",
                "name": self._default_target_name_for_row(row_id),
                "hero_name": row_entry["hero_name"],
                "state": row_entry["state"],
                "incoming_spells": [],
                "source_row_label": self._row_label(row_id),
                "saved_at": "",
            },
            source_type="live",
        )

    def _active_target_snapshot(self):
        if self.live_target_row_id:
            live_snapshot = self._build_target_snapshot_from_row(self.live_target_row_id)
            if live_snapshot:
                return live_snapshot
            self.live_target_row_id = None

        if self.active_saved_target_id:
            saved_target = self._get_saved_target_by_id(self.active_saved_target_id)
            if saved_target:
                return self._build_target_snapshot_from_template(saved_target, source_type="saved")
            self.active_saved_target_id = ""
            self._save_settings()

        return None

    def _refresh_saved_target_choices(self):
        self.saved_target_choice_to_id = {}
        self.saved_target_id_to_choice = {}
        values = []

        for target in self.saved_targets:
            base_label = self._saved_target_choice_label(target)
            label = base_label
            suffix = 2
            while label in self.saved_target_choice_to_id:
                label = f"{base_label} [{suffix}]"
                suffix += 1
            self.saved_target_choice_to_id[label] = target["id"]
            self.saved_target_id_to_choice[target["id"]] = label
            values.append(label)

        if self.active_saved_target_combo is not None:
            self.active_saved_target_combo.configure(values=values)
        if self.target_editor_saved_target_combo is not None:
            self.target_editor_saved_target_combo.configure(values=values)

        current_choice = self.saved_target_id_to_choice.get(self.active_saved_target_id, "")
        if self.active_saved_target_choice_var.get() != current_choice:
            self.active_saved_target_choice_var.set(current_choice)
        if self.target_editor_saved_target_choice_var.get() != current_choice:
            self.target_editor_saved_target_choice_var.set(current_choice)

    def _update_target_status(self, note=None):
        self._refresh_saved_target_choices()
        active_target = self._active_target_snapshot()
        active_saved_target = self._get_saved_target_by_id(self.active_saved_target_id)
        if active_saved_target is None:
            self._clear_saved_target_editor()

        if active_target:
            source_prefix = "Live target" if active_target.get("_source_type") == "live" else "Saved target"
            status_text = (
                f"{source_prefix}: {active_target['name']} • "
                f"{_format_number(active_target['health'])} HP • "
                f"{_format_number(active_target['health_regen'])} HP Regen • "
                f"{_format_number(active_target['armor'])} Armor • "
                f"{_format_number(active_target['magic_resist'])}% MR. "
                "Table target metrics use basic physical attacks."
            )
            if active_target.get("incoming_spell_count"):
                status_text += (
                    f" Incoming spells: {_format_number(active_target['incoming_spell_raw_damage'])} raw, "
                    f"{_format_number(active_target['incoming_spell_effective_damage'])} after reductions, "
                    f"{_format_number(active_target['remaining_health_after_spells'])} HP remaining."
                )
        else:
            status_text = (
                "No active target. Use the selected hero row as a live target or save a target template for reuse "
                f"in {TARGETS_FILENAME}."
            )

        if note:
            status_text = f"{note} {status_text}"
        self.active_target_status_var.set(status_text)

        if self.clear_target_button is not None:
            self.clear_target_button.configure(state="normal" if active_target else "disabled")
        if self.delete_saved_target_button is not None:
            self.delete_saved_target_button.configure(state="normal" if active_saved_target else "disabled")
        self._set_saved_target_editor_enabled(active_saved_target is not None)

    def _ensure_target_metric_columns_visible(self):
        if any(column_id in self.visible_column_ids for column_id in TARGET_METRIC_COLUMN_IDS):
            return

        self.visible_column_ids = self._ordered_visible_columns(
            list(self.visible_column_ids) + list(TARGET_METRIC_COLUMN_IDS)
        )
        self._apply_visible_columns(note="Target metrics added to the table.")

    def _activate_saved_target(self, target_id):
        target = self._get_saved_target_by_id(target_id)
        if not target:
            return

        self.active_saved_target_id = target["id"]
        self.live_target_row_id = None
        self._save_settings()
        self._ensure_target_metric_columns_visible()
        self._load_saved_target_into_editor(target)
        self._update_target_status()
        self._refresh_table(refresh_editor=False)

    def _handle_saved_target_selected(self, _event=None):
        target_id = self.saved_target_choice_to_id.get(self.active_saved_target_choice_var.get())
        if not target_id:
            return
        self._activate_saved_target(target_id)

    def _refresh_editor_from_selected_target(self):
        target_choice = str(self.target_editor_saved_target_choice_var.get() or "").strip()
        target_id = self.saved_target_choice_to_id.get(target_choice)
        if not target_id:
            target_id = self.active_saved_target_id
        if not target_id:
            self._update_target_status(note="Choose a saved target first.")
            return

        target = self._get_saved_target_by_id(target_id)
        if not target:
            self._update_target_status(note="Couldn't load that saved target.")
            return

        self._activate_saved_target(target_id)
        self._update_target_status(note=f"Loaded saved target '{target['name']}' into the editor.")

    def _use_selected_row_as_live_target(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        self.live_target_row_id = self.current_selected_row_id
        self.active_saved_target_id = ""
        self._save_settings()
        self._clear_saved_target_editor()
        self._ensure_target_metric_columns_visible()
        self._update_target_status(note="Using the selected row as a live target.")
        self._refresh_table(refresh_editor=False)

    def _save_selected_row_as_target(self):
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        row_entry = self.hero_rows.get(self.current_selected_row_id)
        if not row_entry:
            return

        target_name = str(self.target_name_var.get() or "").strip() or self._default_target_name_for_row(self.current_selected_row_id)
        record = self._normalize_saved_target_record(
            {
                "id": uuid.uuid4().hex,
                "name": target_name,
                "hero_name": row_entry["hero_name"],
                "state": row_entry["state"],
                "source_row_label": self._row_label(self.current_selected_row_id),
                "saved_at": _timestamp(),
            }
        )
        if not record:
            return

        self.saved_targets.append(record)
        self._save_saved_targets_data()
        self.target_name_var.set(record["name"])
        self._activate_saved_target(record["id"])
        self._update_target_status(note=f"Saved target '{record['name']}'.")

    def _clear_active_target(self):
        self.live_target_row_id = None
        self.active_saved_target_id = ""
        self._save_settings()
        if self.active_saved_target_choice_var.get():
            self.active_saved_target_choice_var.set("")
        self._clear_saved_target_editor()
        self._update_target_status(note="Cleared the active target.")
        self._refresh_table(refresh_editor=False)

    def _delete_active_saved_target(self):
        target = self._get_saved_target_by_id(self.active_saved_target_id)
        if not target:
            return

        self.saved_targets = [
            current_target for current_target in self.saved_targets
            if current_target.get("id") != target["id"]
        ]
        self._save_saved_targets_data()
        self.active_saved_target_id = ""
        self._save_settings()
        self._clear_saved_target_editor()
        self._update_target_status(note=f"Deleted saved target '{target['name']}'.")
        self._refresh_table(refresh_editor=False)

    def _set_saved_target_editor_enabled(self, enabled):
        entry_state = "normal" if enabled else "disabled"
        combo_state = "normal" if enabled else "disabled"
        talent_combo_state = "readonly" if enabled else "disabled"
        modifier_combo_state = "readonly" if enabled and HERO_CORE_MODIFIER_TYPES else "disabled"

        if self.saved_target_name_entry is not None:
            self.saved_target_name_entry.configure(state=entry_state)
        if self.saved_target_hero_combo is not None:
            self.saved_target_hero_combo.configure(state=combo_state)
        if self.saved_target_level_entry is not None:
            self.saved_target_level_entry.configure(state=entry_state)
        for button in self.saved_target_item_buttons:
            button.configure(state="normal" if enabled else "disabled")
        for combo in self.saved_target_talent_combos.values():
            combo.configure(state=talent_combo_state)
        if self.saved_target_modifier_combo is not None:
            self.saved_target_modifier_combo.configure(state=modifier_combo_state)
        if self.saved_target_modifier_add_button is not None:
            self.saved_target_modifier_add_button.configure(state="normal" if enabled else "disabled")
        if self.saved_target_spell_type_combo is not None:
            self.saved_target_spell_type_combo.configure(state="readonly" if enabled else "disabled")
        if self.saved_target_spell_add_button is not None:
            self.saved_target_spell_add_button.configure(state="normal" if enabled else "disabled")

        if self.update_saved_target_button is not None:
            self.update_saved_target_button.configure(state="normal" if enabled else "disabled")
        if self.refresh_saved_target_from_row_button is not None:
            row_available = enabled and self.current_selected_row_id in self.hero_rows if self.current_selected_row_id else False
            self.refresh_saved_target_from_row_button.configure(state="normal" if row_available else "disabled")

    def _load_saved_target_into_editor(self, target):
        if not target:
            self._clear_saved_target_editor()
            return

        state = self._copy_hero_state(target.get("state"))
        snapshot = self._build_target_snapshot_from_template(target, source_type="saved")

        self.saved_target_editor_name_var.set(str(target.get("name") or ""))
        self.saved_target_editor_hero_var.set(str(target.get("hero_name") or ""))
        self.saved_target_editor_level_var.set(str(state["level"]))
        for index, item_var in enumerate(self.saved_target_editor_items_vars):
            item_var.set(state["items"][index])
        self._refresh_item_slot_labels()
        for tier in TALENT_TIERS:
            self.saved_target_editor_talent_vars[tier].set(
                {
                    "none": "None",
                    "left": "Left",
                    "right": "Right",
                }.get(state["talents"].get(tier, "none"), "None")
            )
        self._load_modifier_widgets(
            state.get("modifiers", []),
            self.saved_target_modifiers_container,
            self.saved_target_modifiers,
            self._on_saved_target_modifier_changed,
            self._delete_saved_target_modifier,
        )
        self._load_saved_target_spell_rows(target.get("incoming_spells", []))
        hero_name = str(target.get("hero_name") or "-")
        source_row_label = str(target.get("source_row_label") or "-")
        saved_at = str(target.get("saved_at") or "-")
        items_text = snapshot["items_display"] if snapshot else "-"
        talents_text = snapshot["talents_display"] if snapshot else "-"
        modifiers_text = self._modifier_payloads_summary_text(state.get("modifiers", []))
        spell_text = (
            f"{_format_number(snapshot['incoming_spell_raw_damage'])} raw -> "
            f"{_format_number(snapshot['incoming_spell_effective_damage'])} effective"
            if snapshot and snapshot.get("incoming_spell_count")
            else "-"
        )
        stats_text = (
            f"Current stats: {_format_number(snapshot['health'])} HP, "
            f"{_format_number(snapshot['health_regen'])} Regen, "
            f"{_format_number(snapshot['armor'])} Armor, "
            f"{_format_number(snapshot['magic_resist'])}% MR"
            if snapshot
            else "Current stats unavailable."
        )
        self.saved_target_editor_meta_var.set(
            f"Template: {hero_name} ({source_row_label}) Lv{state['level']} • Saved {saved_at}\n"
            f"Items: {items_text}\n"
            f"Talents: {talents_text}\n"
            f"Modifiers: {modifiers_text}\n"
            f"Incoming spells: {spell_text}\n"
            f"{stats_text}"
        )

    def _clear_saved_target_editor(self):
        self.saved_target_editor_name_var.set("")
        self.saved_target_editor_hero_var.set("")
        self.saved_target_editor_level_var.set("1")
        for item_var in self.saved_target_editor_items_vars:
            item_var.set("")
        self._refresh_item_slot_labels()
        for talent_var in self.saved_target_editor_talent_vars.values():
            talent_var.set("None")
        self._load_modifier_widgets([], self.saved_target_modifiers_container, self.saved_target_modifiers, self._on_saved_target_modifier_changed, self._delete_saved_target_modifier)
        self._load_saved_target_spell_rows([])
        self.saved_target_editor_meta_var.set("Select a saved target to edit.")

    def _add_selected_modifier(self):
        if not self.selected_modifiers_container or not HERO_CORE_MODIFIER_TYPES:
            return

        type_name = str(self.selected_modifier_type_var.get() or "").strip()
        if not type_name:
            return

        mod = Modifier.create(
            type_name,
            self.selected_modifiers_container,
            self._on_selected_modifier_changed,
            self._delete_selected_modifier,
        )
        if not mod:
            return

        mod.pack(fill="x", pady=2)
        self.selected_modifiers.append(mod)
        self._on_selected_modifier_changed()

    def _delete_selected_modifier(self, mod):
        if mod not in self.selected_modifiers:
            return
        self.selected_modifiers.remove(mod)
        mod.destroy()
        self._on_selected_modifier_changed()

    def _on_selected_modifier_changed(self):
        for mod in self.selected_modifiers:
            mod.update_display()

        if self.loading_editor or not self.current_selected_row_id:
            return

        row_entry = self.hero_rows.get(self.current_selected_row_id)
        if not row_entry:
            return

        row_entry["state"]["modifiers"] = self._serialize_modifier_widgets(self.selected_modifiers)
        self._refresh_selected_hero_summary(self.current_selected_row_id)
        row_ids_to_refresh = (
            list(self.table_rows_by_id.keys())
            if self.current_selected_row_id == self.live_target_row_id
            else [self.current_selected_row_id]
        )
        self._refresh_tree_rows_in_place(row_ids_to_refresh)

    def _add_saved_target_modifier(self):
        if not self.saved_target_modifiers_container or not HERO_CORE_MODIFIER_TYPES:
            return
        if not self._get_saved_target_by_id(self.active_saved_target_id):
            return

        type_name = str(self.saved_target_modifier_type_var.get() or "").strip()
        if not type_name:
            return

        mod = Modifier.create(
            type_name,
            self.saved_target_modifiers_container,
            self._on_saved_target_modifier_changed,
            self._delete_saved_target_modifier,
        )
        if not mod:
            return

        mod.pack(fill="x", pady=2)
        self.saved_target_modifiers.append(mod)
        self._on_saved_target_modifier_changed()

    def _delete_saved_target_modifier(self, mod):
        if mod not in self.saved_target_modifiers:
            return
        self.saved_target_modifiers.remove(mod)
        mod.destroy()
        self._on_saved_target_modifier_changed()

    def _on_saved_target_modifier_changed(self):
        for mod in self.saved_target_modifiers:
            mod.update_display()
        self._refresh_saved_target_spell_rows()

    def _save_saved_target_edits(self):
        target = self._get_saved_target_by_id(self.active_saved_target_id)
        if not target:
            self._update_target_status(note="Pick a saved target before editing.")
            return

        name = str(self.saved_target_editor_name_var.get() or "").strip() or target["name"]
        hero_name = _normalize_choice(self.saved_target_editor_hero_var.get(), self.hero_names)
        if not hero_name:
            self._update_target_status(note="Choose a valid target hero.")
            return

        state = self._current_saved_target_editor_state()
        incoming_spells = self._serialize_saved_target_spell_rows()

        target.update(
            {
                "name": name,
                "hero_name": hero_name,
                "state": state,
                "incoming_spells": incoming_spells,
                "source_row_label": "Template",
                "saved_at": _timestamp(),
            }
        )
        self._save_saved_targets_data()
        self._load_saved_target_into_editor(target)
        self._refresh_saved_target_choices()
        self._update_target_status(note=f"Updated saved target '{target['name']}'.")
        self._refresh_table(refresh_editor=False)

    def _load_selected_row_into_saved_target_editor(self):
        target = self._get_saved_target_by_id(self.active_saved_target_id)
        if not target:
            self._update_target_status(note="Pick a saved target before loading a row into the editor.")
            return
        if not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            self._update_target_status(note="Select a hero row before loading it into the editor.")
            return

        row_entry = self.hero_rows.get(self.current_selected_row_id)
        if not row_entry:
            self._update_target_status(note="Couldn't read the selected row.")
            return

        state = self._copy_hero_state(row_entry["state"])
        self.saved_target_editor_name_var.set(
            str(self.saved_target_editor_name_var.get() or "").strip() or target["name"]
        )
        self.saved_target_editor_hero_var.set(row_entry["hero_name"])
        self.saved_target_editor_level_var.set(str(state["level"]))
        for index, item_var in enumerate(self.saved_target_editor_items_vars):
            item_var.set(state["items"][index])
        self._refresh_item_slot_labels()
        for tier in TALENT_TIERS:
            self.saved_target_editor_talent_vars[tier].set(
                {
                    "none": "None",
                    "left": "Left",
                    "right": "Right",
                }.get(state["talents"].get(tier, "none"), "None")
            )
        self._load_modifier_widgets(
            state.get("modifiers", []),
            self.saved_target_modifiers_container,
            self.saved_target_modifiers,
            self._on_saved_target_modifier_changed,
            self._delete_saved_target_modifier,
        )
        self._refresh_saved_target_spell_rows()

        source_row_label = self._row_label(self.current_selected_row_id)
        row_snapshot = self._current_saved_target_editor_snapshot()
        items_text = row_snapshot["items_display"] if row_snapshot else "-"
        talents_text = row_snapshot["talents_display"] if row_snapshot else "-"
        modifiers_text = self._modifier_payloads_summary_text(state.get("modifiers", []))
        spell_text = (
            f"{_format_number(row_snapshot['incoming_spell_raw_damage'])} raw -> "
            f"{_format_number(row_snapshot['incoming_spell_effective_damage'])} effective"
            if row_snapshot and row_snapshot.get("incoming_spell_count")
            else "-"
        )
        stats_text = (
            f"Draft from selected row: {row_entry['hero_name']} ({source_row_label}) Lv{state['level']}\n"
            f"Items: {items_text}\n"
            f"Talents: {talents_text}\n"
            f"Modifiers: {modifiers_text}\n"
            f"Incoming spells: {spell_text}\n"
            f"Current stats: {_format_number(row_snapshot['health'])} HP, "
            f"{_format_number(row_snapshot['health_regen'])} Regen, "
            f"{_format_number(row_snapshot['armor'])} Armor, "
            f"{_format_number(row_snapshot['magic_resist'])}% MR\n"
            "This is only loaded into the editor until you save."
            if row_snapshot
            else "Draft loaded from selected row. This is only loaded into the editor until you save."
        )
        self.saved_target_editor_meta_var.set(stats_text)
        self._update_target_status(
            note=f"Loaded {row_entry['hero_name']} ({source_row_label}) into the editor. Save to overwrite '{target['name']}'."
        )

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

    def _build_scrollable_editor_tab(self, parent):
        shell = ttk.Frame(parent)
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        content = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        return content

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

        ttk.Label(controls, text="Columns").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.column_picker_button = ttk.Button(
            controls,
            textvariable=self.column_picker_button_var,
            command=self._toggle_column_picker,
        )
        self.column_picker_button.grid(row=2, column=1, sticky="w", padx=(6, 12), pady=(8, 0))
        ttk.Button(controls, text="Show All Columns", command=self._show_all_columns).grid(
            row=2,
            column=2,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Label(controls, textvariable=self.column_status_var, foreground="#666").grid(
            row=2,
            column=3,
            columnspan=4,
            sticky="w",
            padx=(6, 0),
            pady=(8, 0),
        )
        self._build_column_picker(controls)
        self.column_picker_frame.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(10, 0))
        self.column_picker_frame.grid_remove()

        ttk.Label(controls, text="Saved Target").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.active_saved_target_combo = ttk.Combobox(
            controls,
            textvariable=self.active_saved_target_choice_var,
            state="readonly",
            width=42,
        )
        self.active_saved_target_combo.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(6, 12), pady=(10, 0))
        self.active_saved_target_combo.bind("<<ComboboxSelected>>", self._handle_saved_target_selected)
        self.clear_target_button = ttk.Button(
            controls,
            text="Clear Target",
            command=self._clear_active_target,
        )
        self.clear_target_button.grid(row=4, column=3, sticky="w", pady=(10, 0))
        self.delete_saved_target_button = ttk.Button(
            controls,
            text="Delete Saved Target",
            command=self._delete_active_saved_target,
        )
        self.delete_saved_target_button.grid(row=4, column=4, columnspan=2, sticky="w", padx=(6, 0), pady=(10, 0))
        ttk.Label(
            controls,
            textvariable=self.active_target_status_var,
            foreground="#666",
            wraplength=1150,
            justify="left",
        ).grid(row=5, column=0, columnspan=7, sticky="w", pady=(8, 0))

        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
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

        self.tree = ttk.Treeview(tree_container, columns=TABLE_COLUMN_IDS, show="headings", selectmode="extended")
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
        self._apply_visible_columns(save=False)
        self._update_target_status()

        editor_notebook = ttk.Notebook(editor_frame)
        editor_notebook.pack(fill="both", expand=True)

        selected_tab = ttk.Frame(editor_notebook)
        target_tab = ttk.Frame(editor_notebook)
        editor_notebook.add(selected_tab, text="Selected Hero")
        editor_notebook.add(target_tab, text="Target Tools")
        selected_tab_content = self._build_scrollable_editor_tab(selected_tab)
        target_tab_content = self._build_scrollable_editor_tab(target_tab)

        editor_card = ttk.LabelFrame(selected_tab_content, text="Selected Hero")
        editor_card.pack(fill="both", expand=True, padx=(0, 4), pady=(0, 8))

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
                command=lambda slot_index=index: self._open_shop_window(slot_index, owner="selected"),
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

        selected_modifiers_frame = ttk.LabelFrame(editor_card, text="Modifiers")
        selected_modifiers_frame.pack(fill="x", padx=10, pady=(0, 10))
        selected_modifiers_header = ttk.Frame(selected_modifiers_frame)
        selected_modifiers_header.pack(fill="x", padx=8, pady=(8, 6))
        ttk.Label(selected_modifiers_header, text="Type").pack(side="left")
        self.selected_modifier_combo = ttk.Combobox(
            selected_modifiers_header,
            textvariable=self.selected_modifier_type_var,
            values=HERO_CORE_MODIFIER_TYPES,
            state="readonly" if HERO_CORE_MODIFIER_TYPES else "disabled",
            width=24,
        )
        self.selected_modifier_combo.pack(side="left", padx=(8, 8))
        self.selected_modifier_add_button = ttk.Button(
            selected_modifiers_header,
            text="+ Add Modifier",
            command=self._add_selected_modifier,
            state="normal" if HERO_CORE_MODIFIER_TYPES else "disabled",
        )
        self.selected_modifier_add_button.pack(side="left")
        self.selected_modifiers_container = ttk.Frame(selected_modifiers_frame)
        self.selected_modifiers_container.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(
            selected_modifiers_frame,
            text="Custom stat and attack-damage modifiers apply to this row build immediately.",
            foreground="#666",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 8))

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

        target_card = ttk.LabelFrame(target_tab_content, text="Target Tools")
        target_card.pack(fill="both", expand=True, padx=(0, 4), pady=(0, 8))

        ttk.Label(
            target_card,
            text=(
                "Use the selected hero row as a live target, or save it as a reusable target template and edit the build here."
            ),
            foreground="#666",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 10))

        target_picker_row = ttk.Frame(target_card)
        target_picker_row.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(target_picker_row, text="Saved Target").pack(side="left")
        self.target_editor_saved_target_combo = ttk.Combobox(
            target_picker_row,
            textvariable=self.target_editor_saved_target_choice_var,
            state="readonly",
            width=36,
        )
        self.target_editor_saved_target_combo.pack(side="left", fill="x", expand=True, padx=(8, 8))
        ttk.Button(
            target_picker_row,
            text="Load Selected Target",
            command=self._refresh_editor_from_selected_target,
        ).pack(side="left")

        target_name_row = ttk.Frame(target_card)
        target_name_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(target_name_row, text="Saved Target Name").pack(side="left")
        ttk.Entry(target_name_row, textvariable=self.target_name_var).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(8, 8),
        )

        target_actions = ttk.Frame(target_card)
        target_actions.pack(fill="x", padx=10, pady=(0, 10))
        self.use_live_target_button = ttk.Button(
            target_actions,
            text="Use Selected Row As Live Target",
            command=self._use_selected_row_as_live_target,
            state="disabled",
        )
        self.use_live_target_button.pack(side="left")
        self.save_target_button = ttk.Button(
            target_actions,
            text="Save Selected Row As Target",
            command=self._save_selected_row_as_target,
            state="disabled",
        )
        self.save_target_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            target_card,
            text=(
                "Live targets update when that row changes. Saved target templates persist across sessions and can be "
                "picked from the Saved Target control above."
            ),
            foreground="#666",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

        saved_target_editor_frame = ttk.LabelFrame(target_card, text="Edit Active Saved Target")
        saved_target_editor_frame.pack(fill="x", padx=10, pady=(0, 10))

        editor_grid = ttk.Frame(saved_target_editor_frame)
        editor_grid.pack(fill="x", padx=8, pady=(8, 6))
        ttk.Label(editor_grid, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.saved_target_name_entry = ttk.Entry(editor_grid, textvariable=self.saved_target_editor_name_var)
        self.saved_target_name_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(editor_grid, text="Hero").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.saved_target_hero_combo = ttk.Combobox(
            editor_grid,
            textvariable=self.saved_target_editor_hero_var,
            values=self.hero_names,
            state="normal",
            width=22,
        )
        self.saved_target_hero_combo.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(editor_grid, text="Level").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
        self.saved_target_level_entry = ttk.Entry(editor_grid, textvariable=self.saved_target_editor_level_var, width=12)
        self.saved_target_level_entry.grid(row=1, column=3, sticky="w", pady=4)

        editor_grid.columnconfigure(1, weight=1)
        editor_grid.columnconfigure(3, weight=1)

        saved_target_items_frame = ttk.LabelFrame(saved_target_editor_frame, text="Items")
        saved_target_items_frame.pack(fill="x", padx=8, pady=(0, 6))
        self.saved_target_item_buttons = []
        for index, _item_var in enumerate(self.saved_target_editor_items_vars):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(saved_target_items_frame, text=f"Slot {index + 1}").grid(
                row=row,
                column=column,
                sticky="w",
                padx=(8, 6),
                pady=6,
            )
            button = ttk.Button(
                saved_target_items_frame,
                textvariable=self.saved_target_item_display_vars[index],
                command=lambda slot_index=index: self._open_shop_window(slot_index, owner="target"),
                width=28,
            )
            button.grid(row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=6)
            self.saved_target_item_buttons.append(button)

        saved_target_items_frame.columnconfigure(1, weight=1)
        saved_target_items_frame.columnconfigure(3, weight=1)
        ttk.Label(
            saved_target_items_frame,
            text="Click a slot to open the same item shop used by the selected hero editor.",
            foreground="#666",
            wraplength=520,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 8))

        saved_target_talents_frame = ttk.LabelFrame(saved_target_editor_frame, text="Talents")
        saved_target_talents_frame.pack(fill="x", padx=8, pady=(0, 6))
        self.saved_target_talent_combos = {}
        for index, tier in enumerate(TALENT_TIERS):
            row = index // 2
            column = (index % 2) * 2
            ttk.Label(saved_target_talents_frame, text=f"Level {tier}").grid(
                row=row,
                column=column,
                sticky="w",
                padx=(8, 8),
                pady=6,
            )
            combo = ttk.Combobox(
                saved_target_talents_frame,
                textvariable=self.saved_target_editor_talent_vars[tier],
                values=TALENT_CHOICES,
                state="readonly",
                width=10,
            )
            combo.grid(row=row, column=column + 1, sticky="w", padx=(0, 12), pady=6)
            self.saved_target_talent_combos[tier] = combo

        saved_target_talents_frame.columnconfigure(1, weight=1)
        saved_target_talents_frame.columnconfigure(3, weight=1)

        saved_target_modifiers_frame = ttk.LabelFrame(saved_target_editor_frame, text="Modifiers")
        saved_target_modifiers_frame.pack(fill="x", padx=8, pady=(0, 6))
        saved_target_modifiers_header = ttk.Frame(saved_target_modifiers_frame)
        saved_target_modifiers_header.pack(fill="x", padx=8, pady=(8, 6))
        ttk.Label(saved_target_modifiers_header, text="Type").pack(side="left")
        self.saved_target_modifier_combo = ttk.Combobox(
            saved_target_modifiers_header,
            textvariable=self.saved_target_modifier_type_var,
            values=HERO_CORE_MODIFIER_TYPES,
            state="readonly" if HERO_CORE_MODIFIER_TYPES else "disabled",
            width=24,
        )
        self.saved_target_modifier_combo.pack(side="left", padx=(8, 8))
        self.saved_target_modifier_add_button = ttk.Button(
            saved_target_modifiers_header,
            text="+ Add Modifier",
            command=self._add_saved_target_modifier,
            state="normal" if HERO_CORE_MODIFIER_TYPES else "disabled",
        )
        self.saved_target_modifier_add_button.pack(side="left")
        self.saved_target_modifiers_container = ttk.Frame(saved_target_modifiers_frame)
        self.saved_target_modifiers_container.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(
            saved_target_modifiers_frame,
            text="These modifiers stay in the editor draft until you save the target template.",
            foreground="#666",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        saved_target_spells_frame = ttk.LabelFrame(saved_target_editor_frame, text="Spells Cast On Target")
        saved_target_spells_frame.pack(fill="x", padx=8, pady=(0, 6))
        saved_target_spells_header = ttk.Frame(saved_target_spells_frame)
        saved_target_spells_header.pack(fill="x", padx=8, pady=(8, 6))
        ttk.Label(saved_target_spells_header, text="Damage Type").pack(side="left")
        self.saved_target_spell_type_combo = ttk.Combobox(
            saved_target_spells_header,
            textvariable=self.saved_target_spell_type_var,
            values=TARGET_SPELL_DAMAGE_TYPES,
            state="readonly",
            width=12,
        )
        self.saved_target_spell_type_combo.pack(side="left", padx=(8, 8))
        self.saved_target_spell_add_button = ttk.Button(
            saved_target_spells_header,
            text="+ Add Spell",
            command=self._add_saved_target_spell_row,
        )
        self.saved_target_spell_add_button.pack(side="left")
        self.saved_target_spells_container = ttk.Frame(saved_target_spells_frame)
        self.saved_target_spells_container.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(
            saved_target_spells_frame,
            text=(
                "Use expressions like 4.5*25 or (300+150)/2. "
                "Physical uses armor, Magical uses magic resist, and Pure ignores reductions."
            ),
            foreground="#666",
            wraplength=520,
        ).pack(anchor="w", padx=8, pady=(0, 8))

        saved_target_editor_actions = ttk.Frame(saved_target_editor_frame)
        saved_target_editor_actions.pack(fill="x", padx=8, pady=(0, 6))
        self.update_saved_target_button = ttk.Button(
            saved_target_editor_actions,
            text="Save Template Changes",
            command=self._save_saved_target_edits,
            state="disabled",
        )
        self.update_saved_target_button.pack(side="left")
        self.refresh_saved_target_from_row_button = ttk.Button(
            saved_target_editor_actions,
            text="Load Selected Row Into Editor",
            command=self._load_selected_row_into_saved_target_editor,
            state="disabled",
        )
        self.refresh_saved_target_from_row_button.pack(side="left", padx=(8, 0))
        ttk.Label(
            saved_target_editor_frame,
            textvariable=self.saved_target_editor_meta_var,
            foreground="#666",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 8))

        self.search_var.trace_add("write", lambda *_args: self._refresh_table())

    def _bind_editor_vars(self):
        self.selected_row_name_var.trace_add("write", lambda *_args: self._handle_row_name_change())
        self.selected_level_var.trace_add("write", lambda *_args: self._handle_editor_change())
        for item_var in self.selected_items_vars:
            item_var.trace_add("write", lambda *_args: self._handle_item_slot_var_change())
        for talent_var in self.selected_talent_vars.values():
            talent_var.trace_add("write", lambda *_args: self._handle_editor_change())
        self.saved_target_editor_hero_var.trace_add("write", self._handle_saved_target_editor_draft_change)
        self.saved_target_editor_level_var.trace_add("write", self._handle_saved_target_editor_draft_change)
        for item_var in self.saved_target_editor_items_vars:
            item_var.trace_add("write", lambda *_args: self._handle_target_item_slot_var_change())
        for talent_var in self.saved_target_editor_talent_vars.values():
            talent_var.trace_add("write", self._handle_saved_target_editor_draft_change)

    def _handle_item_slot_var_change(self):
        self._refresh_item_slot_labels()
        if not self.loading_editor:
            self._handle_editor_change()

    def _handle_target_item_slot_var_change(self):
        self._refresh_item_slot_labels()
        if not self.loading_editor:
            self._refresh_saved_target_spell_rows()

    def _handle_saved_target_editor_draft_change(self, *_args):
        if not self.loading_editor:
            self._refresh_saved_target_spell_rows()

    def _shop_item_vars(self, owner):
        if owner == "target":
            return self.saved_target_editor_items_vars
        return self.selected_items_vars

    def _shop_item_display_vars(self, owner):
        if owner == "target":
            return self.saved_target_item_display_vars
        return self.selected_item_display_vars

    def _shop_item_buttons(self, owner):
        if owner == "target":
            return self.saved_target_item_buttons
        return self.item_slot_buttons

    def _refresh_item_slot_labels(self):
        for owner in ("selected", "target"):
            item_vars = self._shop_item_vars(owner)
            display_vars = self._shop_item_display_vars(owner)
            for index, item_var in enumerate(item_vars):
                item_name = str(item_var.get()).strip()
                display_text = item_name or "Choose Item"
                if (
                    self.shop_window
                    and self.active_shop_owner == owner
                    and self.active_item_slot_index == index
                ):
                    display_text = f"[Active] {display_text}"
                display_vars[index].set(display_text)

    def _shop_title_text(self):
        if self.active_item_slot_index is None:
            return "Item Shop"

        if self.active_shop_owner == "target":
            target = self._get_saved_target_by_id(self.active_saved_target_id)
            if not target:
                return "Item Shop"
            return (
                f"Item Shop - {target.get('name') or 'Saved Target'} "
                f"({target.get('hero_name') or '-'}) Slot {self.active_item_slot_index + 1}"
            )

        if self.current_selected_row_id not in self.hero_rows:
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
        if self.active_item_slot_index is None:
            self.shop_status_var.set("Select an item slot.")
            return

        if self.active_shop_owner == "target":
            target = self._get_saved_target_by_id(self.active_saved_target_id)
            if not target:
                self.shop_status_var.set("Select a saved target and item slot.")
                return
            self.shop_status_var.set(
                f"Choosing an item for saved target {target.get('name') or 'Saved Target'} "
                f"slot {self.active_item_slot_index + 1}. Click an item to fill the slot, "
                "then keep picking for the next slot. Click outside the shop or use X to close it."
            )
        elif self.current_selected_row_id in self.hero_rows:
            row_entry = self.hero_rows[self.current_selected_row_id]
            hero_name = row_entry["hero_name"]
            row_label = self._row_label(self.current_selected_row_id)
            self.shop_status_var.set(
                f"Choosing an item for {hero_name} ({row_label}) slot {self.active_item_slot_index + 1}. "
                "Click an item to fill the slot, then keep picking for the next slot. "
                "Click outside the shop or use X to close it."
            )
        else:
            self.shop_status_var.set("Select a hero row or saved target and item slot.")
            return

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
        self.active_shop_owner = None
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
        item_vars = self._shop_item_vars(self.active_shop_owner)
        item_vars[self.active_item_slot_index].set("")
        if self.active_shop_owner == "target":
            self._refresh_item_slot_labels()

    def _choose_shop_item(self, item_name):
        if self.active_item_slot_index is None:
            return

        item_vars = self._shop_item_vars(self.active_shop_owner)
        item_vars[self.active_item_slot_index].set(item_name)
        if self.active_item_slot_index < INVENTORY_SLOTS - 1:
            self.active_item_slot_index += 1

        self._refresh_item_slot_labels()
        self._update_shop_status()

    def _open_shop_window(self, slot_index, owner="selected"):
        if owner == "target":
            if not self._get_saved_target_by_id(self.active_saved_target_id):
                return
        elif not self.current_selected_row_id or self.current_selected_row_id not in self.hero_rows:
            return

        self.active_shop_owner = owner
        self.active_item_slot_index = slot_index
        self._refresh_item_slot_labels()
        self._update_shop_status()
        anchor_buttons = self._shop_item_buttons(owner)
        anchor_widget = anchor_buttons[slot_index] if slot_index < len(anchor_buttons) else None

        if self.shop_window and self.shop_window.winfo_exists():
            self._position_shop_window(anchor_widget)
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

        self._position_shop_window(anchor_widget)
        self.shop_window.lift()
        name_search_entry.focus_set()

    def _default_hero_state(self):
        return {
            "level": 1,
            "items": ["" for _ in range(INVENTORY_SLOTS)],
            "talents": {tier: "none" for tier in TALENT_TIERS},
            "modifiers": [],
        }

    def _normalize_modifier_payload(self, modifier_data):
        if not isinstance(modifier_data, dict):
            return None

        type_name = str(modifier_data.get("type") or "").strip()
        if type_name not in HERO_CORE_MODIFIER_TYPE_SET:
            return None

        values = modifier_data.get("values", {})
        if not isinstance(values, dict):
            values = {}

        normalized_values = {}
        for key, value in values.items():
            key_text = str(key or "").strip()
            if not key_text.endswith("_var"):
                continue
            if isinstance(value, bool):
                normalized_values[key_text] = value
            else:
                normalized_values[key_text] = str(value)

        return {
            "type": type_name,
            "values": normalized_values,
        }

    def _copy_hero_state(self, state=None):
        source = state or self._default_hero_state()
        items = [str(item or "").strip() for item in list(source.get("items", []))[:INVENTORY_SLOTS]]
        if len(items) < INVENTORY_SLOTS:
            items.extend([""] * (INVENTORY_SLOTS - len(items)))

        talent_source = source.get("talents", {})
        if not isinstance(talent_source, dict):
            talent_source = {}

        modifier_source = source.get("modifiers", [])
        if not isinstance(modifier_source, list):
            modifier_source = []

        normalized_modifiers = []
        for modifier_data in modifier_source:
            normalized_modifier = self._normalize_modifier_payload(modifier_data)
            if normalized_modifier:
                normalized_modifiers.append(normalized_modifier)

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
            "modifiers": normalized_modifiers,
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

    def _serialize_modifier_widget(self, mod):
        values = {}
        for key, value in mod.__dict__.items():
            if key.endswith("_var") and hasattr(value, "get"):
                values[key] = value.get()
        return self._normalize_modifier_payload(
            {
                "type": getattr(mod, "TYPE_NAME", ""),
                "values": values,
            }
        )

    def _serialize_modifier_widgets(self, modifiers):
        payloads = []
        for mod in modifiers:
            serialized = self._serialize_modifier_widget(mod)
            if serialized:
                payloads.append(serialized)
        return payloads

    def _destroy_modifier_widgets(self, modifiers):
        for mod in modifiers[:]:
            mod.destroy()
        modifiers.clear()

    def _load_modifier_widgets(self, modifier_payloads, parent, destination, on_change, on_delete):
        self._destroy_modifier_widgets(destination)
        if parent is None:
            return

        for modifier_data in modifier_payloads or []:
            normalized_modifier = self._normalize_modifier_payload(modifier_data)
            if not normalized_modifier:
                continue

            mod = Modifier.create(
                normalized_modifier["type"],
                parent,
                on_change,
                on_delete,
            )
            if not mod:
                continue

            for key, value in normalized_modifier.get("values", {}).items():
                variable = getattr(mod, key, None)
                if hasattr(variable, "set"):
                    variable.set(value)

            mod.pack(fill="x", pady=2)
            destination.append(mod)
            mod.update_display()

    def _modifier_payload_enabled(self, modifier_payload):
        values = modifier_payload.get("values", {})
        return _as_bool(values.get("enabled_var"), default=True)

    def _modifier_payload_label(self, modifier_payload):
        values = modifier_payload.get("values", {})
        return str(values.get("label_var") or modifier_payload.get("type") or "Modifier").strip() or "Modifier"

    def _modifier_payload_value(self, modifier_payload, key="value_var", default=0.0):
        values = modifier_payload.get("values", {})
        raw_value = values.get(key, "")
        parsed = safe_eval(str(raw_value or ""), None)
        return default if parsed is None else float(parsed)

    def _modifier_payloads_summary_text(self, modifier_payloads):
        labels = [
            self._modifier_payload_label(modifier_payload)
            for modifier_payload in modifier_payloads
            if self._modifier_payload_enabled(modifier_payload)
        ]
        return ", ".join(labels) if labels else "-"

    def _current_saved_target_editor_state(self):
        return self._copy_hero_state(
            {
                "level": self.saved_target_editor_level_var.get(),
                "items": [str(item_var.get()).strip() for item_var in self.saved_target_editor_items_vars],
                "talents": {
                    tier: {
                        "None": "none",
                        "Left": "left",
                        "Right": "right",
                    }.get(self.saved_target_editor_talent_vars[tier].get(), "none")
                    for tier in TALENT_TIERS
                },
                "modifiers": self._serialize_modifier_widgets(self.saved_target_modifiers),
            }
        )

    def _serialize_saved_target_spell_rows(self):
        payloads = []
        for row in self.saved_target_spell_rows:
            payload = self._normalize_target_spell_payload(
                {
                    "label": row["label_var"].get(),
                    "damage": row["damage_var"].get(),
                    "damage_type": row["type_var"].get(),
                    "enabled": row["enabled_var"].get(),
                }
            )
            if payload:
                payloads.append(payload)
        return payloads

    def _current_saved_target_editor_snapshot(self):
        hero_name = _normalize_choice(self.saved_target_editor_hero_var.get(), self.hero_names)
        if not hero_name:
            return None

        return self._build_target_snapshot_from_template(
            {
                "id": self.active_saved_target_id,
                "name": str(self.saved_target_editor_name_var.get() or "").strip() or "Saved Target",
                "hero_name": hero_name,
                "state": self._current_saved_target_editor_state(),
                "incoming_spells": self._serialize_saved_target_spell_rows(),
                "source_row_label": "Editor Draft",
                "saved_at": "",
            },
            source_type="editor",
        )

    def _destroy_saved_target_spell_rows(self):
        for row in self.saved_target_spell_rows[:]:
            row["frame"].destroy()
        self.saved_target_spell_rows.clear()

    def _refresh_saved_target_spell_rows(self):
        snapshot = self._current_saved_target_editor_snapshot()
        for row in self.saved_target_spell_rows:
            evaluation = self._evaluate_target_spell(
                {
                    "label": row["label_var"].get(),
                    "damage": row["damage_var"].get(),
                    "damage_type": row["type_var"].get(),
                    "enabled": row["enabled_var"].get(),
                },
                snapshot or {
                    "armor": 0.0,
                    "magic_resist": 0.0,
                },
            )
            if not evaluation:
                row["result_var"].set("(disabled)")
                continue
            if evaluation["raw_damage"] is None:
                row["result_var"].set("Invalid")
                continue
            row["result_var"].set(
                f"{_format_number(evaluation['raw_damage'])} raw -> "
                f"{_format_number(evaluation['effective_damage'])} eff"
            )

    def _on_saved_target_spell_changed(self, *_args):
        self._refresh_saved_target_spell_rows()

    def _add_saved_target_spell_row(self, spell_payload=None):
        if self.saved_target_spells_container is None:
            return

        normalized_spell = self._normalize_target_spell_payload(spell_payload or {})
        if not normalized_spell:
            normalized_spell = {
                "label": "",
                "damage": "",
                "damage_type": str(self.saved_target_spell_type_var.get() or TARGET_SPELL_DAMAGE_TYPES[0]),
                "enabled": True,
            }

        frame = ttk.Frame(self.saved_target_spells_container)
        frame.pack(fill="x", pady=2)

        enabled_var = tk.BooleanVar(value=normalized_spell["enabled"])
        label_var = tk.StringVar(value=normalized_spell["label"])
        type_var = tk.StringVar(value=normalized_spell["damage_type"])
        damage_var = tk.StringVar(value=normalized_spell["damage"])
        result_var = tk.StringVar(value="")

        ttk.Checkbutton(frame, variable=enabled_var).pack(side="left", padx=(0, 4))
        ttk.Entry(frame, textvariable=label_var, width=14).pack(side="left", padx=(0, 6))
        ttk.Combobox(
            frame,
            textvariable=type_var,
            values=TARGET_SPELL_DAMAGE_TYPES,
            state="readonly",
            width=10,
        ).pack(side="left", padx=(0, 6))
        ttk.Entry(frame, textvariable=damage_var, width=12).pack(side="left", padx=(0, 6))
        ttk.Label(frame, textvariable=result_var, foreground="#666", width=24).pack(side="left", padx=(0, 6))
        ttk.Button(
            frame,
            text="X",
            width=2,
            command=lambda: self._delete_saved_target_spell_row(spell_row),
        ).pack(side="right")

        spell_row = {
            "frame": frame,
            "enabled_var": enabled_var,
            "label_var": label_var,
            "type_var": type_var,
            "damage_var": damage_var,
            "result_var": result_var,
        }
        self.saved_target_spell_rows.append(spell_row)

        for variable in (enabled_var, label_var, type_var, damage_var):
            variable.trace_add("write", self._on_saved_target_spell_changed)

        self._refresh_saved_target_spell_rows()

    def _delete_saved_target_spell_row(self, spell_row):
        if spell_row not in self.saved_target_spell_rows:
            return
        self.saved_target_spell_rows.remove(spell_row)
        spell_row["frame"].destroy()
        self._refresh_saved_target_spell_rows()

    def _load_saved_target_spell_rows(self, spell_payloads):
        self._destroy_saved_target_spell_rows()
        for spell_payload in spell_payloads or []:
            self._add_saved_target_spell_row(spell_payload)
        self._refresh_saved_target_spell_rows()

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
        if self.use_live_target_button is not None:
            self.use_live_target_button.configure(state="normal" if has_row else "disabled")
        if self.save_target_button is not None:
            self.save_target_button.configure(state="normal" if has_row else "disabled")
        if self.refresh_saved_target_from_row_button is not None:
            has_saved_target = self._get_saved_target_by_id(self.active_saved_target_id) is not None
            self.refresh_saved_target_from_row_button.configure(
                state="normal" if has_row and has_saved_target else "disabled"
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
        focus_state = self._capture_focus_state() if not refresh_editor else None
        self.skip_editor_sync_row_id = self.current_selected_row_id if not refresh_editor else None
        previous_selection = [iid for iid in self.tree.selection() if iid in self.hero_rows]
        current_focus = self.tree.focus()
        active_target_snapshot = self._active_target_snapshot()

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        visible_row_ids = self._filtered_row_ids()
        rows = [self._build_table_row(row_id, active_target_snapshot) for row_id in visible_row_ids]
        self._sort_table_rows(rows)
        self.table_rows_by_id = {row["row_id"]: row for row in rows}

        for row in rows:
            values = [row.get(column_id, "") for column_id, _label, _width, _anchor in TABLE_COLUMNS]
            self.tree.insert("", "end", iid=row["row_id"], values=values)

        self.suppress_tree_selection_events = True
        try:
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
        finally:
            self.suppress_tree_selection_events = False

        visible_hero_count = len({row["hero"] for row in rows})
        extra_copy_count = max(0, len(self.hero_rows) - len(self.hero_names))
        self.summary_var.set(
            f"Showing {len(rows)} row(s) across {visible_hero_count} hero(es). "
            f"Total rows: {len(self.hero_rows)} with {extra_copy_count} extra copy row(s). "
            f"Sorted by {self.sort_column}{' desc' if self.sort_reverse else ' asc'}. "
            f"Active target: {active_target_snapshot['name'] if active_target_snapshot else 'none'}."
        )
        self._update_target_status()
        if refresh_editor:
            self._handle_tree_selection()
        elif focus_state is not None:
            self.parent.after_idle(lambda state=focus_state: self._restore_focus_state(state))

    def _refresh_tree_rows_in_place(self, row_ids):
        if self.tree is None:
            return

        active_target_snapshot = self._active_target_snapshot()
        for row_id in row_ids or []:
            if row_id not in self.hero_rows or not self.tree.exists(row_id):
                continue

            row = self._build_table_row(row_id, active_target_snapshot)
            self.table_rows_by_id[row_id] = row
            values = [row.get(column_id, "") for column_id, _label, _width, _anchor in TABLE_COLUMNS]
            self.tree.item(row_id, values=values)

        self._update_target_status()

    def _handle_tree_selection(self, _event=None):
        if self.suppress_tree_selection_events:
            return
        selection = [iid for iid in self.tree.selection() if iid in self.hero_rows]
        if self.skip_editor_sync_row_id:
            if not selection:
                return
            focus_row_id = self.tree.focus()
            row_id = focus_row_id if focus_row_id in selection else (selection[0] if selection else None)
            skipped_row_id = self.skip_editor_sync_row_id
            self.skip_editor_sync_row_id = None
            if row_id and row_id == skipped_row_id:
                self.current_selected_row_id = row_id
                self._update_row_action_state(row_id)
                return
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

    def _capture_focus_state(self):
        focus_widget = self.parent.focus_get()
        if focus_widget is None or focus_widget == self.tree:
            return None

        focus_state = {"widget_path": str(focus_widget)}
        try:
            focus_state["insert_index"] = focus_widget.index(tk.INSERT)
        except (AttributeError, tk.TclError):
            pass
        try:
            if focus_widget.selection_present():
                focus_state["selection_range"] = (
                    focus_widget.index(tk.SEL_FIRST),
                    focus_widget.index(tk.SEL_LAST),
                )
        except (AttributeError, tk.TclError):
            pass
        return focus_state

    def _restore_focus_state(self, focus_state):
        if not focus_state:
            return

        try:
            widget = self.parent.nametowidget(focus_state["widget_path"])
        except (KeyError, AttributeError, tk.TclError):
            return

        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            widget.focus_set()
        except tk.TclError:
            return

        insert_index = focus_state.get("insert_index")
        if insert_index is not None:
            try:
                widget.icursor(insert_index)
            except (AttributeError, tk.TclError):
                pass

        selection_range = focus_state.get("selection_range")
        if selection_range is not None:
            try:
                widget.selection_range(*selection_range)
            except (AttributeError, tk.TclError):
                pass

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
        self.target_name_var.set(self._default_target_name_for_row(row_id))

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
        self._load_modifier_widgets(
            state.get("modifiers", []),
            self.selected_modifiers_container,
            self.selected_modifiers,
            self._on_selected_modifier_changed,
            self._delete_selected_modifier,
        )

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

    def _build_table_row(self, row_id, active_target_snapshot=None):
        row_entry = self.hero_rows[row_id]
        hero_name = row_entry["hero_name"]
        hero_data = self.heroes.get(hero_name, {})
        state = row_entry["state"]
        computed = self._compute_hero_stats(hero_name, hero_data, state)
        computed.update(self._compute_target_metrics(computed, active_target_snapshot))

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
            "damage_min": _format_number(computed["damage_min"]),
            "damage_max": _format_number(computed["damage_max"]),
            "attack_speed": _format_number(computed["attack_speed"]),
            "target_damage_per_hit": _format_table_metric(computed["target_damage_per_hit"]),
            "target_dps": _format_table_metric(computed["target_dps"]),
            "target_attacks_to_kill": _format_table_metric(computed["target_attacks_to_kill"]),
            "target_time_to_kill": _format_table_metric(computed["target_time_to_kill"]),
            "move_speed": _format_number(computed["move_speed"]),
            "attack_range": _format_number(computed["attack_range"]),
            "projectile_speed": _format_number(computed["projectile_speed"]),
            "bat": _format_number(computed["bat"]),
            "animation_point": _format_number(computed["animation_point"]),
            "animation_backswing": _format_number(computed["animation_backswing"]),
            "turn_rate": _format_number(computed["turn_rate"]),
            "collision_size": _format_number(computed["collision_size"]),
            "vision_day": _format_number(computed["vision_day"]),
            "vision_night": _format_number(computed["vision_night"]),
            "talents": computed["talents_display"],
            "items": computed["items_display"],
            "_raw": computed,
        }

    def _compute_target_metrics(self, computed, target_snapshot):
        metrics = {
            "target_damage_per_hit": None,
            "target_dps": None,
            "target_attacks_to_kill": None,
            "target_time_to_kill": None,
            "target_name": target_snapshot.get("name") if target_snapshot else "",
            "incoming_spell_raw_damage": target_snapshot.get("incoming_spell_raw_damage", 0.0) if target_snapshot else 0.0,
            "incoming_spell_effective_damage": target_snapshot.get("incoming_spell_effective_damage", 0.0) if target_snapshot else 0.0,
            "remaining_health_after_spells": target_snapshot.get("remaining_health_after_spells", 0.0) if target_snapshot else 0.0,
        }
        if not target_snapshot:
            return metrics

        attack_speed = _to_float(computed.get("attack_speed"), default=0.0)
        bat = _to_float(computed.get("bat"), default=0.0)
        attack_rate = calculate_attack_rate(attack_speed, bat)

        raw_attack_damage = _to_float(computed.get("attack_damage"), default=0.0)
        target_armor = _to_float(target_snapshot.get("armor"), default=0.0)
        evasion = max(0.0, _to_float(target_snapshot.get("evasion"), default=0.0)) / 100.0
        target_health = _to_float(target_snapshot.get("health"), default=None)
        target_regen = _to_float(target_snapshot.get("health_regen"), default=0.0)
        incoming_spell_damage = _to_float(target_snapshot.get("incoming_spell_effective_damage"), default=0.0)

        reduced_damage = apply_physical_reduction(raw_attack_damage, target_armor)
        reduced_damage *= max(0.0, 1.0 - evasion)

        metrics["target_damage_per_hit"] = reduced_damage
        metrics["target_dps"] = calculate_dps(reduced_damage, attack_rate)

        if target_health is not None and target_health > 0:
            remaining_health = max(0.0, target_health - incoming_spell_damage)
            if remaining_health <= 0:
                metrics["target_attacks_to_kill"] = 0
                metrics["target_time_to_kill"] = 0
                return metrics
            metrics["target_attacks_to_kill"] = calculate_hits_to_kill(
                remaining_health,
                reduced_damage,
                target_regen,
                attack_rate,
            )
            metrics["target_time_to_kill"] = calculate_time_to_kill(
                remaining_health,
                reduced_damage,
                attack_rate,
                target_regen,
            )

        return metrics

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

    def _collect_state_custom_modifiers(self, state):
        modifiers = _empty_modifiers()
        damage_modifiers = []
        active_labels = []

        for modifier_payload in state.get("modifiers", []):
            normalized_modifier = self._normalize_modifier_payload(modifier_payload)
            if not normalized_modifier or not self._modifier_payload_enabled(normalized_modifier):
                continue

            type_name = normalized_modifier["type"]
            label = self._modifier_payload_label(normalized_modifier)
            value = self._modifier_payload_value(normalized_modifier)

            if type_name == "Flat Damage":
                if abs(value) > 1e-9:
                    damage_modifiers.append({"kind": "flat", "value": value})
                    active_labels.append(label)
                continue

            if type_name == "Percentage Damage":
                pct = value / 100.0
                if abs(pct) > 1e-9:
                    damage_modifiers.append(
                        {
                            "kind": "pct",
                            "value": pct,
                            "apply_to_total": _as_bool(
                                normalized_modifier.get("values", {}).get("apply_to_total_var"),
                                default=True,
                            ),
                        }
                    )
                    active_labels.append(label)
                continue

            applied = False
            if type_name == "Strength":
                modifiers["strength"] += value
                applied = True
            elif type_name == "Agility":
                modifiers["agility"] += value
                applied = True
            elif type_name == "Intelligence":
                modifiers["intelligence"] += value
                applied = True
            elif type_name == "Armor":
                modifiers["armor_flat"] += value
                applied = True
            elif type_name == "Magic Resistance":
                modifiers["magic_resist_flat"] += value
                applied = True
            elif type_name == "Attack Speed":
                modifiers["attack_speed_flat"] += value
                applied = True
            elif type_name == "BAT Reduction %":
                modifiers["bat_reduction_pct"] += value / 100.0
                applied = True
            elif type_name == "HP":
                modifiers["health_flat"] += value
                applied = True
            elif type_name == "Mana":
                modifiers["mana_flat"] += value
                applied = True
            elif type_name == "HP Regen Flat":
                modifiers["health_regen_flat"] += value
                applied = True
            elif type_name == "Mana Regen Flat":
                modifiers["mana_regen_flat"] += value
                applied = True
            elif type_name == "Movespeed Flat":
                modifiers["move_speed_flat"] += value
                applied = True
            elif type_name == "Movespeed Percent":
                modifiers["move_speed_pct"] += value / 100.0
                applied = True

            if applied and abs(value) > 1e-9:
                active_labels.append(label)

        return modifiers, damage_modifiers, active_labels

    def _apply_attack_damage_modifier_chain(self, base_damage, damage_modifiers):
        damage = float(base_damage)
        for modifier in damage_modifiers:
            if modifier.get("kind") == "flat":
                damage += modifier.get("value", 0.0)
                continue
            if modifier.get("kind") == "pct":
                pct = modifier.get("value", 0.0)
                if modifier.get("apply_to_total", True):
                    damage *= max(0.0, 1 + pct)
                else:
                    damage += base_damage * pct
        return damage

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
        custom_modifiers, custom_damage_modifiers, custom_modifier_labels = self._collect_state_custom_modifiers(state)

        total_modifiers = _empty_modifiers()
        _merge_modifiers(total_modifiers, item_modifiers)
        _merge_modifiers(total_modifiers, talent_modifiers)
        _merge_modifiers(total_modifiers, custom_modifiers)

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

        attack_damage_bonus = self._base_attack_damage_gain(hero_data, primary_attribute) * level_factor
        attack_damage_bonus += self._bonus_attribute_damage(primary_attribute, total_modifiers)
        attack_damage_bonus += total_modifiers["attack_damage_flat"]

        attack_damage = _to_float(stats.get("damageAverage")) + attack_damage_bonus
        damage_min = _to_float(stats.get("damageMin"), default=None)
        if damage_min is not None:
            damage_min += attack_damage_bonus
        damage_max = _to_float(stats.get("damageMax"), default=None)
        if damage_max is not None:
            damage_max += attack_damage_bonus

        attack_damage = self._apply_attack_damage_modifier_chain(attack_damage, custom_damage_modifiers)
        if damage_min is not None:
            damage_min = self._apply_attack_damage_modifier_chain(damage_min, custom_damage_modifiers)
        if damage_max is not None:
            damage_max = self._apply_attack_damage_modifier_chain(damage_max, custom_damage_modifiers)

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
        bat = _to_float(stats.get("bat"))
        if total_modifiers["bat_reduction_pct"]:
            bat *= max(0.05, 1 - min(0.95, max(0.0, total_modifiers["bat_reduction_pct"])))

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
            "damage_min": damage_min,
            "damage_max": damage_max,
            "attack_speed": attack_speed,
            "move_speed": move_speed,
            "attack_range": attack_range,
            "projectile_speed": projectile_speed,
            "bat": bat,
            "animation_point": _to_float(stats.get("animationPoint"), default=None),
            "animation_backswing": _to_float(stats.get("animationBackswing"), default=None),
            "turn_rate": _to_float(stats.get("turnRate")),
            "collision_size": _to_float(stats.get("collisionSize"), default=None),
            "vision_day": _to_float(stats.get("visionDay"), default=None),
            "vision_night": _to_float(stats.get("visionNight"), default=None),
            "networth": networth,
            "talents_display": ", ".join(selected_talent_codes) if selected_talent_codes else "-",
            "items_display": ", ".join(selected_items) if selected_items else "-",
            "applied_talent_labels": applied_talent_labels,
            "custom_modifier_labels": custom_modifier_labels,
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

        row = self._build_table_row(row_id, self._active_target_snapshot())
        raw = row["_raw"]
        applied_talents = raw.get("applied_talent_labels", [])
        if applied_talents:
            applied_talent_text = "Applied stat talents: " + "; ".join(applied_talents)
        else:
            applied_talent_text = "Applied stat talents: none"
        custom_modifiers = raw.get("custom_modifier_labels", [])
        if custom_modifiers:
            custom_modifier_text = "Custom modifiers: " + "; ".join(custom_modifiers)
        else:
            custom_modifier_text = "Custom modifiers: none"

        target_text = ""
        if raw.get("target_name"):
            spell_setup_text = ""
            if _to_float(raw.get("incoming_spell_effective_damage"), default=0.0) > 0:
                spell_setup_text = (
                    f" after {_format_number(raw['incoming_spell_effective_damage'])} spell damage "
                    f"({_format_number(raw['remaining_health_after_spells'])} HP left)"
                )
            target_text = (
                f"\nVs {raw['target_name']}{spell_setup_text}: {row['target_damage_per_hit']} Dmg/Hit, "
                f"{row['target_dps']} DPS, {row['target_attacks_to_kill']} Hits To Kill, "
                f"{row['target_time_to_kill']}s TTK."
            )

        self.selected_applied_summary_var.set(
            f"{row['row_label']} row current stats: {row['health']} HP, {row['mana']} Mana, {row['armor']} Armor, "
            f"{row['networth']} Networth, "
            f"{row['attack_damage']} Attack Damage, {row['attack_speed']} Attack Speed, {row['move_speed']} Move Speed.\n"
            f"{applied_talent_text}\n{custom_modifier_text}{target_text}"
        )
