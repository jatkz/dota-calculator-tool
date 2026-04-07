import json
import os
import tkinter as tk
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import messagebox, ttk


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


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_gold_value(value):
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    if text == "-":
        return None
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def _format_gold(value):
    return f"{int(value):,}"


def _normalize_choice(value, choices):
    text = str(value or "").strip()
    if not text:
        return ""
    return next((choice for choice in choices if choice.lower() == text.lower()), "")


def _counter_to_tuple(counter):
    return tuple(sorted((name, count) for name, count in counter.items() if count > 0))


@dataclass(frozen=True)
class AcquisitionPlan:
    spent_gold: int | None
    consumed_items: tuple = field(default_factory=tuple)

    @property
    def consumed_count(self):
        return sum(count for _name, count in self.consumed_items)


class BuildItemRow:
    def __init__(
        self,
        parent,
        item_choices,
        on_change,
        on_move_up,
        on_move_down,
        on_delete,
        item_name="",
        use_prior_items=True,
    ):
        self.parent = parent
        self.item_choices = item_choices
        self.on_change = on_change
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.on_delete = on_delete

        self.frame = ttk.Frame(parent)
        self.controls_frame = ttk.Frame(self.frame)
        self.controls_frame.pack(fill="x")
        self.position_var = tk.StringVar(value="#1")
        self.item_var = tk.StringVar(value=item_name)
        self.cost_var = tk.StringVar(value="")
        self.detail_var = tk.StringVar(value="")
        self.use_prior_items_var = tk.BooleanVar(value=use_prior_items)

        ttk.Label(self.controls_frame, textvariable=self.position_var, width=4).pack(side="left", padx=(0, 8))

        self.item_combo = ttk.Combobox(
            self.controls_frame,
            textvariable=self.item_var,
            values=self.item_choices,
            state="normal",
            width=28,
        )
        self.item_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.item_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_change())
        self.item_combo.bind("<KeyRelease>", self._handle_keyrelease)
        self.item_combo.bind("<FocusOut>", lambda _event: self._normalize_value())

        ttk.Checkbutton(
            self.controls_frame,
            text="Use earlier items",
            variable=self.use_prior_items_var,
            command=self.on_change,
        ).pack(side="left", padx=(0, 8))

        ttk.Label(self.controls_frame, text="Spend").pack(side="left", padx=(0, 4))
        ttk.Label(self.controls_frame, textvariable=self.cost_var, width=10).pack(side="left", padx=(0, 8))

        ttk.Button(self.controls_frame, text="Up", width=5, command=lambda: self.on_move_up(self)).pack(side="left", padx=2)
        ttk.Button(self.controls_frame, text="Down", width=5, command=lambda: self.on_move_down(self)).pack(side="left", padx=2)
        ttk.Button(self.controls_frame, text="Remove", command=lambda: self.on_delete(self)).pack(side="left", padx=(6, 0))

        ttk.Label(
            self.frame,
            textvariable=self.detail_var,
            foreground="#666",
            wraplength=860,
        ).pack(anchor="w", padx=(42, 0), pady=(2, 0))

        self.item_var.trace_add("write", lambda *_args: self.on_change())

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def destroy(self):
        self.frame.destroy()

    def get_item_name(self):
        return self.item_var.get().strip()

    def set_position(self, position):
        self.position_var.set(f"#{position}")

    def set_cost_text(self, text):
        self.cost_var.set(text)

    def set_detail_text(self, text):
        self.detail_var.set(text)

    def uses_prior_items(self):
        return bool(self.use_prior_items_var.get())

    def _normalize_value(self):
        current = self.get_item_name()
        if not current:
            self.item_var.set("")
            self.on_change()
            return

        exact = _normalize_choice(current, self.item_choices)
        if exact:
            self.item_var.set(exact)
            self.on_change()

    def _handle_keyrelease(self, event):
        if event.keysym in {"Up", "Down", "Left", "Right", "Tab", "Return", "Escape"}:
            self.on_change()
            return

        widget = event.widget
        current = widget.get()
        cursor = widget.index(tk.INSERT)
        selection = widget.selection_present()

        should_autocomplete = selection or cursor == len(current)
        if should_autocomplete and current.strip():
            match = next(
                (choice for choice in self.item_choices if choice.lower().startswith(current.lower())),
                None,
            )
            if match and match != current:
                widget.delete(0, tk.END)
                widget.insert(0, match)
                widget.icursor(len(current))
                widget.select_range(len(current), tk.END)
                self.item_var.set(match)
                self.on_change()
                return

        self.on_change()


class BuildPlannerApp:
    SAVE_FILENAME = "saved-builds.json"
    ROLE_CHOICES = tuple(f"Pos {index}" for index in range(1, 6))

    def __init__(self, parent):
        self.parent = parent
        self.base_dir = os.path.dirname(__file__)
        self.dataset_path = os.path.join(self.base_dir, "dataset.json")
        self.saved_builds_path = os.path.join(self.base_dir, self.SAVE_FILENAME)

        self.dataset_payload = _load_json_file(self.dataset_path, {"heroesCore": {}, "items": {}})
        self.heroes = self._load_heroes()
        self.items = self._load_items()

        self.hero_names = sorted(self.heroes.keys())
        self.item_names = sorted(self.items.keys())

        self.saved_builds_data = self._load_saved_builds_data()
        self.current_build_id = None
        self.loading_build = False
        self.item_rows = []
        self.current_total_cost = 0

        self.build_name_var = tk.StringVar(value="")
        self.hero_var = tk.StringVar(value="")
        self.role_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="Pick a hero and start adding items.")
        self.role_summary_var = tk.StringVar(value="Role position is optional. Use Pos 1-5.")
        self.editor_state_var = tk.StringVar(value="Creating a new build.")
        self.status_var = tk.StringVar(value=f"Builds save to {self.SAVE_FILENAME}.")

        self._create_widgets()
        self.add_item_row()
        self._refresh_saved_builds_tree()
        self._refresh_role_choices()
        self._refresh_current_build_view()

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

    def _load_saved_builds_data(self):
        payload = _load_json_file(self.saved_builds_path, {"builds": []})
        source_builds = payload.get("builds", [])
        if not isinstance(source_builds, list):
            source_builds = []

        normalized_builds = []
        seen_ids = set()
        for build in source_builds:
            if not isinstance(build, dict):
                continue
            normalized = self._normalize_build_record(build)
            if normalized["id"] in seen_ids:
                normalized["id"] = uuid.uuid4().hex
            seen_ids.add(normalized["id"])
            normalized_builds.append(normalized)

        normalized_payload = {"builds": normalized_builds}
        _write_json_file(self.saved_builds_path, normalized_payload)
        return normalized_payload

    def _normalize_build_record(self, record):
        hero_name = _normalize_choice(record.get("hero"), self.hero_names)
        role_name = self._normalize_role_value(record.get("role"))

        items = []
        item_payload = record.get("items", [])
        if not isinstance(item_payload, list):
            item_payload = []
        for item_entry in item_payload:
            normalized_item = self._normalize_item_entry(item_entry)
            if normalized_item:
                items.append(normalized_item)

        return {
            "id": str(record.get("id") or uuid.uuid4().hex),
            "name": str(record.get("name") or "").strip(),
            "hero": hero_name,
            "role": role_name,
            "items": items,
            "created_at": str(record.get("created_at") or ""),
            "updated_at": str(record.get("updated_at") or ""),
        }

    def _normalize_item_entry(self, item_entry):
        use_prior_items = True
        if isinstance(item_entry, dict):
            item_name = item_entry.get("name")
            use_prior_items = self._coerce_use_prior_items(item_entry.get("use_prior_items", True))
        else:
            item_name = item_entry

        normalized_item = _normalize_choice(item_name, self.item_names)
        if not normalized_item:
            return None

        return {
            "name": normalized_item,
            "use_prior_items": use_prior_items,
        }

    def _coerce_use_prior_items(self, value):
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off"}
        if value is None:
            return True
        return bool(value)

    def _normalize_role_value(self, value):
        text = str(value or "").strip()
        if not text:
            return ""

        normalized = _normalize_choice(text, self.ROLE_CHOICES)
        if normalized:
            return normalized

        compact = "".join(character.lower() for character in text if character.isalnum())
        role_aliases = {
            "1": "Pos 1",
            "pos1": "Pos 1",
            "position1": "Pos 1",
            "role1": "Pos 1",
            "2": "Pos 2",
            "pos2": "Pos 2",
            "position2": "Pos 2",
            "role2": "Pos 2",
            "3": "Pos 3",
            "pos3": "Pos 3",
            "position3": "Pos 3",
            "role3": "Pos 3",
            "4": "Pos 4",
            "pos4": "Pos 4",
            "position4": "Pos 4",
            "role4": "Pos 4",
            "5": "Pos 5",
            "pos5": "Pos 5",
            "position5": "Pos 5",
            "role5": "Pos 5",
        }
        return role_aliases.get(compact, text)

    def _role_choice_values(self, current_role=""):
        values = ["", *self.ROLE_CHOICES]
        if current_role and current_role not in values:
            values.append(current_role)
        return values

    def _create_widgets(self):
        canvas = tk.Canvas(self.parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas, padding="16")

        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        ttk.Label(content, text="Build Planner", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            content,
            text="Create hero builds, keep the item buy order, and save them for later.",
            foreground="#666",
        ).pack(anchor="w", pady=(0, 12))

        details_frame = ttk.LabelFrame(content, text="Build Details")
        details_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(details_frame, text="Build Name").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        ttk.Entry(details_frame, textvariable=self.build_name_var, width=32).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 12),
            pady=8,
        )

        ttk.Label(details_frame, text="Hero").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=8)
        self.hero_combo = ttk.Combobox(
            details_frame,
            textvariable=self.hero_var,
            values=self.hero_names,
            state="normal",
            width=24,
        )
        self.hero_combo.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=8)

        ttk.Label(details_frame, text="Role").grid(row=0, column=4, sticky="w", padx=(0, 6), pady=8)
        self.role_combo = ttk.Combobox(
            details_frame,
            textvariable=self.role_var,
            values=self._role_choice_values(),
            state="normal",
            width=20,
        )
        self.role_combo.grid(row=0, column=5, sticky="w", padx=(0, 10), pady=8)

        action_row = ttk.Frame(details_frame)
        action_row.grid(row=1, column=0, columnspan=6, sticky="ew", padx=10, pady=(0, 10))

        ttk.Button(action_row, text="Save Build", command=self.save_current_build).pack(side="left")
        ttk.Button(action_row, text="Clear Editor", command=self.clear_editor).pack(side="left", padx=(8, 0))
        ttk.Label(action_row, textvariable=self.editor_state_var, foreground="#666").pack(side="left", padx=(12, 0))

        ttk.Label(details_frame, textvariable=self.summary_var).grid(
            row=2,
            column=0,
            columnspan=6,
            sticky="w",
            padx=10,
            pady=(0, 4),
        )
        ttk.Label(details_frame, textvariable=self.role_summary_var, foreground="#666").grid(
            row=3,
            column=0,
            columnspan=6,
            sticky="w",
            padx=10,
            pady=(0, 10),
        )

        body = ttk.Frame(content)
        body.pack(fill="both", expand=True)

        editor_frame = ttk.Frame(body)
        editor_frame.pack(side="left", fill="both", expand=True, padx=(0, 12))

        library_frame = ttk.Frame(body)
        library_frame.pack(side="left", fill="both")

        items_frame = ttk.LabelFrame(editor_frame, text="Item Buy Order")
        items_frame.pack(fill="x", pady=(0, 12))

        item_actions = ttk.Frame(items_frame)
        item_actions.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(item_actions, text="+ Add Item", command=self.add_item_row).pack(side="left")
        ttk.Button(item_actions, text="Clear Items", command=self.clear_item_rows).pack(side="left", padx=(8, 0))

        ttk.Label(
            items_frame,
            text="Reorder items with Up/Down to keep the exact sequence you want to buy.",
            foreground="#666",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        self.items_container = ttk.Frame(items_frame)
        self.items_container.pack(fill="x", padx=10, pady=(0, 10))

        summary_frame = ttk.LabelFrame(editor_frame, text="Stacked Cost Summary")
        summary_frame.pack(fill="both", expand=True)

        summary_tree_frame = ttk.Frame(summary_frame)
        summary_tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.summary_tree = ttk.Treeview(
            summary_tree_frame,
            columns=("order", "item", "spend", "running_total", "details"),
            show="headings",
            height=14,
        )
        self.summary_tree.heading("order", text="Order")
        self.summary_tree.heading("item", text="Item")
        self.summary_tree.heading("spend", text="Spend")
        self.summary_tree.heading("running_total", text="Running Spend")
        self.summary_tree.heading("details", text="How It Was Bought")
        self.summary_tree.column("order", width=70, anchor="center")
        self.summary_tree.column("item", width=210, anchor="w")
        self.summary_tree.column("spend", width=110, anchor="e")
        self.summary_tree.column("running_total", width=130, anchor="e")
        self.summary_tree.column("details", width=360, anchor="w")

        summary_scrollbar = ttk.Scrollbar(summary_tree_frame, orient="vertical", command=self.summary_tree.yview)
        self.summary_tree.configure(yscrollcommand=summary_scrollbar.set)

        self.summary_tree.pack(side="left", fill="both", expand=True)
        summary_scrollbar.pack(side="right", fill="y")

        saved_frame = ttk.LabelFrame(library_frame, text="Saved Builds")
        saved_frame.pack(fill="both", expand=True)

        saved_tree_frame = ttk.Frame(saved_frame)
        saved_tree_frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        self.saved_builds_tree = ttk.Treeview(
            saved_tree_frame,
            columns=("name", "hero", "role", "items", "gold", "updated"),
            show="headings",
            height=20,
        )
        self.saved_builds_tree.heading("name", text="Build")
        self.saved_builds_tree.heading("hero", text="Hero")
        self.saved_builds_tree.heading("role", text="Role")
        self.saved_builds_tree.heading("items", text="Items")
        self.saved_builds_tree.heading("gold", text="Gold")
        self.saved_builds_tree.heading("updated", text="Updated")
        self.saved_builds_tree.column("name", width=200, anchor="w")
        self.saved_builds_tree.column("hero", width=140, anchor="w")
        self.saved_builds_tree.column("role", width=100, anchor="w")
        self.saved_builds_tree.column("items", width=60, anchor="center")
        self.saved_builds_tree.column("gold", width=90, anchor="e")
        self.saved_builds_tree.column("updated", width=150, anchor="w")

        saved_scrollbar = ttk.Scrollbar(saved_tree_frame, orient="vertical", command=self.saved_builds_tree.yview)
        self.saved_builds_tree.configure(yscrollcommand=saved_scrollbar.set)

        self.saved_builds_tree.pack(side="left", fill="both", expand=True)
        saved_scrollbar.pack(side="right", fill="y")

        saved_actions = ttk.Frame(saved_frame)
        saved_actions.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(saved_actions, text="Load Selected", command=self.load_selected_build).pack(side="left")
        ttk.Button(saved_actions, text="Delete Selected", command=self.delete_selected_build).pack(side="left", padx=(8, 0))

        ttk.Label(saved_frame, textvariable=self.status_var, foreground="#666", wraplength=650).pack(
            anchor="w",
            padx=10,
            pady=(0, 10),
        )

        self.hero_combo.bind("<<ComboboxSelected>>", lambda _event: self._handle_hero_change())
        self.hero_combo.bind("<KeyRelease>", lambda event: self._handle_combobox_keyrelease(event, self.hero_var, self.hero_names, self._handle_hero_change))
        self.hero_combo.bind("<FocusOut>", lambda _event: self._normalize_combobox_value(self.hero_var, self.hero_names, self._handle_hero_change))

        self.role_combo.bind("<<ComboboxSelected>>", lambda _event: self._handle_role_change())
        self.role_combo.bind("<KeyRelease>", lambda event: self._handle_combobox_keyrelease(event, self.role_var, self.role_combo.cget("values"), self._refresh_current_build_view))
        self.role_combo.bind("<FocusOut>", lambda _event: self._handle_role_change())

        self.saved_builds_tree.bind("<Double-1>", lambda _event: self.load_selected_build())

    def _normalize_combobox_value(self, variable, values, callback):
        current = str(variable.get()).strip()
        if not current:
            variable.set("")
            callback()
            return

        exact = _normalize_choice(current, values)
        if exact:
            variable.set(exact)
        callback()

    def _handle_combobox_keyrelease(self, event, variable, values, callback):
        if event.keysym in {"Up", "Down", "Left", "Right", "Tab", "Return", "Escape"}:
            callback()
            return

        widget = event.widget
        current = widget.get()
        cursor = widget.index(tk.INSERT)
        selection = widget.selection_present()

        should_autocomplete = selection or cursor == len(current)
        if should_autocomplete and current.strip():
            match = next((choice for choice in values if choice.lower().startswith(current.lower())), None)
            if match and match != current:
                widget.delete(0, tk.END)
                widget.insert(0, match)
                widget.icursor(len(current))
                widget.select_range(len(current), tk.END)
                variable.set(match)
                callback()
                return

        callback()

    def _handle_hero_change(self):
        self._refresh_role_choices()
        self._refresh_current_build_view()

    def _handle_role_change(self):
        normalized_role = self._normalize_role_value(self.role_var.get())
        self.role_var.set(normalized_role)
        self._refresh_role_choices()
        self._refresh_current_build_view()

    def _refresh_role_choices(self):
        current_role = self._normalize_role_value(self.role_var.get())
        self.role_combo.configure(values=self._role_choice_values(current_role))
        self.role_var.set(current_role)

        if current_role and current_role not in self.ROLE_CHOICES:
            self.role_summary_var.set(
                f"Role position is optional. Legacy role '{current_role}' is loaded; choose Pos 1-5 to replace it."
            )
        else:
            self.role_summary_var.set("Role position is optional. Pos 1 = carry, Pos 5 = hard support.")

    def add_item_row(self, item_name="", use_prior_items=True):
        row = BuildItemRow(
            self.items_container,
            self.item_names,
            self._refresh_current_build_view,
            self.move_item_row_up,
            self.move_item_row_down,
            self.remove_item_row,
            item_name=item_name,
            use_prior_items=use_prior_items,
        )
        row.pack(fill="x", pady=4)
        self.item_rows.append(row)
        self._refresh_current_build_view()

    def remove_item_row(self, row):
        if row not in self.item_rows:
            return
        self.item_rows.remove(row)
        row.destroy()
        if not self.item_rows:
            self.add_item_row()
            return
        self._refresh_current_build_view()

    def move_item_row_up(self, row):
        index = self.item_rows.index(row)
        if index == 0:
            return
        self.item_rows[index - 1], self.item_rows[index] = self.item_rows[index], self.item_rows[index - 1]
        self._repack_item_rows()

    def move_item_row_down(self, row):
        index = self.item_rows.index(row)
        if index >= len(self.item_rows) - 1:
            return
        self.item_rows[index + 1], self.item_rows[index] = self.item_rows[index], self.item_rows[index + 1]
        self._repack_item_rows()

    def clear_item_rows(self):
        for row in self.item_rows[:]:
            row.destroy()
        self.item_rows.clear()
        self.add_item_row()

    def _repack_item_rows(self):
        for row in self.item_rows:
            row.frame.pack_forget()
        for row in self.item_rows:
            row.pack(fill="x", pady=4)
        self._refresh_current_build_view()

    def _item_cost_value(self, item_name):
        item_data = self.items.get(item_name)
        if not item_data:
            return None
        return _parse_gold_value(item_data.get("cost"))

    def _item_cost_text(self, item_name):
        if not item_name:
            return ""
        if item_name not in self.items:
            return "Unknown"

        cost_value = self._item_cost_value(item_name)
        if cost_value is None:
            return "N/A"
        return _format_gold(cost_value)

    def _collect_current_items(self, require_valid=False):
        items = []
        invalid_items = []
        for row in self.item_rows:
            item_name = row.get_item_name()
            if not item_name:
                continue
            normalized_item = _normalize_choice(item_name, self.item_names)
            if normalized_item:
                items.append(
                    {
                        "name": normalized_item,
                        "use_prior_items": row.uses_prior_items(),
                    }
                )
            else:
                invalid_items.append(item_name)

        if require_valid and invalid_items:
            return items, invalid_items
        return items, invalid_items

    def _item_entry_name(self, item_entry):
        if isinstance(item_entry, dict):
            return str(item_entry.get("name") or "").strip()
        return str(item_entry or "").strip()

    def _item_entry_uses_prior_items(self, item_entry):
        if not isinstance(item_entry, dict):
            return True
        return self._coerce_use_prior_items(item_entry.get("use_prior_items", True))

    def _item_recipe_names(self, item_name):
        item_data = self.items.get(item_name)
        if not item_data:
            return []

        recipe_payload = item_data.get("recipe")
        if not isinstance(recipe_payload, list):
            return []

        recipe_names = []
        for recipe_item in recipe_payload:
            if isinstance(recipe_item, str) and recipe_item.strip():
                recipe_names.append(recipe_item.strip())
        return recipe_names

    def _item_recipe_cost_value(self, item_name):
        item_data = self.items.get(item_name)
        if not item_data:
            return 0
        recipe_cost = _parse_gold_value(item_data.get("recipeCost"))
        return recipe_cost or 0

    def _clean_inventory(self, inventory):
        return Counter({name: count for name, count in inventory.items() if count > 0})

    def _plan_rank(self, plan):
        if plan is None or plan.spent_gold is None:
            return (1, float("inf"), 0)
        return (0, plan.spent_gold, -plan.consumed_count)

    def _choose_better_plan(self, current_best, candidate):
        if candidate is None:
            return current_best
        if current_best is None:
            return candidate
        if self._plan_rank(candidate) < self._plan_rank(current_best):
            return candidate
        return current_best

    def _candidate_acquisition_plans(self, item_name, inventory, allow_owned_match, sequence_cache, path):
        item_data = self.items.get(item_name)
        if not item_data:
            return []

        candidates = []
        if allow_owned_match and inventory.get(item_name, 0) > 0:
            candidates.append(AcquisitionPlan(0, ((item_name, 1),)))

        direct_cost = self._item_cost_value(item_name)
        if direct_cost is not None:
            candidates.append(AcquisitionPlan(direct_cost))

        recipe_names = self._item_recipe_names(item_name)
        if recipe_names and item_name not in path:
            ingredient_plan = self._plan_recipe_sequence(
                tuple(recipe_names),
                inventory,
                sequence_cache,
                path + (item_name,),
            )
            if ingredient_plan is not None and ingredient_plan.spent_gold is not None:
                candidates.append(
                    AcquisitionPlan(
                        ingredient_plan.spent_gold + self._item_recipe_cost_value(item_name),
                        ingredient_plan.consumed_items,
                    )
                )

        deduped = {}
        for candidate in candidates:
            key = (candidate.spent_gold, candidate.consumed_items)
            deduped[key] = candidate
        return list(deduped.values())

    def _plan_recipe_sequence(self, recipe_names, inventory, sequence_cache, path):
        cache_key = (recipe_names, _counter_to_tuple(inventory))
        if cache_key in sequence_cache:
            return sequence_cache[cache_key]

        if not recipe_names:
            empty_plan = AcquisitionPlan(0)
            sequence_cache[cache_key] = empty_plan
            return empty_plan

        first_item = recipe_names[0]
        remaining_items = recipe_names[1:]
        best_plan = None

        for candidate in self._candidate_acquisition_plans(
            first_item,
            inventory,
            True,
            sequence_cache,
            path,
        ):
            remaining_inventory = Counter(inventory)
            remaining_inventory.subtract(dict(candidate.consumed_items))
            remaining_inventory = self._clean_inventory(remaining_inventory)

            remaining_plan = self._plan_recipe_sequence(
                remaining_items,
                remaining_inventory,
                sequence_cache,
                path,
            )
            if remaining_plan is None or remaining_plan.spent_gold is None:
                continue

            combined_consumed = Counter(dict(candidate.consumed_items))
            combined_consumed.update(dict(remaining_plan.consumed_items))
            combined_plan = AcquisitionPlan(
                candidate.spent_gold + remaining_plan.spent_gold,
                _counter_to_tuple(combined_consumed),
            )
            best_plan = self._choose_better_plan(best_plan, combined_plan)

        sequence_cache[cache_key] = best_plan
        return best_plan

    def _plan_item_purchase(self, item_name, inventory, use_prior_items):
        if item_name not in self.items:
            return None

        sequence_cache = {}
        source_inventory = Counter(inventory) if use_prior_items else Counter()
        best_plan = None
        for candidate in self._candidate_acquisition_plans(
            item_name,
            source_inventory,
            False,
            sequence_cache,
            (),
        ):
            best_plan = self._choose_better_plan(best_plan, candidate)
        return best_plan

    def _format_consumed_items(self, consumed_items):
        if not consumed_items:
            return ""

        parts = []
        for item_name, count in consumed_items:
            if count == 1:
                parts.append(item_name)
            else:
                parts.append(f"{item_name} x{count}")
        return ", ".join(parts)

    def _build_step_details(self, item_name, use_prior_items, plan):
        if item_name not in self.items:
            return "Item name does not match dataset.json."

        if plan is None or plan.spent_gold is None:
            return "This item cannot be priced from the current dataset."

        if not self._item_recipe_names(item_name):
            return "Bought as a standalone item."

        consumed_text = self._format_consumed_items(plan.consumed_items)
        if consumed_text:
            return f"Uses earlier buys: {consumed_text}"

        if use_prior_items and self._item_recipe_names(item_name):
            return "No earlier components were available, so this step buys it fresh."

        if use_prior_items:
            return "Bought as a standalone item."

        return "Forced fresh buy. Earlier components stay separate."

    def _simulate_item_entries(self, item_entries):
        simulation_rows = []
        inventory = Counter()
        running_total = 0

        for index, item_entry in enumerate(item_entries, start=1):
            item_name = self._item_entry_name(item_entry)
            use_prior_items = self._item_entry_uses_prior_items(item_entry)
            plan = None
            spend_text = self._item_cost_text(item_name)
            details = ""

            if item_name and item_name in self.items:
                plan = self._plan_item_purchase(item_name, inventory, use_prior_items)
                if plan is not None and plan.spent_gold is not None:
                    spend_text = _format_gold(plan.spent_gold)
                    running_total += plan.spent_gold
                    inventory.subtract(dict(plan.consumed_items))
                    inventory = self._clean_inventory(inventory)
                    inventory[item_name] += 1
                else:
                    spend_text = "N/A"
                details = self._build_step_details(item_name, use_prior_items, plan)
            elif item_name:
                details = "Item name does not match dataset.json."

            simulation_rows.append(
                {
                    "index": index,
                    "item_name": item_name,
                    "spend_text": spend_text,
                    "running_total": running_total,
                    "details": details,
                    "plan": plan,
                }
            )

        return simulation_rows

    def _refresh_current_build_view(self):
        if self.loading_build:
            return

        for item_id in self.summary_tree.get_children():
            self.summary_tree.delete(item_id)

        selected_items = []
        invalid_items = []
        item_entries = []
        for row in self.item_rows:
            item_entries.append(
                {
                    "name": row.get_item_name(),
                    "use_prior_items": row.uses_prior_items(),
                }
            )

        simulation_rows = self._simulate_item_entries(item_entries)
        row_lookup = {simulation_row["index"]: simulation_row for simulation_row in simulation_rows}

        for index, row in enumerate(self.item_rows, start=1):
            row.set_position(index)
            item_name = row.get_item_name()
            simulation_row = row_lookup.get(index)
            cost_text = simulation_row["spend_text"] if simulation_row else self._item_cost_text(item_name)
            detail_text = simulation_row["details"] if simulation_row else ""
            row.set_cost_text(cost_text)
            row.set_detail_text(detail_text)

            if not item_name:
                continue

            selected_items.append(item_name)
            if item_name not in self.items:
                invalid_items.append(item_name)

            running_total = simulation_row["running_total"] if simulation_row else 0
            self.summary_tree.insert(
                "",
                "end",
                values=(
                    index,
                    item_name,
                    cost_text,
                    _format_gold(running_total),
                    detail_text,
                ),
            )

        self.current_total_cost = simulation_rows[-1]["running_total"] if simulation_rows else 0

        hero_name = _normalize_choice(self.hero_var.get(), self.hero_names)
        role_name = self._normalize_role_value(self.role_var.get())
        hero_summary = hero_name if hero_name else "No hero selected"
        role_summary = role_name if role_name else "Any role"
        invalid_suffix = f" • {len(invalid_items)} invalid item(s)" if invalid_items else ""
        self.summary_var.set(
            f"{hero_summary} • {role_summary} • {len(selected_items)} item(s) • Total gold spent: {_format_gold(self.current_total_cost)}{invalid_suffix}"
        )

    def _build_total_cost(self, items):
        simulation_rows = self._simulate_item_entries(items)
        if not simulation_rows:
            return 0
        return simulation_rows[-1]["running_total"]

    def _build_display_name(self, build):
        if build["name"]:
            return build["name"]
        if build["hero"]:
            suffix = f" {build['role']}" if build["role"] else ""
            return f"{build['hero']}{suffix} Build"
        return "Unnamed Build"

    def _generate_default_build_name(self, hero_name, role_name):
        base_name = f"{hero_name}{f' {role_name}' if role_name else ''} Build".strip()
        if not base_name:
            base_name = "Build"

        existing_names = {
            self._build_display_name(build).lower()
            for build in self.saved_builds_data["builds"]
            if build.get("id") != self.current_build_id
        }
        candidate = base_name
        index = 2
        while candidate.lower() in existing_names:
            candidate = f"{base_name} {index}"
            index += 1
        return candidate

    def _save_builds(self):
        _write_json_file(self.saved_builds_path, self.saved_builds_data)

    def _refresh_saved_builds_tree(self, selected_build_id=None):
        for item_id in self.saved_builds_tree.get_children():
            self.saved_builds_tree.delete(item_id)

        builds = sorted(
            self.saved_builds_data["builds"],
            key=lambda build: (build.get("updated_at", ""), self._build_display_name(build).lower()),
            reverse=True,
        )

        for build in builds:
            build_id = build["id"]
            total_cost = self._build_total_cost(build["items"])
            self.saved_builds_tree.insert(
                "",
                "end",
                iid=build_id,
                values=(
                    self._build_display_name(build),
                    build["hero"],
                    build["role"] or "-",
                    len(build["items"]),
                    _format_gold(total_cost),
                    build["updated_at"] or build["created_at"] or "-",
                ),
            )

        if selected_build_id and self.saved_builds_tree.exists(selected_build_id):
            self.saved_builds_tree.selection_set(selected_build_id)
            self.saved_builds_tree.focus(selected_build_id)
            self.saved_builds_tree.see(selected_build_id)

    def _selected_build_id(self):
        selection = self.saved_builds_tree.selection()
        if not selection:
            return None
        return selection[0]

    def save_current_build(self):
        hero_name = _normalize_choice(self.hero_var.get(), self.hero_names)
        if not hero_name:
            messagebox.showerror("Missing Hero", "Select a hero before saving a build.")
            return

        role_name = self._normalize_role_value(self.role_var.get())
        items, invalid_items = self._collect_current_items(require_valid=True)
        if invalid_items:
            messagebox.showerror(
                "Invalid Item",
                f"These item names do not match dataset.json:\n{', '.join(invalid_items)}",
            )
            return

        build_name = self.build_name_var.get().strip()
        if not build_name:
            build_name = self._generate_default_build_name(hero_name, role_name)
            self.build_name_var.set(build_name)

        timestamp = _timestamp()
        build_id = self.current_build_id or uuid.uuid4().hex
        existing_index = next(
            (index for index, build in enumerate(self.saved_builds_data["builds"]) if build["id"] == build_id),
            None,
        )

        created_at = timestamp
        if existing_index is not None:
            created_at = self.saved_builds_data["builds"][existing_index].get("created_at") or timestamp

        build_record = {
            "id": build_id,
            "name": build_name,
            "hero": hero_name,
            "role": role_name,
            "items": items,
            "created_at": created_at,
            "updated_at": timestamp,
        }

        if existing_index is None:
            self.saved_builds_data["builds"].append(build_record)
            self.status_var.set(f"Saved new build '{build_name}' to {self.SAVE_FILENAME}.")
        else:
            self.saved_builds_data["builds"][existing_index] = build_record
            self.status_var.set(f"Updated build '{build_name}' in {self.SAVE_FILENAME}.")

        self.current_build_id = build_id
        self.editor_state_var.set(f"Editing saved build: {build_name}")
        self._save_builds()
        self._refresh_saved_builds_tree(selected_build_id=build_id)
        self._refresh_current_build_view()

    def load_selected_build(self):
        build_id = self._selected_build_id()
        if not build_id:
            messagebox.showinfo("No Selection", "Select a saved build to load.")
            return

        build = next((entry for entry in self.saved_builds_data["builds"] if entry["id"] == build_id), None)
        if not build:
            return

        self.loading_build = True
        self.current_build_id = build["id"]
        self.build_name_var.set(build["name"])
        self.hero_var.set(build["hero"])
        self.role_var.set(build["role"])
        self._refresh_role_choices()

        for row in self.item_rows[:]:
            row.destroy()
        self.item_rows.clear()

        if build["items"]:
            for item_entry in build["items"]:
                row = BuildItemRow(
                    self.items_container,
                    self.item_names,
                    self._refresh_current_build_view,
                    self.move_item_row_up,
                    self.move_item_row_down,
                    self.remove_item_row,
                    item_name=self._item_entry_name(item_entry),
                    use_prior_items=self._item_entry_uses_prior_items(item_entry),
                )
                row.pack(fill="x", pady=4)
                self.item_rows.append(row)
        else:
            row = BuildItemRow(
                self.items_container,
                self.item_names,
                self._refresh_current_build_view,
                self.move_item_row_up,
                self.move_item_row_down,
                self.remove_item_row,
            )
            row.pack(fill="x", pady=4)
            self.item_rows.append(row)

        self.loading_build = False
        self.editor_state_var.set(f"Editing saved build: {self._build_display_name(build)}")
        self.status_var.set(f"Loaded build '{self._build_display_name(build)}'.")
        self._refresh_current_build_view()
        self._refresh_saved_builds_tree(selected_build_id=build_id)

    def delete_selected_build(self):
        build_id = self._selected_build_id()
        if not build_id:
            messagebox.showinfo("No Selection", "Select a saved build to delete.")
            return

        build = next((entry for entry in self.saved_builds_data["builds"] if entry["id"] == build_id), None)
        if not build:
            return

        build_name = self._build_display_name(build)
        should_delete = messagebox.askyesno("Delete Build", f"Delete saved build '{build_name}'?")
        if not should_delete:
            return

        self.saved_builds_data["builds"] = [
            entry for entry in self.saved_builds_data["builds"] if entry["id"] != build_id
        ]
        self._save_builds()
        self._refresh_saved_builds_tree()

        if self.current_build_id == build_id:
            self.clear_editor(update_status=False)

        self.status_var.set(f"Deleted build '{build_name}'.")

    def clear_editor(self, update_status=True):
        self.current_build_id = None
        self.loading_build = True
        self.build_name_var.set("")
        self.hero_var.set("")
        self.role_var.set("")
        self.loading_build = False
        self._refresh_role_choices()

        for row in self.item_rows[:]:
            row.destroy()
        self.item_rows.clear()
        self.add_item_row()

        for item_id in self.saved_builds_tree.selection():
            self.saved_builds_tree.selection_remove(item_id)

        self.editor_state_var.set("Creating a new build.")
        if update_status:
            self.status_var.set(f"Cleared the editor. Builds save to {self.SAVE_FILENAME}.")
        self._refresh_current_build_view()
