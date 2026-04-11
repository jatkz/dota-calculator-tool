import json
import os
import re
import tkinter as tk
from difflib import get_close_matches
from datetime import datetime
from tkinter import ttk

try:
    from scripts.score_dpt_draft import (
        DRAFT_WEIGHTS as DPT_DRAFT_WEIGHTS,
        score_candidate as score_dpt_candidate,
        finalize_candidate_normalization as finalize_dpt_candidate_normalization,
    )
    DPT_SCORER_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - fallback keeps the UI usable.
    DPT_DRAFT_WEIGHTS = None
    score_dpt_candidate = None
    finalize_dpt_candidate_normalization = None
    DPT_SCORER_IMPORT_ERROR = str(exc)


ROLE_KEYS = ["1", "2", "3", "4", "5"]
SCORE_VALUES = [3, 2, 1, 0, -1, -2, -3]
BOX_TYPES = ("synergy", "matchup")
BOX_LABELS = {
    "synergy": "Synergy",
    "matchup": "Matchup",
}
ATTRIBUTE_ORDER = [
    ("str", "strength"),
    ("agi", "agility"),
    ("int", "intelligence"),
    ("uni", "universal"),
]
ATTRIBUTE_LABELS = {short: short.upper() for short, _ in ATTRIBUTE_ORDER}
DRAFT_GRID_COLUMNS = 5
DRAFT_GRID_BUTTON_WIDTH = 13
DRAFT_GRID_BUTTON_HEIGHT = 2
DRAFT_GRID_BUTTON_WRAP = 84
DRAFT_GRID_BUTTON_PADX = 0
DRAFT_GRID_BUTTON_PADY = 0
DRAFT_GRID_CELL_PADX = 0
DRAFT_GRID_CELL_PADY = 0
DRAFT_DETAIL_TEXT_HEIGHT = 12
DRAFT_SUMMARY_TREE_HEIGHT = 9
DPT_EXPLORER_SUMMARY_HEIGHT = 12
DPT_EXPLORER_TABLE_HEIGHT = 14


def _score_key(score):
    return str(score)


def _blank_score_rows():
    return {_score_key(score): "" for score in SCORE_VALUES}


def _blank_box_record():
    return {role: _blank_score_rows() for role in ROLE_KEYS}


def _blank_role_record():
    return {box_type: _blank_box_record() for box_type in BOX_TYPES}


def _blank_hero_record():
    return {
        "default_role": "1",
        "roles": {role: _blank_role_record() for role in ROLE_KEYS},
    }


def _normalize_attribute(value):
    mapping = {
        "strength": "str",
        "agility": "agi",
        "intelligence": "int",
        "universal": "uni",
    }
    return mapping.get(str(value or "").strip().lower(), "uni")


def _load_json_file(path, default_payload):
    if not os.path.exists(path):
        return default_payload

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return default_payload

    if isinstance(default_payload, dict) and isinstance(payload, dict):
        return payload
    if isinstance(default_payload, list) and isinstance(payload, list):
        return payload
    return default_payload


def _write_json_file(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _normalize_match_text(text):
    lowered = str(text or "").lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_compact_text(text):
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class HeroDraftLibraryApp:
    def __init__(self, parent):
        self.parent = parent
        self.base_dir = os.path.dirname(__file__)
        self.dataset_path = os.path.join(self.base_dir, "dataset.json")
        self.library_path = os.path.join(self.base_dir, "library-dex.json")
        self.saved_drafts_path = os.path.join(self.base_dir, "saved-drafts.json")
        self.app_state_path = os.path.join(self.base_dir, "app-state.json")
        self.dpt_library_path = os.path.join(self.base_dir, "dpt_matchups_synergies.json")
        self.dpt_scores_path = os.path.join(self.base_dir, "dpt_scores.json")

        self.heroes = self._load_heroes()
        self.hero_names = sorted(self.heroes.keys())
        self.hero_attributes = {
            hero: self._resolve_hero_attribute(self.heroes[hero])
            for hero in self.hero_names
        }
        self.hero_attribute_data_missing = bool(self.hero_names) and all(
            self.hero_attributes.get(hero) == "uni"
            for hero in self.hero_names
        )
        self.heroes_by_attribute = {
            short: sorted([hero for hero in self.hero_names if self.hero_attributes.get(hero) == short])
            for short, _ in ATTRIBUTE_ORDER
        }
        self.hero_match_names = {
            hero: _normalize_match_text(hero)
            for hero in self.hero_names
        }
        self.hero_match_lookup = {
            normalized: hero
            for hero, normalized in self.hero_match_names.items()
            if normalized
        }
        self.hero_compact_lookup = {
            _normalize_compact_text(hero): hero
            for hero in self.hero_names
            if _normalize_compact_text(hero)
        }
        self.hero_match_choices = list(self.hero_match_lookup.keys())
        self.hero_compact_choices = list(self.hero_compact_lookup.keys())

        self.library_data = self._load_library_data()
        self.saved_drafts_data = self._load_saved_drafts_data()
        self.app_state_data = self._load_app_state_data()
        self.dpt_library_load_error = ""
        self.dpt_library_data = self._load_dpt_library_data()
        self.dpt_scores_load_error = ""
        self.dpt_scores_data = self._load_dpt_scores_data()

        self.current_edit_hero = None
        self.current_edit_attribute = "uni" if self.hero_attribute_data_missing else "str"
        self.loading_edit_values = False
        self.library_save_after_id = None

        self.banned_heroes = set()
        self.enemy_assignments = {}
        self.ally_assignments = {}

        self.edit_search_var = tk.StringVar(value="")
        self.edit_default_role_var = tk.StringVar(value="1")
        self.edit_save_status_var = tk.StringVar(value="Changes save to library-dex.json as you type.")
        self.edit_hero_title_var = tk.StringVar(value="")
        self.edit_hero_meta_var = tk.StringVar(value="")

        self.your_role_var = tk.StringVar(value=self.app_state_data["draft"].get("your_role", "1"))
        self.draft_action_var = tk.StringVar(value="ban")
        self.draft_name_var = tk.StringVar(value="")
        self.draft_status_var = tk.StringVar(value="")
        self.ban_summary_var = tk.StringVar(value="Bans: none")
        self.enemy_summary_var = tk.StringVar(value="Enemies: none")
        self.ally_summary_var = tk.StringVar(value="Allies: none")
        self.dpt_explorer_hero_var = tk.StringVar(value=self._default_dpt_explorer_hero())
        self.dpt_explorer_role_var = tk.StringVar(value="")
        self.dpt_explorer_filter_var = tk.StringVar(value="")
        self.dpt_explorer_status_var = tk.StringVar(value="")

        self.edit_grid_frames = {}
        self.edit_score_vars = {}
        self.search_results = []
        self.draft_hero_buttons = {}
        self.draft_treeviews = {}
        self.ally_mode_buttons = {}
        self.dpt_explorer_trees = {}
        self.dpt_explorer_tree_sort_state = {}
        self.latest_dpt_candidate_rows = []
        self.latest_dpt_candidate_lookup = {}
        self.scrolled_regions = []

        self._build_ui()
        self._bind_global_mousewheel()
        self._rebuild_edit_hero_grids()
        self._refresh_edit_search_results()
        self._refresh_draft_outputs()

    def _load_heroes(self):
        payload = _load_json_file(self.dataset_path, {"heroes": {}, "heroesCore": {}})
        for key in ("heroes", "heroesCore"):
            heroes = payload.get(key, {})
            if isinstance(heroes, dict) and heroes:
                return heroes
        return {}

    def _resolve_hero_attribute(self, hero_record):
        if not isinstance(hero_record, dict):
            return "uni"

        general = hero_record.get("general", {})
        if isinstance(general, dict):
            normalized = _normalize_attribute(general.get("primary_attribute"))
            if normalized != "uni" or str(general.get("primary_attribute", "")).strip().lower() == "universal":
                return normalized

        for key in ("primary_attribute", "primaryAttribute", "attribute_type"):
            value = hero_record.get(key)
            normalized = _normalize_attribute(value)
            if normalized != "uni" or str(value or "").strip().lower() == "universal":
                return normalized

        return "uni"

    def _load_library_data(self):
        payload = _load_json_file(self.library_path, {"heroes": {}})
        heroes_payload = payload.get("heroes", {})
        if not isinstance(heroes_payload, dict):
            heroes_payload = {}

        if not self.hero_names:
            return {"heroes": heroes_payload}

        normalized = {"heroes": {}}
        for hero_name in self.hero_names:
            normalized["heroes"][hero_name] = self._normalize_hero_record(heroes_payload.get(hero_name))

        if normalized != payload:
            _write_json_file(self.library_path, normalized)
        return normalized

    def _load_saved_drafts_data(self):
        payload = _load_json_file(self.saved_drafts_path, {"drafts": []})
        drafts = payload.get("drafts", [])
        if not isinstance(drafts, list):
            drafts = []

        normalized_drafts = []
        for draft in drafts:
            if not isinstance(draft, dict):
                continue
            normalized_drafts.append(self._normalize_saved_draft(draft))

        normalized = {"drafts": normalized_drafts}
        _write_json_file(self.saved_drafts_path, normalized)
        return normalized

    def _load_app_state_data(self):
        payload = _load_json_file(self.app_state_path, {"draft": {"your_role": "1"}})
        draft_payload = payload.get("draft", {})
        if not isinstance(draft_payload, dict):
            draft_payload = {}

        your_role = str(draft_payload.get("your_role", "1"))
        if your_role not in ROLE_KEYS:
            your_role = "1"

        normalized = {
            "draft": {
                "your_role": your_role,
            }
        }
        if normalized != payload:
            _write_json_file(self.app_state_path, normalized)
        return normalized

    def _load_dpt_library_data(self):
        self.dpt_library_load_error = ""
        payload = _load_json_file(self.dpt_library_path, {"heroes": {}})
        heroes_payload = payload.get("heroes", {})
        if not isinstance(heroes_payload, dict):
            self.dpt_library_load_error = "dpt_matchups_synergies.json is invalid."
            return {"heroes": {}}
        if not heroes_payload:
            if os.path.exists(self.dpt_library_path):
                self.dpt_library_load_error = "dpt_matchups_synergies.json has no hero entries yet."
            else:
                self.dpt_library_load_error = "dpt_matchups_synergies.json was not found."
        return payload

    def _save_app_state(self):
        self.app_state_data["draft"]["your_role"] = self.your_role_var.get()
        _write_json_file(self.app_state_path, self.app_state_data)

    def _default_dpt_explorer_hero(self):
        raw_heroes = self.dpt_library_data.get("heroes", {}) if hasattr(self, "dpt_library_data") else {}
        score_heroes = self.dpt_scores_data.get("heroes", {}) if hasattr(self, "dpt_scores_data") else {}
        names = sorted(set(raw_heroes) | set(score_heroes))
        return names[0] if names else ""

    def _load_dpt_scores_data(self):
        self.dpt_scores_load_error = ""
        if DPT_SCORER_IMPORT_ERROR:
            self.dpt_scores_load_error = f"DPT scorer import failed: {DPT_SCORER_IMPORT_ERROR}"
            return {"heroes": {}}

        payload = _load_json_file(self.dpt_scores_path, {"heroes": {}})
        heroes_payload = payload.get("heroes", {})
        if not isinstance(heroes_payload, dict):
            self.dpt_scores_load_error = "dpt_scores.json is invalid."
            return {"heroes": {}}
        if not heroes_payload:
            if os.path.exists(self.dpt_scores_path):
                self.dpt_scores_load_error = "dpt_scores.json has no hero entries yet."
            else:
                self.dpt_scores_load_error = "dpt_scores.json was not found."
        return payload

    def _normalize_hero_record(self, record):
        normalized = _blank_hero_record()
        if not isinstance(record, dict):
            return normalized

        default_role = str(record.get("default_role", "1"))
        if default_role in ROLE_KEYS:
            normalized["default_role"] = default_role

        roles_payload = record.get("roles", {})
        if not isinstance(roles_payload, dict):
            roles_payload = {}

        for hero_role in ROLE_KEYS:
            source_role = roles_payload.get(hero_role, {})
            if not isinstance(source_role, dict):
                continue
            for box_type in BOX_TYPES:
                source_box = source_role.get(box_type, {})
                if not isinstance(source_box, dict):
                    continue
                for target_role in ROLE_KEYS:
                    source_rows = source_box.get(target_role, {})
                    if not isinstance(source_rows, dict):
                        continue
                    for score in SCORE_VALUES:
                        score_key = _score_key(score)
                        normalized["roles"][hero_role][box_type][target_role][score_key] = str(
                            source_rows.get(score_key, "")
                        )

        return normalized

    def _normalize_saved_draft(self, draft):
        your_role = str(draft.get("your_role", "1"))
        if your_role not in ROLE_KEYS:
            your_role = "1"

        bans = [
            hero
            for hero in draft.get("bans", [])
            if hero in self.heroes
        ]

        enemy_assignments = {}
        source_enemy_assignments = draft.get("enemy_assignments", {})
        if isinstance(source_enemy_assignments, dict):
            for hero, role in source_enemy_assignments.items():
                role_text = str(role)
                if hero in self.heroes and role_text in ROLE_KEYS:
                    enemy_assignments[hero] = role_text

        ally_assignments = {}
        source_ally_assignments = draft.get("ally_assignments", {})
        if isinstance(source_ally_assignments, dict):
            for role, hero in source_ally_assignments.items():
                role_text = str(role)
                if role_text in ROLE_KEYS and hero in self.heroes:
                    ally_assignments[role_text] = hero

        return {
            "name": str(draft.get("name", "")).strip() or f"Draft {_timestamp()}",
            "saved_at": str(draft.get("saved_at", _timestamp())),
            "your_role": your_role,
            "bans": sorted(set(bans)),
            "enemy_assignments": enemy_assignments,
            "ally_assignments": ally_assignments,
            "notes": str(draft.get("notes", "")),
        }

    def _build_ui(self):
        notebook = ttk.Notebook(self.parent)
        notebook.pack(fill="both", expand=True)

        edit_tab = ttk.Frame(notebook)
        draft_tab = ttk.Frame(notebook)
        dpt_explorer_tab = ttk.Frame(notebook)
        notebook.add(edit_tab, text="Edit Mode")
        notebook.add(draft_tab, text="Draft Mode")
        notebook.add(dpt_explorer_tab, text="DPT Explorer")
        notebook.select(draft_tab)

        self.edit_content = self._create_scrolled_content(edit_tab)
        self.draft_content = self._create_scrolled_content(draft_tab)
        self.dpt_explorer_content = self._create_scrolled_content(dpt_explorer_tab)

        self._build_edit_mode()
        self._build_draft_mode()
        self._build_dpt_explorer_mode()

    def _create_scrolled_content(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, padding=16)

        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.scrolled_regions.append({"canvas": canvas, "content": content})

        return content

    def _bind_global_mousewheel(self):
        self.parent.bind_all("<MouseWheel>", self._handle_global_mousewheel, add="+")
        self.parent.bind_all("<Button-4>", self._handle_global_mousewheel, add="+")
        self.parent.bind_all("<Button-5>", self._handle_global_mousewheel, add="+")

    def _handle_global_mousewheel(self, event):
        region = self._find_scroll_region(event.widget)
        if not region:
            return None

        units = self._mousewheel_units(event)
        if not units:
            return None

        canvas = region["canvas"]
        target = self._resolve_scroll_target(event.widget, canvas, units)
        if target is None:
            return None

        target.yview_scroll(units, "units")
        return "break"

    def _find_scroll_region(self, widget):
        for region in self.scrolled_regions:
            for ancestor in (region["content"], region["canvas"]):
                if self._widget_is_descendant(widget, ancestor):
                    return region
        return None

    def _widget_is_descendant(self, widget, ancestor):
        current = widget
        while current is not None:
            if str(current) == str(ancestor):
                return True
            parent_name = current.winfo_parent()
            if not parent_name:
                return False
            current = current.nametowidget(parent_name)
        return False

    def _mousewheel_units(self, event):
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1

        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return 0
        if abs(delta) >= 120:
            return int(-delta / 120)
        return -1 if delta > 0 else 1

    def _resolve_scroll_target(self, widget, canvas, units):
        current = widget
        while current is not None and str(current) != str(canvas):
            if self._is_inner_scrollable_widget(current):
                if self._widget_can_scroll(current, units):
                    return current
            parent_name = current.winfo_parent()
            if not parent_name:
                break
            current = current.nametowidget(parent_name)
        return canvas

    def _is_inner_scrollable_widget(self, widget):
        return widget.winfo_class() in {"Text", "Listbox", "Treeview"}

    def _widget_can_scroll(self, widget, units):
        try:
            first, last = widget.yview()
        except Exception:
            return False

        if units < 0:
            return float(first) > 0.0
        if units > 0:
            return float(last) < 1.0
        return False

    def _build_edit_mode(self):
        ttk.Label(
            self.edit_content,
            text="Hero Draft Library Editor",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            self.edit_content,
            text="Choose an attribute tab, open a hero, then edit default role plus role-by-role synergy and matchup notes.",
        ).pack(anchor="w", pady=(0, 12))

        if self.hero_attribute_data_missing:
            ttk.Label(
                self.edit_content,
                text="This dataset does not expose primary attributes, so hero lists are grouped under UNI for now.",
                foreground="#666",
            ).pack(anchor="w", pady=(0, 12))

        self.edit_selector_frame = ttk.Frame(self.edit_content)
        self.edit_selector_frame.pack(fill="x", expand=True)

        self.edit_attribute_notebook = ttk.Notebook(self.edit_selector_frame)
        self.edit_attribute_notebook.pack(fill="x", pady=(0, 12))
        self.edit_attribute_notebook.bind("<<NotebookTabChanged>>", self._handle_edit_attribute_tab_change)

        for short_label, _full_label in ATTRIBUTE_ORDER:
            tab = ttk.Frame(self.edit_attribute_notebook, padding=8)
            self.edit_attribute_notebook.add(tab, text=ATTRIBUTE_LABELS[short_label])

            ttk.Label(
                tab,
                text=f"{ATTRIBUTE_LABELS[short_label]} heroes",
                font=("Arial", 11, "bold"),
            ).pack(anchor="w", pady=(0, 8))

            grid_frame = ttk.Frame(tab)
            grid_frame.pack(fill="x")
            self.edit_grid_frames[short_label] = grid_frame

        if self.hero_attribute_data_missing:
            self.edit_attribute_notebook.select(ATTRIBUTE_ORDER.index(("uni", "universal")))

        search_frame = ttk.LabelFrame(self.edit_selector_frame, text="Hero Search", padding=10)
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="Autocomplete").pack(anchor="w")
        search_entry = ttk.Entry(search_frame, textvariable=self.edit_search_var, width=40)
        search_entry.pack(anchor="w", fill="x", pady=(4, 8))
        search_entry.bind("<Return>", self._open_selected_search_result)
        self.edit_search_var.trace_add("write", lambda *_: self._refresh_edit_search_results())

        self.edit_search_listbox = tk.Listbox(search_frame, height=8, exportselection=False)
        self.edit_search_listbox.pack(fill="x")
        self.edit_search_listbox.bind("<Double-Button-1>", self._open_selected_search_result)
        self.edit_search_listbox.bind("<Return>", self._open_selected_search_result)

        self.edit_detail_frame = ttk.Frame(self.edit_content)

        top_row = ttk.Frame(self.edit_detail_frame)
        top_row.pack(fill="x", pady=(0, 10))

        ttk.Button(top_row, text="Back", command=self._show_edit_selector).pack(side="left")

        text_frame = ttk.Frame(top_row)
        text_frame.pack(side="left", padx=(12, 0))
        ttk.Label(text_frame, textvariable=self.edit_hero_title_var, font=("Arial", 15, "bold")).pack(anchor="w")
        ttk.Label(text_frame, textvariable=self.edit_hero_meta_var).pack(anchor="w")

        defaults_frame = ttk.LabelFrame(self.edit_detail_frame, text="Default Role", padding=10)
        defaults_frame.pack(fill="x", pady=(0, 10))

        for role in ROLE_KEYS:
            button = tk.Radiobutton(
                defaults_frame,
                text=f"Role {role}",
                value=role,
                variable=self.edit_default_role_var,
                indicatoron=False,
                width=8,
                padx=8,
            )
            button.pack(side="left", padx=(0, 6))

        self.edit_default_role_var.trace_add("write", lambda *_: self._handle_default_role_change())

        ttk.Label(
            self.edit_detail_frame,
            textvariable=self.edit_save_status_var,
        ).pack(anchor="w", pady=(0, 10))

        self.edit_role_notebook = ttk.Notebook(self.edit_detail_frame)
        self.edit_role_notebook.pack(fill="both", expand=True)

        for hero_role in ROLE_KEYS:
            role_tab = ttk.Frame(self.edit_role_notebook, padding=8)
            self.edit_role_notebook.add(role_tab, text=f"Role {hero_role}")

            box_row = ttk.Frame(role_tab)
            box_row.pack(fill="both", expand=True)

            for index, box_type in enumerate(BOX_TYPES):
                box_frame = ttk.LabelFrame(box_row, text=BOX_LABELS[box_type], padding=10)
                box_frame.pack(side="left", fill="both", expand=True, padx=(0, 10 if index == 0 else 0))

                role_notebook = ttk.Notebook(box_frame)
                role_notebook.pack(fill="both", expand=True)

                for target_role in ROLE_KEYS:
                    target_tab = ttk.Frame(role_notebook, padding=8)
                    role_notebook.add(target_tab, text=f"Role {target_role}")

                    ttk.Label(
                        target_tab,
                        text=(
                            f"Hero role {hero_role} -> {BOX_LABELS[box_type].lower()} with role {target_role}"
                            " | comma-separated hero names, spell-checks on focus out"
                        ),
                    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

                    for row_index, score in enumerate(SCORE_VALUES, start=1):
                        ttk.Label(target_tab, text=f"{score:+d}" if score != 0 else "0", width=4).grid(
                            row=row_index,
                            column=0,
                            sticky="w",
                            padx=(0, 8),
                            pady=2,
                        )
                        var = tk.StringVar(value="")
                        self.edit_score_vars[(hero_role, box_type, target_role, _score_key(score))] = var
                        var.trace_add(
                            "write",
                            lambda *_args, hr=hero_role, bt=box_type, tr=target_role, sk=_score_key(score): self._handle_score_change(
                                hr,
                                bt,
                                tr,
                                sk,
                            ),
                        )
                        entry = ttk.Entry(target_tab, textvariable=var, width=50)
                        entry.grid(
                            row=row_index,
                            column=1,
                            sticky="ew",
                            pady=2,
                        )
                        entry.bind(
                            "<FocusOut>",
                            lambda _event, hr=hero_role, bt=box_type, tr=target_role, sk=_score_key(score): self._normalize_score_entry(
                                hr,
                                bt,
                                tr,
                                sk,
                            ),
                        )
                        entry.bind(
                            "<Return>",
                            lambda _event, hr=hero_role, bt=box_type, tr=target_role, sk=_score_key(score): self._normalize_score_entry(
                                hr,
                                bt,
                                tr,
                                sk,
                            ),
                        )

                    target_tab.columnconfigure(1, weight=1)

        self._show_edit_selector()

    def _build_draft_mode(self):
        ttk.Label(
            self.draft_content,
            text="Draft Mode",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            self.draft_content,
            text="Set your role, choose a draft action, then click heroes to build bans, enemy picks, and allies.",
        ).pack(anchor="w", pady=(0, 12))

        if self.hero_attribute_data_missing:
            ttk.Label(
                self.draft_content,
                text="Current hero data is missing primary-attribute labels, so the hero grid is grouped under UNI.",
                foreground="#666",
            ).pack(anchor="w", pady=(0, 12))

        controls_frame = ttk.Frame(self.draft_content)
        controls_frame.pack(fill="x", pady=(0, 12))

        your_role_frame = ttk.LabelFrame(controls_frame, text="Your Role", padding=6)
        your_role_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        for role in ROLE_KEYS:
            button = tk.Radiobutton(
                your_role_frame,
                text=f"Role {role}",
                value=role,
                variable=self.your_role_var,
                indicatoron=False,
                width=8,
                padx=8,
                command=self._handle_your_role_change,
            )
            button.pack(side="left", padx=(0, 6))

        action_frame = ttk.LabelFrame(controls_frame, text="Draft Action", padding=6)
        action_frame.pack(side="left", fill="x", expand=True)

        tk.Radiobutton(
            action_frame,
            text="Bans",
            value="ban",
            variable=self.draft_action_var,
            indicatoron=False,
            padx=6,
            width=7,
        ).pack(side="left", padx=(0, 2))

        tk.Radiobutton(
            action_frame,
            text="Enemy",
            value="enemy",
            variable=self.draft_action_var,
            indicatoron=False,
            padx=6,
            width=7,
        ).pack(side="left", padx=(0, 2))

        for role in ROLE_KEYS:
            button = tk.Radiobutton(
                action_frame,
                text=f"Ally {role}",
                value=f"ally:{role}",
                variable=self.draft_action_var,
                indicatoron=False,
                padx=10,
                width=8,
            )
            button.pack(side="left", padx=(0, 6))
            self.ally_mode_buttons[role] = button

        pools_frame = ttk.Frame(self.draft_content)
        pools_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(pools_frame, textvariable=self.ban_summary_var).pack(anchor="w")
        ttk.Label(pools_frame, textvariable=self.enemy_summary_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(pools_frame, textvariable=self.ally_summary_var).pack(anchor="w", pady=(4, 0))

        grid_frame = ttk.LabelFrame(self.draft_content, text="Hero Grid", padding=10)
        grid_frame.pack(fill="x", pady=(0, 12))

        for index, (short_label, _full_label) in enumerate(ATTRIBUTE_ORDER):
            category_frame = ttk.LabelFrame(grid_frame, text=ATTRIBUTE_LABELS[short_label], padding=8)
            category_frame.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=6,
                pady=6,
            )
            self._build_draft_category_grid(category_frame, short_label)

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        summary_notebook = ttk.Notebook(self.draft_content)
        summary_notebook.pack(fill="both", expand=True, pady=(0, 12))

        self.draft_treeviews["bans"] = self._create_summary_tree_tab(summary_notebook, "Ban Sums")
        self.draft_treeviews["enemies"] = self._create_summary_tree_tab(summary_notebook, "Enemy Sums")
        self.draft_treeviews["allies"] = self._create_summary_tree_tab(summary_notebook, "Ally Sums")
        self.draft_treeviews["overall"] = self._create_summary_tree_tab(summary_notebook, "Overall")
        self.draft_treeviews["role3"] = self._create_summary_tree_tab(summary_notebook, "Role 3 Picks")
        self.draft_treeviews["dpt"] = self._create_dpt_summary_tree_tab(summary_notebook, "DPT Picks")
        summary_notebook.select(summary_notebook.tabs()[-1])

        detail_notebook = ttk.Notebook(self.draft_content)
        detail_notebook.pack(fill="both", expand=True, pady=(0, 12))

        self.ban_detail_text = self._create_detail_text_tab(detail_notebook, "Bans")
        self.enemy_detail_text = self._create_detail_text_tab(detail_notebook, "Enemies")
        self.ally_detail_text = self._create_detail_text_tab(detail_notebook, "Allies")
        self.dpt_detail_text = self._create_detail_text_tab(detail_notebook, "DPT")
        detail_notebook.select(detail_notebook.tabs()[-1])

        save_frame = ttk.LabelFrame(self.draft_content, text="Save Draft", padding=10)
        save_frame.pack(fill="both", expand=True)

        name_row = ttk.Frame(save_frame)
        name_row.pack(fill="x", pady=(0, 8))
        ttk.Label(name_row, text="Draft name").pack(side="left")
        ttk.Entry(name_row, textvariable=self.draft_name_var, width=36).pack(side="left", padx=(8, 12))
        ttk.Button(name_row, text="Save Draft", command=self._save_current_draft).pack(side="left", padx=(0, 6))
        ttk.Button(name_row, text="Clear Draft", command=self._clear_current_draft).pack(side="left")

        ttk.Label(save_frame, textvariable=self.draft_status_var).pack(anchor="w", pady=(0, 8))

        ttk.Label(save_frame, text="Notes").pack(anchor="w")
        self.draft_notes_text = tk.Text(save_frame, height=6, wrap="word")
        self.draft_notes_text.pack(fill="x", pady=(4, 10))

        saved_row = ttk.Frame(save_frame)
        saved_row.pack(fill="both", expand=True)

        saved_list_frame = ttk.Frame(saved_row)
        saved_list_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ttk.Label(saved_list_frame, text="Saved drafts").pack(anchor="w")
        self.saved_drafts_listbox = tk.Listbox(saved_list_frame, height=8, exportselection=False)
        self.saved_drafts_listbox.pack(fill="both", expand=True, pady=(4, 0))
        self.saved_drafts_listbox.bind("<Double-Button-1>", lambda _event: self._load_selected_draft())

        action_column = ttk.Frame(saved_row)
        action_column.pack(side="left", fill="y")
        ttk.Button(action_column, text="Load Selected", command=self._load_selected_draft).pack(fill="x", pady=(0, 6))
        ttk.Button(action_column, text="Delete Selected", command=self._delete_selected_draft).pack(fill="x")

        self._refresh_saved_drafts_listbox()

    def _build_dpt_explorer_mode(self):
        ttk.Label(
            self.dpt_explorer_content,
            text="DPT Explorer",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            self.dpt_explorer_content,
            text="Browse raw Dota2ProTracker matchup and synergy rows alongside the derived DPT scores for each hero role.",
        ).pack(anchor="w", pady=(0, 12))

        controls_frame = ttk.LabelFrame(self.dpt_explorer_content, text="Selection", padding=10)
        controls_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(controls_frame, text="Hero").grid(row=0, column=0, sticky="w")
        self.dpt_explorer_hero_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.dpt_explorer_hero_var,
            values=self._get_dpt_explorer_hero_names(),
            width=28,
            postcommand=lambda: self._update_dpt_explorer_hero_choices(self.dpt_explorer_hero_var.get()),
        )
        self.dpt_explorer_hero_combo.grid(row=1, column=0, sticky="ew", padx=(0, 12))
        self.dpt_explorer_hero_combo.bind("<<ComboboxSelected>>", self._handle_dpt_explorer_hero_change)
        self.dpt_explorer_hero_combo.bind("<Return>", self._handle_dpt_explorer_hero_change)
        self.dpt_explorer_hero_combo.bind("<FocusOut>", self._handle_dpt_explorer_hero_change)
        self.dpt_explorer_hero_combo.bind("<KeyRelease>", self._handle_dpt_explorer_hero_typing)

        ttk.Label(controls_frame, text="Role").grid(row=0, column=1, sticky="w")
        self.dpt_explorer_role_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.dpt_explorer_role_var,
            values=[],
            width=16,
            state="readonly",
        )
        self.dpt_explorer_role_combo.grid(row=1, column=1, sticky="ew", padx=(0, 12))
        self.dpt_explorer_role_combo.bind("<<ComboboxSelected>>", self._handle_dpt_explorer_role_change)

        ttk.Label(controls_frame, text="Row Filter").grid(row=0, column=2, sticky="w")
        filter_entry = ttk.Entry(
            controls_frame,
            textvariable=self.dpt_explorer_filter_var,
            width=24,
        )
        filter_entry.grid(row=1, column=2, sticky="ew")
        self.dpt_explorer_filter_var.trace_add("write", lambda *_: self._refresh_dpt_explorer())

        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=0)
        controls_frame.columnconfigure(2, weight=1)

        ttk.Label(
            self.dpt_explorer_content,
            textvariable=self.dpt_explorer_status_var,
            foreground="#555",
        ).pack(anchor="w", pady=(0, 8))

        summary_frame = ttk.LabelFrame(self.dpt_explorer_content, text="Role Summary", padding=8)
        summary_frame.pack(fill="both", expand=True, pady=(0, 12))
        self.dpt_explorer_summary_text = tk.Text(
            summary_frame,
            height=DPT_EXPLORER_SUMMARY_HEIGHT,
            wrap="word",
        )
        self.dpt_explorer_summary_text.pack(fill="both", expand=True)
        self.dpt_explorer_summary_text.configure(state="disabled")

        notebook = ttk.Notebook(self.dpt_explorer_content)
        notebook.pack(fill="both", expand=True, pady=(0, 12))

        self.dpt_explorer_trees["matchups"] = self._create_dpt_explorer_tree_tab(
            notebook,
            "Matchups",
            columns=("hero", "role", "winrate", "lane", "matches"),
            headings={
                "hero": "Hero",
                "role": "Role",
                "winrate": "Winrate",
                "lane": "Lane Adv",
                "matches": "Matches",
            },
            widths={
                "hero": 180,
                "role": 120,
                "winrate": 90,
                "lane": 90,
                "matches": 90,
            },
        )
        self.dpt_explorer_trees["synergies"] = self._create_dpt_explorer_tree_tab(
            notebook,
            "Synergies",
            columns=("hero", "role", "winrate", "lane", "matches"),
            headings={
                "hero": "Hero",
                "role": "Role",
                "winrate": "Winrate",
                "lane": "Lane Adv",
                "matches": "Matches",
            },
            widths={
                "hero": 180,
                "role": 120,
                "winrate": 90,
                "lane": 90,
                "matches": 90,
            },
        )
        self.dpt_explorer_trees["vs_scores"] = self._create_dpt_explorer_tree_tab(
            notebook,
            "VS Scores",
            columns=("hero", "role", "win_raw", "win_norm", "win_conf", "lane_raw", "lane_norm", "lane_conf"),
            headings={
                "hero": "Hero",
                "role": "Role",
                "win_raw": "Win Raw",
                "win_norm": "Win Norm",
                "win_conf": "Win Conf",
                "lane_raw": "Lane Raw",
                "lane_norm": "Lane Norm",
                "lane_conf": "Lane Conf",
            },
            widths={
                "hero": 160,
                "role": 110,
                "win_raw": 90,
                "win_norm": 90,
                "win_conf": 90,
                "lane_raw": 90,
                "lane_norm": 90,
                "lane_conf": 90,
            },
        )
        self.dpt_explorer_trees["with_scores"] = self._create_dpt_explorer_tree_tab(
            notebook,
            "With Scores",
            columns=("hero", "role", "win_raw", "win_norm", "win_conf", "lane_raw", "lane_norm", "lane_conf"),
            headings={
                "hero": "Hero",
                "role": "Role",
                "win_raw": "Win Raw",
                "win_norm": "Win Norm",
                "win_conf": "Win Conf",
                "lane_raw": "Lane Raw",
                "lane_norm": "Lane Norm",
                "lane_conf": "Lane Conf",
            },
            widths={
                "hero": 160,
                "role": 110,
                "win_raw": 90,
                "win_norm": 90,
                "win_conf": 90,
                "lane_raw": 90,
                "lane_norm": 90,
                "lane_conf": 90,
            },
        )
        notebook.select(notebook.tabs()[0])

        self._update_dpt_explorer_role_choices()
        self._refresh_dpt_explorer()

    def _create_dpt_explorer_tree_tab(self, notebook, label, columns, headings, widths):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=label)

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=DPT_EXPLORER_TABLE_HEIGHT,
        )
        y_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        for column in columns:
            tree.heading(
                column,
                text=headings[column],
                command=lambda selected_column=column, selected_tree=tree: self._handle_dpt_explorer_tree_sort(
                    selected_tree,
                    selected_column,
                ),
            )
            tree.column(column, width=widths[column], anchor="center" if column != "hero" else "w")

        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        return tree

    def _get_dpt_explorer_hero_names(self):
        raw_heroes = self.dpt_library_data.get("heroes", {})
        score_heroes = self.dpt_scores_data.get("heroes", {})
        return sorted(set(raw_heroes) | set(score_heroes))

    def _update_dpt_explorer_hero_choices(self, query):
        hero_names = self._get_dpt_explorer_hero_names()
        text = str(query or "").strip().lower()
        if not text:
            filtered = hero_names
        else:
            startswith_matches = [hero for hero in hero_names if hero.lower().startswith(text)]
            contains_matches = [
                hero for hero in hero_names
                if text in hero.lower() and hero not in startswith_matches
            ]
            filtered = startswith_matches + contains_matches

            matched_hero = self._match_hero_name(query)
            if matched_hero and matched_hero not in filtered:
                filtered.insert(0, matched_hero)

        if hasattr(self, "dpt_explorer_hero_combo"):
            self.dpt_explorer_hero_combo["values"] = filtered[:40] if filtered else hero_names[:40]
        return filtered

    def _get_dpt_explorer_role_keys(self, hero_name):
        role_keys = set()
        raw_roles = self.dpt_library_data.get("heroes", {}).get(hero_name, {}).get("roles", {})
        score_roles = self.dpt_scores_data.get("heroes", {}).get(hero_name, {}).get("roles", {})
        role_keys.update(role for role in raw_roles if role in ROLE_KEYS)
        role_keys.update(role for role in score_roles if role in ROLE_KEYS)
        return sorted(role_keys, key=lambda role: ROLE_KEYS.index(role))

    def _handle_dpt_explorer_hero_change(self, _event=None):
        input_text = self.dpt_explorer_hero_var.get().strip()
        hero_name = self._match_hero_name(input_text) if input_text else ""
        if not hero_name and input_text in self._get_dpt_explorer_hero_names():
            hero_name = input_text
        if not hero_name:
            current_values = self._get_dpt_explorer_hero_names()
            if current_values:
                hero_name = current_values[0]
        self.dpt_explorer_hero_var.set(hero_name)
        self._update_dpt_explorer_role_choices()
        self._refresh_dpt_explorer()

    def _handle_dpt_explorer_hero_typing(self, event=None):
        if event and event.keysym in {"Return", "Tab", "Up", "Down", "Left", "Right", "Escape"}:
            return
        self._update_dpt_explorer_hero_choices(self.dpt_explorer_hero_var.get())

    def _handle_dpt_explorer_role_change(self, _event=None):
        self._refresh_dpt_explorer()

    def _update_dpt_explorer_role_choices(self):
        hero_name = self.dpt_explorer_hero_var.get().strip()
        role_keys = self._get_dpt_explorer_role_keys(hero_name) if hero_name else []
        role_labels = [f"{role} - {self._role_label(role)}" for role in role_keys]
        self.dpt_explorer_role_combo["values"] = role_labels

        current_role = self.dpt_explorer_role_var.get().split(" - ", 1)[0].strip()
        if current_role not in role_keys:
            current_role = role_keys[0] if role_keys else ""
        self.dpt_explorer_role_var.set(
            f"{current_role} - {self._role_label(current_role)}" if current_role else ""
        )

    def _role_label(self, role_key):
        return {
            "1": "Carry",
            "2": "Mid",
            "3": "Offlane",
            "4": "Support",
            "5": "Hard Support",
        }.get(str(role_key), str(role_key))

    def _refresh_dpt_explorer(self):
        hero_name = self.dpt_explorer_hero_var.get().strip()
        role_key = self.dpt_explorer_role_var.get().split(" - ", 1)[0].strip()
        filter_text = self.dpt_explorer_filter_var.get().strip().lower()

        raw_hero_data = self.dpt_library_data.get("heroes", {}).get(hero_name, {})
        raw_role_data = raw_hero_data.get("roles", {}).get(role_key, {})
        score_hero_data = self.dpt_scores_data.get("heroes", {}).get(hero_name, {})
        score_role_data = score_hero_data.get("roles", {}).get(role_key, {})

        if not hero_name:
            self.dpt_explorer_status_var.set(
                self.dpt_library_load_error or self.dpt_scores_load_error or "No DPT explorer data available."
            )
            self._set_readonly_text(self.dpt_explorer_summary_text, "No DPT hero selected.")
            for tree in self.dpt_explorer_trees.values():
                self._clear_tree_with_message(tree, "No DPT data available.")
            return

        self.dpt_explorer_status_var.set(
            f"{hero_name} | Role {role_key or '?'} {self._role_label(role_key) if role_key else ''}".strip()
        )
        self._set_readonly_text(
            self.dpt_explorer_summary_text,
            self._format_dpt_explorer_summary_text(hero_name, role_key, raw_role_data, score_role_data),
        )
        self._populate_dpt_explorer_raw_tree(
            self.dpt_explorer_trees["matchups"],
            raw_role_data.get("matchups", []),
            filter_text,
            empty_message="No matchup rows for this hero role.",
        )
        self._populate_dpt_explorer_raw_tree(
            self.dpt_explorer_trees["synergies"],
            raw_role_data.get("synergies", []),
            filter_text,
            empty_message="No synergy rows for this hero role.",
        )
        self._populate_dpt_explorer_pair_tree(
            self.dpt_explorer_trees["vs_scores"],
            score_role_data.get("pairs", {}).get("vs", {}),
            filter_text,
            empty_message="No VS score rows for this hero role.",
        )
        self._populate_dpt_explorer_pair_tree(
            self.dpt_explorer_trees["with_scores"],
            score_role_data.get("pairs", {}).get("with", {}),
            filter_text,
            empty_message="No WITH score rows for this hero role.",
        )

    def _format_dpt_explorer_summary_text(self, hero_name, role_key, raw_role_data, score_role_data):
        if not raw_role_data and not score_role_data:
            problems = [problem for problem in (self.dpt_library_load_error, self.dpt_scores_load_error) if problem]
            if problems:
                return "\n".join(problems)
            return "No DPT raw rows or scores are available for this hero role."

        lines = [
            f"{hero_name} ({self._role_label(role_key) if role_key else 'Unknown Role'})",
        ]

        if raw_role_data:
            lines.append(
                f"Raw rows: {len(raw_role_data.get('matchups', []))} matchups | {len(raw_role_data.get('synergies', []))} synergies"
            )
            source = raw_role_data.get("source", {})
            source_path = source.get("path")
            if source_path:
                lines.append(f"Source: {source_path}")
            updated_at = raw_role_data.get("updatedAt")
            if updated_at:
                lines.append(f"Updated: {updated_at}")

        if score_role_data:
            overall = score_role_data.get("overall", {})
            lines.append("")
            lines.append("Overall DPT Scores")
            for score_key in ("matchupWin", "synergyWin", "compositeWin", "matchupLane", "synergyLane"):
                score = overall.get(score_key, {})
                lines.append(
                    f"  {score_key}: raw {self._format_optional_number(score.get('raw'))} | "
                    f"norm {self._format_optional_number(score.get('normalized'), digits=2)} | "
                    f"conf {self._format_optional_number(score.get('confidence'), digits=4)} | "
                    f"rows {score.get('coveredRowCount', 0)}/{score.get('rowCount', 0)} | "
                    f"matches {score.get('totalMatches', 0)}"
                )

            role_priors = self.dpt_scores_data.get("heroes", {}).get(hero_name, {}).get("rolePriors", {})
            if role_priors:
                lines.append("")
                lines.append("Role Priors")
                for prior_role in sorted(role_priors, key=lambda role: ROLE_KEYS.index(role) if role in ROLE_KEYS else 99):
                    prior = role_priors[prior_role]
                    lines.append(
                        f"  {prior_role} - {prior.get('role')}: "
                        f"weight {self._format_optional_number(prior.get('weight'), digits=4)} | "
                        f"matches {prior.get('sampleMatches', 0)}"
                    )

        return "\n".join(lines)

    def _populate_dpt_explorer_raw_tree(self, tree, rows, filter_text, empty_message):
        filtered_rows = []
        for row in rows:
            hero_name = str(row.get("hero", ""))
            role_label = str(row.get("role", ""))
            haystack = f"{hero_name} {role_label}".lower()
            if filter_text and filter_text not in haystack:
                continue
            filtered_rows.append(row)

        filtered_rows.sort(
            key=lambda row: (
                -(int(row.get("matches") or 0)),
                -(float(row.get("winrate") or 0.0)),
                str(row.get("hero", "")),
            )
        )

        rows_to_insert = [
            (
                row.get("hero", ""),
                row.get("role", ""),
                self._format_optional_number(row.get("winrate"), digits=1),
                self._format_optional_number(row.get("laneAdvantage"), digits=1),
                int(row.get("matches") or 0),
            )
            for row in filtered_rows
        ]
        self._populate_tree_rows(tree, rows_to_insert, empty_message)

    def _populate_dpt_explorer_pair_tree(self, tree, pair_payload, filter_text, empty_message):
        rows = []
        for target_hero, target_data in pair_payload.items():
            for role_key, role_data in target_data.get("roles", {}).items():
                hero_and_role = f"{target_hero} {role_data.get('role', '')}".lower()
                if filter_text and filter_text not in hero_and_role:
                    continue
                win_score = role_data.get("win", {})
                lane_score = role_data.get("lane", {})
                rows.append(
                    (
                        target_hero,
                        role_data.get("role", self._role_label(role_key)),
                        self._format_optional_number(win_score.get("raw")),
                        self._format_optional_number(win_score.get("normalized"), digits=2),
                        self._format_optional_number(win_score.get("confidence"), digits=4),
                        self._format_optional_number(lane_score.get("raw")),
                        self._format_optional_number(lane_score.get("normalized"), digits=2),
                        self._format_optional_number(lane_score.get("confidence"), digits=4),
                    )
                )

        rows.sort(
            key=lambda item: (
                -(float(item[2]) if item[2] not in {"-", ""} else -999.0),
                item[0],
                item[1],
            )
        )
        self._populate_tree_rows(tree, rows, empty_message)

    def _populate_tree_rows(self, tree, rows, empty_message):
        for item_id in tree.get_children():
            tree.delete(item_id)

        if not rows:
            self._clear_tree_with_message(tree, empty_message)
            return

        for row in rows:
            tree.insert("", "end", values=row)
        self._apply_dpt_explorer_tree_sort(tree)

    def _clear_tree_with_message(self, tree, message):
        for item_id in tree.get_children():
            tree.delete(item_id)
        values = [message] + [""] * (len(tree["columns"]) - 1)
        tree.insert("", "end", values=tuple(values))

    def _format_optional_number(self, value, digits=4):
        if value is None:
            return "-"
        if isinstance(value, (int, float)):
            return f"{float(value):.{digits}f}"
        return str(value)

    def _handle_dpt_explorer_tree_sort(self, tree, column):
        current_state = self.dpt_explorer_tree_sort_state.get(str(tree), {})
        current_column = current_state.get("column")
        current_reverse = bool(current_state.get("reverse", False))

        if current_column == column:
            reverse = not current_reverse
        else:
            reverse = False

        self.dpt_explorer_tree_sort_state[str(tree)] = {
            "column": column,
            "reverse": reverse,
        }
        self._apply_dpt_explorer_tree_sort(tree)

    def _apply_dpt_explorer_tree_sort(self, tree):
        state = self.dpt_explorer_tree_sort_state.get(str(tree))
        if not state:
            return

        column = state.get("column")
        reverse = bool(state.get("reverse", False))
        if not column:
            return

        items = list(tree.get_children(""))
        if len(items) <= 1:
            return

        values = [
            (self._dpt_explorer_tree_sort_key(tree.set(item_id, column)), item_id)
            for item_id in items
        ]
        values.sort(key=lambda item: item[0], reverse=reverse)
        for index, (_sort_key, item_id) in enumerate(values):
            tree.move(item_id, "", index)

    def _dpt_explorer_tree_sort_key(self, value):
        text = str(value or "").strip()
        if text in {"", "-"}:
            return (2, 0.0, "")

        normalized = text.replace(",", "")
        try:
            return (0, float(normalized), text.lower())
        except ValueError:
            return (1, 0.0, text.lower())

    def _create_detail_text_tab(self, notebook, label):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=label)
        text_widget = tk.Text(tab, height=DRAFT_DETAIL_TEXT_HEIGHT, wrap="word")
        text_widget.pack(fill="both", expand=True)
        text_widget.configure(state="disabled")
        return text_widget

    def _create_summary_tree_tab(self, notebook, label):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=label)

        columns = ("hero", "synergy", "matchup", "total")
        tree = ttk.Treeview(tab, columns=columns, show="headings", height=DRAFT_SUMMARY_TREE_HEIGHT)
        tree.heading("hero", text="Hero")
        tree.heading("synergy", text="Synergy")
        tree.heading("matchup", text="Matchup")
        tree.heading("total", text="Total")
        tree.column("hero", width=220, anchor="w")
        tree.column("synergy", width=90, anchor="center")
        tree.column("matchup", width=90, anchor="center")
        tree.column("total", width=90, anchor="center")
        tree.pack(fill="both", expand=True)
        return tree

    def _create_dpt_summary_tree_tab(self, notebook, label):
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=label)

        columns = ("hero", "role", "draft", "win", "lane", "enemy", "ally", "ban", "conf")
        tree = ttk.Treeview(tab, columns=columns, show="headings", height=DRAFT_SUMMARY_TREE_HEIGHT)
        headings = {
            "hero": "Hero",
            "role": "Role",
            "draft": "Draft",
            "win": "Win",
            "lane": "Lane",
            "enemy": "Enemy",
            "ally": "Ally",
            "ban": "Ban",
            "conf": "Conf",
        }
        widths = {
            "hero": 180,
            "role": 95,
            "draft": 72,
            "win": 72,
            "lane": 72,
            "enemy": 72,
            "ally": 72,
            "ban": 72,
            "conf": 72,
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], anchor="center" if column != "hero" else "w")
        tree.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", self._handle_dpt_tree_select)
        return tree

    def _build_draft_category_grid(self, parent, attribute_key):
        heroes = self.heroes_by_attribute.get(attribute_key, [])
        for index, hero in enumerate(heroes):
            button = tk.Button(
                parent,
                text=hero,
                width=DRAFT_GRID_BUTTON_WIDTH,
                height=DRAFT_GRID_BUTTON_HEIGHT,
                wraplength=DRAFT_GRID_BUTTON_WRAP,
                justify="center",
                padx=DRAFT_GRID_BUTTON_PADX,
                pady=DRAFT_GRID_BUTTON_PADY,
                font=("Arial", 9),
                command=lambda selected_hero=hero: self._handle_draft_hero_click(selected_hero),
            )
            button.grid(
                row=index // DRAFT_GRID_COLUMNS,
                column=index % DRAFT_GRID_COLUMNS,
                sticky="w",
                padx=DRAFT_GRID_CELL_PADX,
                pady=DRAFT_GRID_CELL_PADY,
            )
            self.draft_hero_buttons[hero] = button

        parent.grid_anchor("w")
        for column in range(DRAFT_GRID_COLUMNS):
            parent.columnconfigure(column, weight=0)

    def _rebuild_edit_hero_grids(self):
        for attribute_key, frame in self.edit_grid_frames.items():
            for child in frame.winfo_children():
                child.destroy()

            heroes = self.heroes_by_attribute.get(attribute_key, [])
            for index, hero in enumerate(heroes):
                ttk.Button(
                    frame,
                    text=hero,
                    command=lambda selected_hero=hero: self._open_edit_hero(selected_hero),
                ).grid(
                    row=index // 4,
                    column=index % 4,
                    sticky="ew",
                    padx=4,
                    pady=4,
                )

            for column in range(4):
                frame.columnconfigure(column, weight=1)

    def _handle_edit_attribute_tab_change(self, _event=None):
        current_tab_id = self.edit_attribute_notebook.select()
        current_index = self.edit_attribute_notebook.index(current_tab_id)
        self.current_edit_attribute = ATTRIBUTE_ORDER[current_index][0]
        self._refresh_edit_search_results()

    def _refresh_edit_search_results(self):
        query = self.edit_search_var.get().strip().lower()
        heroes = self.heroes_by_attribute.get(self.current_edit_attribute, [])
        if not heroes:
            heroes = self.hero_names

        if query:
            startswith_matches = [hero for hero in heroes if hero.lower().startswith(query)]
            contains_matches = [
                hero for hero in heroes
                if query in hero.lower() and hero not in startswith_matches
            ]
            self.search_results = startswith_matches + contains_matches
        else:
            self.search_results = heroes[:]

        self.edit_search_listbox.delete(0, tk.END)
        for hero in self.search_results[:50]:
            self.edit_search_listbox.insert(tk.END, hero)

        if self.search_results:
            self.edit_search_listbox.selection_clear(0, tk.END)
            self.edit_search_listbox.selection_set(0)

    def _open_selected_search_result(self, _event=None):
        selection = self.edit_search_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.search_results):
                self._open_edit_hero(self.search_results[index])
                return

        if self.search_results:
            self._open_edit_hero(self.search_results[0])

    def _show_edit_selector(self):
        self.edit_detail_frame.pack_forget()
        self.edit_selector_frame.pack(fill="x", expand=True)

    def _open_edit_hero(self, hero_name):
        if hero_name not in self.heroes:
            return

        self.current_edit_hero = hero_name
        hero_attribute = self.hero_attributes.get(hero_name, "uni")
        self.edit_hero_title_var.set(hero_name)
        self.edit_hero_meta_var.set(
            f"{ATTRIBUTE_LABELS.get(hero_attribute, 'UNI')} hero | Editing library-dex.json"
        )

        record = self._ensure_hero_record(hero_name)
        self.loading_edit_values = True
        self.edit_default_role_var.set(record["default_role"])
        for hero_role in ROLE_KEYS:
            for box_type in BOX_TYPES:
                for target_role in ROLE_KEYS:
                    for score in SCORE_VALUES:
                        key = (hero_role, box_type, target_role, _score_key(score))
                        self.edit_score_vars[key].set(
                            record["roles"][hero_role][box_type][target_role][_score_key(score)]
                        )
        self.loading_edit_values = False

        self.edit_selector_frame.pack_forget()
        self.edit_detail_frame.pack(fill="both", expand=True)

    def _ensure_hero_record(self, hero_name):
        heroes_payload = self.library_data.setdefault("heroes", {})
        if hero_name not in heroes_payload:
            heroes_payload[hero_name] = _blank_hero_record()
        heroes_payload[hero_name] = self._normalize_hero_record(heroes_payload[hero_name])
        return heroes_payload[hero_name]

    def _handle_default_role_change(self):
        if self.loading_edit_values or not self.current_edit_hero:
            return

        role = self.edit_default_role_var.get()
        if role not in ROLE_KEYS:
            return

        record = self._ensure_hero_record(self.current_edit_hero)
        record["default_role"] = role
        self.edit_save_status_var.set(f"Saved {self.current_edit_hero} default role at {_timestamp()}.")
        self._queue_library_save()
        self._refresh_draft_outputs()

    def _handle_score_change(self, hero_role, box_type, target_role, score_key):
        if self.loading_edit_values or not self.current_edit_hero:
            return

        record = self._ensure_hero_record(self.current_edit_hero)
        record["roles"][hero_role][box_type][target_role][score_key] = self.edit_score_vars[
            (hero_role, box_type, target_role, score_key)
        ].get()
        self.edit_save_status_var.set(f"Saved {self.current_edit_hero} at {_timestamp()}.")
        self._queue_library_save()
        self._refresh_draft_outputs()

    def _normalize_score_entry(self, hero_role, box_type, target_role, score_key):
        if self.loading_edit_values or not self.current_edit_hero:
            return

        key = (hero_role, box_type, target_role, score_key)
        current_value = self.edit_score_vars[key].get()
        normalized_value = self._normalize_score_text(current_value)
        if normalized_value != current_value:
            self.edit_score_vars[key].set(normalized_value)

    def _normalize_score_text(self, text):
        tokens = self._split_score_tokens(text)
        if not tokens:
            return ""

        normalized_tokens = []
        seen = set()
        for token in tokens:
            hero_name = self._match_hero_name(token)
            final_value = hero_name or token.strip()
            dedupe_key = hero_name or final_value.lower()
            if final_value and dedupe_key not in seen:
                seen.add(dedupe_key)
                normalized_tokens.append(final_value)

        return ", ".join(normalized_tokens)

    def _split_score_tokens(self, text):
        return [token.strip() for token in re.split(r"[,;\n]+", str(text or "")) if token.strip()]

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

    def _queue_library_save(self):
        if self.library_save_after_id is not None:
            self.parent.after_cancel(self.library_save_after_id)
        self.library_save_after_id = self.parent.after(200, self._flush_library_save)

    def _flush_library_save(self):
        self.library_save_after_id = None
        _write_json_file(self.library_path, self.library_data)

    def _handle_your_role_change(self):
        your_role = self.your_role_var.get()
        self._save_app_state()

        if your_role in self.ally_assignments:
            del self.ally_assignments[your_role]

        if self.draft_action_var.get() == f"ally:{your_role}":
            self.draft_action_var.set("ban")

        self._refresh_draft_outputs()

    def _handle_draft_hero_click(self, hero_name):
        if hero_name not in self.heroes:
            return

        action = self.draft_action_var.get()
        if action == "ban":
            if hero_name in self.banned_heroes:
                self.banned_heroes.remove(hero_name)
            else:
                self._remove_hero_from_draft_state(hero_name)
                self.banned_heroes.add(hero_name)
        elif action == "enemy":
            if hero_name in self.enemy_assignments:
                del self.enemy_assignments[hero_name]
            else:
                self._remove_hero_from_draft_state(hero_name)
                self.enemy_assignments[hero_name] = self._get_default_role(hero_name)
        elif action.startswith("ally:"):
            ally_role = action.split(":", 1)[1]
            if ally_role not in ROLE_KEYS or ally_role == self.your_role_var.get():
                return
            if self.ally_assignments.get(ally_role) == hero_name:
                del self.ally_assignments[ally_role]
            else:
                self._remove_hero_from_draft_state(hero_name)
                self.ally_assignments[ally_role] = hero_name

        self._refresh_draft_outputs()

    def _remove_hero_from_draft_state(self, hero_name):
        self.banned_heroes.discard(hero_name)
        self.enemy_assignments.pop(hero_name, None)

        roles_to_clear = [role for role, hero in self.ally_assignments.items() if hero == hero_name]
        for role in roles_to_clear:
            del self.ally_assignments[role]

    def _get_default_role(self, hero_name):
        return self._ensure_hero_record(hero_name).get("default_role", "1")

    def _refresh_draft_outputs(self):
        self._refresh_ally_mode_buttons()
        self._refresh_draft_button_labels()
        self._refresh_pool_summary_labels()
        self._refresh_detail_texts()
        self._refresh_summary_tables()

    def _refresh_ally_mode_buttons(self):
        your_role = self.your_role_var.get()
        for role, button in self.ally_mode_buttons.items():
            if role == your_role:
                button.configure(state="disabled")
            else:
                button.configure(state="normal")

    def _refresh_draft_button_labels(self):
        for hero_name, button in self.draft_hero_buttons.items():
            if hero_name in self.banned_heroes:
                button.configure(text=f"X {hero_name}")
            elif hero_name in self.enemy_assignments:
                button.configure(text=f"E{self.enemy_assignments[hero_name]} {hero_name}")
            else:
                ally_role = self._find_ally_role(hero_name)
                if ally_role is not None:
                    button.configure(text=f"A{ally_role} {hero_name}")
                else:
                    button.configure(text=hero_name)

    def _find_ally_role(self, hero_name):
        for role, assigned_hero in self.ally_assignments.items():
            if assigned_hero == hero_name:
                return role
        return None

    def _refresh_pool_summary_labels(self):
        banned = ", ".join(sorted(self.banned_heroes)) if self.banned_heroes else "none"

        enemy_groups = {role: [] for role in ROLE_KEYS}
        for hero_name, role in sorted(self.enemy_assignments.items()):
            enemy_groups.setdefault(role, []).append(hero_name)
        enemy_parts = [
            f"Role {role}: {', '.join(names)}"
            for role, names in enemy_groups.items()
            if names
        ]

        ally_parts = [
            f"Role {role}: {hero_name}"
            for role, hero_name in sorted(self.ally_assignments.items(), key=lambda item: item[0])
        ]

        self.ban_summary_var.set(f"Bans: {banned}")
        self.enemy_summary_var.set(f"Enemies: {' | '.join(enemy_parts) if enemy_parts else 'none'}")
        self.ally_summary_var.set(f"Allies: {' | '.join(ally_parts) if ally_parts else 'none'}")

    def _refresh_detail_texts(self):
        your_role = self.your_role_var.get()
        banned_entries = [(hero_name, self._get_default_role(hero_name)) for hero_name in sorted(self.banned_heroes)]
        enemy_entries = sorted(self.enemy_assignments.items(), key=lambda item: (item[1], item[0]))
        ally_entries = sorted(self.ally_assignments.items(), key=lambda item: item[0])

        self._set_readonly_text(
            self.ban_detail_text,
            self._format_context_entries(
                [(hero, role) for hero, role in banned_entries],
                your_role,
                "Banned heroes",
            ),
        )
        self._set_readonly_text(
            self.enemy_detail_text,
            self._format_context_entries(enemy_entries, your_role, "Enemy heroes"),
        )
        self._set_readonly_text(
            self.ally_detail_text,
            self._format_context_entries(
                [(hero_name, role) for role, hero_name in ally_entries],
                your_role,
                "Allied heroes",
            ),
        )
        self._set_readonly_text(
            self.dpt_detail_text,
            self._default_dpt_detail_text(),
        )

    def _format_context_entries(self, entries, your_role, empty_label):
        if not entries:
            return f"No {empty_label.lower()} selected."

        sections = []
        for hero_name, role in entries:
            synergy_rows, matchup_rows = self._get_context_rows(hero_name, role, your_role)
            sections.append(f"{hero_name} (role {role} -> your role {your_role})")
            sections.append("  Synergy")
            sections.extend(self._format_score_rows(synergy_rows))
            sections.append("  Matchup")
            sections.extend(self._format_score_rows(matchup_rows))
            sections.append("")

        return "\n".join(sections).strip()

    def _format_score_rows(self, rows):
        lines = []
        has_content = False
        for score in SCORE_VALUES:
            value = str(rows.get(_score_key(score), "")).strip()
            if value:
                has_content = True
                label = f"{score:+d}" if score != 0 else "0"
                lines.append(f"    {label}: {value}")
        if not has_content:
            lines.append("    No saved content.")
        return lines

    def _get_context_rows(self, hero_name, hero_role, your_role):
        record = self._ensure_hero_record(hero_name)
        role_record = record["roles"].get(str(hero_role), _blank_role_record())
        synergy_rows = role_record["synergy"].get(str(your_role), _blank_score_rows())
        matchup_rows = role_record["matchup"].get(str(your_role), _blank_score_rows())
        return synergy_rows, matchup_rows

    def _set_readonly_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _refresh_summary_tables(self):
        banned_entries = [(hero_name, self._get_default_role(hero_name)) for hero_name in sorted(self.banned_heroes)]
        enemy_entries = sorted(self.enemy_assignments.items(), key=lambda item: (item[1], item[0]))
        ally_entries = [(hero_name, role) for role, hero_name in sorted(self.ally_assignments.items(), key=lambda item: item[0])]

        self._populate_summary_tree(self.draft_treeviews["bans"], self._aggregate_entries(banned_entries))
        self._populate_summary_tree(self.draft_treeviews["enemies"], self._aggregate_entries(enemy_entries))
        self._populate_summary_tree(self.draft_treeviews["allies"], self._aggregate_entries(ally_entries))
        self._populate_summary_tree(
            self.draft_treeviews["overall"],
            self._aggregate_entries(banned_entries + enemy_entries + ally_entries),
        )
        self._populate_summary_tree(
            self.draft_treeviews["role3"],
            self._score_candidate_role("3"),
        )
        dpt_rows = self._score_dpt_candidates(self.your_role_var.get())
        self._populate_dpt_summary_tree(self.draft_treeviews["dpt"], dpt_rows)

    def _aggregate_entries(self, entries):
        your_role = self.your_role_var.get()
        totals = {}

        for hero_name, role in entries:
            synergy_rows, matchup_rows = self._get_context_rows(hero_name, role, your_role)
            self._apply_rows_to_totals(totals, synergy_rows, "synergy")
            self._apply_rows_to_totals(totals, matchup_rows, "matchup")

        rows = []
        for hero_name, values in totals.items():
            total = values["synergy"] + values["matchup"]
            rows.append(
                (
                    hero_name,
                    values["synergy"],
                    values["matchup"],
                    total,
                )
            )

        rows.sort(key=lambda item: (-item[3], -item[2], -item[1], item[0]))
        return rows

    def _apply_rows_to_totals(self, totals, rows, key_name):
        for score in SCORE_VALUES:
            if score == 0:
                continue
            text = rows.get(_score_key(score), "")
            mentioned_heroes = self._extract_mentioned_heroes(text)
            for hero_name in mentioned_heroes:
                hero_totals = totals.setdefault(hero_name, {"synergy": 0, "matchup": 0})
                hero_totals[key_name] += score

    def _score_candidate_role(self, candidate_role):
        rows = []
        excluded_heroes = set(self.banned_heroes)
        excluded_heroes.update(self.enemy_assignments.keys())
        excluded_heroes.update(self.ally_assignments.values())

        for hero_name in self.hero_names:
            if hero_name in excluded_heroes:
                continue
            if not self._hero_has_role_content(hero_name, candidate_role):
                continue

            synergy_total, matchup_total = self._score_single_candidate(hero_name, candidate_role)
            total = synergy_total + matchup_total

            rows.append((hero_name, synergy_total, matchup_total, total))

        rows.sort(key=lambda item: (-item[3], -item[2], -item[1], item[0]))
        return rows

    def _hero_has_role_content(self, hero_name, hero_role):
        record = self._ensure_hero_record(hero_name)
        role_record = record["roles"].get(str(hero_role), _blank_role_record())
        for box_type in BOX_TYPES:
            for target_role in ROLE_KEYS:
                for value in role_record.get(box_type, {}).get(target_role, {}).values():
                    if str(value).strip():
                        return True
        return False

    def _score_single_candidate(self, hero_name, hero_role):
        record = self._ensure_hero_record(hero_name)
        role_record = record["roles"].get(str(hero_role), _blank_role_record())

        synergy_total = 0
        for ally_role, ally_hero in self.ally_assignments.items():
            synergy_rows = role_record["synergy"].get(str(ally_role), _blank_score_rows())
            synergy_total += self._score_rows_for_selected_hero(synergy_rows, ally_hero)

        matchup_total = 0
        for enemy_hero, enemy_role in self.enemy_assignments.items():
            matchup_rows = role_record["matchup"].get(str(enemy_role), _blank_score_rows())
            matchup_total += self._score_rows_for_selected_hero(matchup_rows, enemy_hero)

        return synergy_total, matchup_total

    def _score_rows_for_selected_hero(self, rows, selected_hero):
        total = 0
        for score in SCORE_VALUES:
            if score == 0:
                continue
            mentioned_heroes = self._extract_mentioned_heroes(rows.get(_score_key(score), ""))
            if selected_hero in mentioned_heroes:
                total += score
        return total

    def _extract_mentioned_heroes(self, text):
        token_matches = {
            hero_name
            for token in self._split_score_tokens(text)
            for hero_name in [self._match_hero_name(token)]
            if hero_name
        }
        if token_matches:
            return token_matches

        normalized_text = _normalize_match_text(text)
        if not normalized_text:
            return set()

        padded_text = f" {normalized_text} "
        matches = set()
        for hero_name, normalized_hero in self.hero_match_names.items():
            if not normalized_hero:
                continue
            if f" {normalized_hero} " in padded_text:
                matches.add(hero_name)
        return matches

    def _populate_summary_tree(self, tree, rows):
        for item_id in tree.get_children():
            tree.delete(item_id)

        if not rows:
            tree.insert("", "end", values=("No hero totals yet", "", "", ""))
            return

        for hero_name, synergy, matchup, total in rows:
            tree.insert("", "end", values=(hero_name, synergy, matchup, total))

    def _score_dpt_candidates(self, candidate_role):
        self.latest_dpt_candidate_rows = []
        self.latest_dpt_candidate_lookup = {}

        if not score_dpt_candidate or not finalize_dpt_candidate_normalization:
            return []
        if candidate_role not in ROLE_KEYS:
            return []

        heroes_payload = self.dpt_scores_data.get("heroes", {})
        if not isinstance(heroes_payload, dict) or not heroes_payload:
            return []

        allies = [
            (hero_name, role)
            for role, hero_name in sorted(self.ally_assignments.items(), key=lambda item: item[0])
            if role in ROLE_KEYS and hero_name in heroes_payload
        ]
        enemies = [
            (hero_name, None)
            for hero_name in sorted(self.enemy_assignments)
            if hero_name in heroes_payload
        ]
        bans = [
            (hero_name, None)
            for hero_name in sorted(self.banned_heroes)
            if hero_name in heroes_payload
        ]

        excluded_heroes = {hero_name for hero_name, _role in allies + enemies + bans}
        rows = []
        for hero_name in sorted(heroes_payload):
            if hero_name in excluded_heroes:
                continue
            candidate = score_dpt_candidate(
                self.dpt_scores_data,
                hero_name,
                candidate_role,
                allies,
                enemies,
                bans,
            )
            if candidate is not None:
                rows.append(candidate)

        if not rows:
            return []

        finalize_dpt_candidate_normalization(rows)
        rows.sort(
            key=lambda row: (
                -row["draft"]["compositeNormalized"],
                -row["draft"]["winNormalized"],
                -row["draft"]["confidence"],
                row["hero"],
            )
        )
        self.latest_dpt_candidate_rows = rows
        return rows

    def _populate_dpt_summary_tree(self, tree, rows):
        for item_id in tree.get_children():
            tree.delete(item_id)

        self.latest_dpt_candidate_lookup = {}

        if not rows:
            message = self.dpt_scores_load_error or "No DPT candidates available for the current draft."
            tree.insert(
                "",
                "end",
                iid="empty",
                values=(message, "", "", "", "", "", "", "", ""),
            )
            self._set_readonly_text(self.dpt_detail_text, self._default_dpt_detail_text())
            return

        for index, row in enumerate(rows):
            item_id = f"dpt-{index}"
            self.latest_dpt_candidate_lookup[item_id] = row
            tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    row["hero"],
                    row["role"],
                    f"{row['draft']['compositeNormalized']:.2f}",
                    f"{row['draft']['winNormalized']:.2f}",
                    f"{row['draft']['laneNormalized']:.2f}",
                    f"{self._dpt_component_composite(row, 'enemy'):+.2f}",
                    f"{self._dpt_component_composite(row, 'ally'):+.2f}",
                    f"{self._dpt_component_composite(row, 'ban'):+.2f}",
                    f"{row['draft']['confidence']:.2f}",
                ),
            )

        first_item = tree.get_children()[0]
        tree.selection_set(first_item)
        tree.focus(first_item)
        self._handle_dpt_tree_select()

    def _dpt_component_composite(self, row, component_name):
        components = row.get("components", {})
        if component_name == "enemy":
            return (
                (DPT_DRAFT_WEIGHTS["composite_win"] * (components.get("enemyWinRaw") or 0.0))
                + (DPT_DRAFT_WEIGHTS["composite_lane"] * (components.get("enemyLaneRaw") or 0.0))
            )
        if component_name == "ally":
            return (
                (DPT_DRAFT_WEIGHTS["composite_win"] * DPT_DRAFT_WEIGHTS["ally"] * (components.get("allyWinRaw") or 0.0))
                + (DPT_DRAFT_WEIGHTS["composite_lane"] * DPT_DRAFT_WEIGHTS["ally_lane"] * (components.get("allyLaneRaw") or 0.0))
            )
        if component_name == "ban":
            return (
                (DPT_DRAFT_WEIGHTS["composite_win"] * DPT_DRAFT_WEIGHTS["ban_relief"] * (components.get("banReliefWinRaw") or 0.0))
                + (DPT_DRAFT_WEIGHTS["composite_lane"] * DPT_DRAFT_WEIGHTS["ban_relief_lane"] * (components.get("banReliefLaneRaw") or 0.0))
            )
        return 0.0

    def _default_dpt_detail_text(self):
        if self.dpt_scores_load_error:
            return self.dpt_scores_load_error
        if not self.latest_dpt_candidate_rows:
            return "No DPT candidates available for this draft state yet."
        top_row = self.latest_dpt_candidate_rows[0]
        return (
            "Select a row in DPT Picks for the full breakdown.\n\n"
            f"Top suggestion: {top_row['hero']} ({top_row['role']})\n"
            f"Draft {top_row['draft']['compositeNormalized']:.2f} | "
            f"Win {top_row['draft']['winNormalized']:.2f} | "
            f"Lane {top_row['draft']['laneNormalized']:.2f} | "
            f"Confidence {top_row['draft']['confidence']:.2f}"
        )

    def _handle_dpt_tree_select(self, _event=None):
        tree = self.draft_treeviews.get("dpt")
        if not tree:
            return
        selection = tree.selection()
        if not selection:
            self._set_readonly_text(self.dpt_detail_text, self._default_dpt_detail_text())
            return

        row = self.latest_dpt_candidate_lookup.get(selection[0])
        if not row:
            self._set_readonly_text(self.dpt_detail_text, self._default_dpt_detail_text())
            return

        self._set_readonly_text(self.dpt_detail_text, self._format_dpt_candidate_detail(row))

    def _format_dpt_candidate_detail(self, row):
        lines = [
            f"{row['hero']} ({row['role']})",
            (
                f"Draft {row['draft']['compositeNormalized']:.2f} | "
                f"Win {row['draft']['winNormalized']:.2f} | "
                f"Lane {row['draft']['laneNormalized']:.2f} | "
                f"Confidence {row['draft']['confidence']:.2f}"
            ),
            "",
            "Baseline",
            (
                f"  Composite win raw {row['baseline']['compositeWinRaw']:+.2f} "
                f"(norm {row['baseline'].get('compositeWinNormalized')}, "
                f"conf {row['baseline']['compositeWinConfidence']:.2f})"
            ),
            (
                f"  Lane raw {row['baseline']['laneRaw']:+.2f} "
                f"(conf {row['baseline']['laneConfidence']:.2f})"
            ),
            "",
            "Draft Components",
            self._format_dpt_component_line(
                "Enemy win avg",
                row["components"]["enemyWinRaw"],
                row["components"].get("enemyWinDirectRaw"),
                row["components"].get("enemyWinReciprocalRaw"),
            ),
            self._format_dpt_component_line(
                "Enemy lane avg",
                row["components"]["enemyLaneRaw"],
                row["components"].get("enemyLaneDirectRaw"),
                row["components"].get("enemyLaneReciprocalRaw"),
            ),
            self._format_dpt_component_line(
                "Ally win avg",
                row["components"]["allyWinRaw"],
                row["components"].get("allyWinDirectRaw"),
                row["components"].get("allyWinReciprocalRaw"),
            ),
            self._format_dpt_component_line(
                "Ally lane avg",
                row["components"]["allyLaneRaw"],
                row["components"].get("allyLaneDirectRaw"),
                row["components"].get("allyLaneReciprocalRaw"),
            ),
            self._format_dpt_component_line(
                "Ban relief win avg",
                row["components"]["banReliefWinRaw"],
                row["components"].get("banReliefWinDirectRaw"),
                row["components"].get("banReliefWinReciprocalRaw"),
            ),
            self._format_dpt_component_line(
                "Ban relief lane avg",
                row["components"]["banReliefLaneRaw"],
                row["components"].get("banReliefLaneDirectRaw"),
                row["components"].get("banReliefLaneReciprocalRaw"),
            ),
            "",
            "Enemy Picks",
        ]
        lines.extend(self._format_dpt_interaction_details(row["details"].get("enemy", []), kind="enemy"))
        lines.append("")
        lines.append("Allied Picks")
        lines.extend(self._format_dpt_interaction_details(row["details"].get("ally", []), kind="ally"))
        lines.append("")
        lines.append("Ban Relief")
        lines.extend(self._format_dpt_interaction_details(row["details"].get("ban", []), kind="ban"))
        return "\n".join(lines).strip()

    def _format_dpt_component_line(self, label, combined, direct, reciprocal):
        return (
            f"  {label} {float(combined or 0.0):+.2f} "
            f"(direct {float(direct or 0.0):+.2f} | reciprocal {float(reciprocal or 0.0):+.2f})"
        )

    def _format_dpt_interaction_details(self, details, kind):
        if not details:
            return ["  None."]

        lines = []
        for detail in details:
            header = detail["hero"]
            if detail.get("role"):
                header = f"{header} ({detail['role']})"
            lines.append(f"  {header}")
            if kind == "ban":
                lines.append(
                    f"    Base win {detail.get('baseWinRaw', 0.0):+.2f} | "
                    f"base lane {detail.get('baseLaneRaw', 0.0):+.2f}"
                )
                lines.append(
                    f"    Relief win {detail.get('reliefWinRaw', 0.0):+.2f} | "
                    f"relief lane {detail.get('reliefLaneRaw', 0.0):+.2f}"
                )
            else:
                lines.append(
                    f"    Win {detail.get('winRaw', 0.0):+.2f} | "
                    f"lane {detail.get('laneRaw', 0.0):+.2f}"
                )
            lines.extend(self._format_dpt_view_lines("Win", detail.get("winViews", {})))
            lines.extend(self._format_dpt_view_lines("Lane", detail.get("laneViews", {})))
            if kind == "ban":
                relief_views = detail.get("reliefViews", {})
                lines.append(
                    "    Relief split: "
                    f"win direct {float(relief_views.get('win', {}).get('direct') or 0.0):+.2f} | "
                    f"win reciprocal {float(relief_views.get('win', {}).get('reciprocal') or 0.0):+.2f} | "
                    f"lane direct {float(relief_views.get('lane', {}).get('direct') or 0.0):+.2f} | "
                    f"lane reciprocal {float(relief_views.get('lane', {}).get('reciprocal') or 0.0):+.2f}"
                )
        return lines

    def _format_dpt_view_lines(self, label, views):
        lines = []
        combined = views.get("combined", {})
        direct = views.get("direct", {})
        reciprocal = views.get("reciprocal", {})

        if combined.get("available"):
            weights = combined.get("weights", {})
            weight_text = ""
            if weights:
                weight_text = (
                    " | weights "
                    f"direct {float(weights.get('direct') or 0.0):.2f}, "
                    f"reciprocal {float(weights.get('reciprocal') or 0.0):.2f}"
                )
            lines.append(
                f"    {label} combined {float(combined.get('raw') or 0.0):+.2f} "
                f"(conf {float(combined.get('confidence') or 0.0):.2f}{weight_text})"
            )
        else:
            lines.append(f"    {label} combined: no DPT pair data.")

        lines.extend(self._format_dpt_single_view_lines(f"{label} direct", direct))
        lines.extend(self._format_dpt_single_view_lines(f"{label} reciprocal", reciprocal))
        return lines

    def _format_dpt_single_view_lines(self, label, view):
        if not view.get("available"):
            return [f"      {label}: no DPT pair data."]

        lines = [
            f"      {label}: {float(view.get('raw') or 0.0):+.2f} "
            f"(conf {float(view.get('confidence') or 0.0):.2f})"
        ]
        resolved_roles = view.get("resolvedRoles", [])
        if resolved_roles:
            role_bits = []
            for role_info in resolved_roles:
                weight = float(role_info.get("weight") or 0.0)
                role_bits.append(
                    f"{role_info.get('role') or role_info.get('roleKey')} {weight:.2f}"
                )
            lines.append(f"        Roles: {', '.join(role_bits)}")
        return lines

    def _save_current_draft(self):
        name = self.draft_name_var.get().strip() or f"Draft {_timestamp()}"

        draft_payload = {
            "name": name,
            "saved_at": _timestamp(),
            "your_role": self.your_role_var.get(),
            "bans": sorted(self.banned_heroes),
            "enemy_assignments": dict(sorted(self.enemy_assignments.items())),
            "ally_assignments": dict(sorted(self.ally_assignments.items())),
            "notes": self.draft_notes_text.get("1.0", tk.END).strip(),
        }

        normalized_draft = self._normalize_saved_draft(draft_payload)
        drafts = [draft for draft in self.saved_drafts_data["drafts"] if draft.get("name") != name]
        drafts.insert(0, normalized_draft)
        self.saved_drafts_data["drafts"] = drafts
        _write_json_file(self.saved_drafts_path, self.saved_drafts_data)
        self._refresh_saved_drafts_listbox(selected_name=name)
        self.draft_status_var.set(f"Saved draft '{name}' to saved-drafts.json.")

    def _clear_current_draft(self):
        self.banned_heroes.clear()
        self.enemy_assignments.clear()
        self.ally_assignments.clear()
        self.draft_name_var.set("")
        self.draft_notes_text.delete("1.0", tk.END)
        self.draft_status_var.set("Draft cleared.")
        self._refresh_draft_outputs()

    def _refresh_saved_drafts_listbox(self, selected_name=None):
        self.saved_drafts_listbox.delete(0, tk.END)
        selected_index = None
        for index, draft in enumerate(self.saved_drafts_data["drafts"]):
            label = f"{draft.get('name', 'Unnamed')} | {draft.get('saved_at', '')}"
            self.saved_drafts_listbox.insert(tk.END, label)
            if draft.get("name") == selected_name:
                selected_index = index

        if selected_index is not None:
            self.saved_drafts_listbox.selection_clear(0, tk.END)
            self.saved_drafts_listbox.selection_set(selected_index)

    def _load_selected_draft(self):
        selection = self.saved_drafts_listbox.curselection()
        if not selection:
            self.draft_status_var.set("Select a saved draft first.")
            return

        draft = self.saved_drafts_data["drafts"][selection[0]]
        self.your_role_var.set(draft.get("your_role", "1"))
        self.banned_heroes = set(draft.get("bans", []))
        self.enemy_assignments = dict(draft.get("enemy_assignments", {}))
        self.ally_assignments = dict(draft.get("ally_assignments", {}))
        self.draft_name_var.set(draft.get("name", ""))
        self.draft_notes_text.delete("1.0", tk.END)
        self.draft_notes_text.insert("1.0", draft.get("notes", ""))
        self.draft_status_var.set(f"Loaded draft '{draft.get('name', '')}'.")
        self._handle_your_role_change()

    def _delete_selected_draft(self):
        selection = self.saved_drafts_listbox.curselection()
        if not selection:
            self.draft_status_var.set("Select a saved draft first.")
            return

        draft = self.saved_drafts_data["drafts"].pop(selection[0])
        _write_json_file(self.saved_drafts_path, self.saved_drafts_data)
        self._refresh_saved_drafts_listbox()
        self.draft_status_var.set(f"Deleted draft '{draft.get('name', '')}'.")
