"""ItemWorkbenchSection class - item creation and persistence"""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from modifiers import Modifier


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
        ttk.Label(fields_row, text="Gold:", font=('Arial', 8)).pack(side="left", padx=(10, 4))
        self.field_vars["gold_amount"] = tk.StringVar(value="0")
        ttk.Entry(fields_row, textvariable=self.field_vars["gold_amount"], width=10).pack(side="left")

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
        values = {}
        for key, value in mod.__dict__.items():
            if key.endswith("_var") and hasattr(value, "get"):
                values[key] = value.get()
        return {"type": getattr(mod, "TYPE_NAME", ""), "values": values}

    def _load_modifier(self, modifier_data):
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
        return {
            "item_id": self.item_id,
            "fields": {key: var.get() for key, var in self.field_vars.items()},
            "notes": self.notes_var.get(),
            "modifiers": [self._serialize_modifier(mod) for mod in self.modifiers],
        }

    def load_from_dict(self, data):
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
        self.frame.pack(**kwargs)

    def destroy(self):
        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()
        self.frame.destroy()


class ItemWorkbenchSection:
    """Standalone item workbench section."""

    ITEM_LIBRARY_FILENAME = "item_library.json"

    def __init__(self, parent, get_variables):
        self.parent = parent
        self.get_variables = get_variables
        self.visible = False
        self.item_rows = []
        self.next_item_id = 1
        self._create_widgets()

    def _create_widgets(self):
        self.section_frame = ttk.Frame(self.parent)
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        header = ttk.Frame(self.section_frame)
        header.pack(fill="x", pady=(5, 5))
        ttk.Label(header, text="ITEM WORKBENCH", font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(header, text="Load Items",
                   command=self.load_items).pack(side="right", padx=5)
        ttk.Button(header, text="+ Add Item",
                   command=self.add_item).pack(side="right", padx=5)

        self.items_container = ttk.Frame(self.section_frame)
        self.items_container.pack(fill="x", pady=5)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def pack_content(self):
        if not self.visible:
            self.section_frame.pack(fill="x", pady=5)
            self.visible = True
            if not self.item_rows:
                self.add_item()

    def add_item(self, item_data=None):
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
        if item_row in self.item_rows:
            self.item_rows.remove(item_row)
            item_row.destroy()

    def clear(self):
        for item_row in self.item_rows[:]:
            item_row.destroy()
        self.item_rows.clear()
        self.next_item_id = 1

    def _get_item_library_path(self):
        return os.path.join(os.path.dirname(__file__), self.ITEM_LIBRARY_FILENAME)

    def _read_library_items(self):
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

    def _write_library_items(self, items):
        file_path = self._get_item_library_path()
        payload = {"version": 1, "items": items}
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _normalize_name(self, name):
        return str(name).strip().lower()

    def _item_name_from_data(self, item_data, fallback_index=None):
        item_name = item_data.get("fields", {}).get("name", "").strip()
        if item_name:
            return item_name
        if fallback_index is not None:
            return f"Item {fallback_index + 1}"
        return "Item"

    def _generate_item_version_name(self, base_name, existing_items):
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

    def save_item(self, item_row):
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

        existing_names = [self._item_name_from_data(item, idx) for idx, item in enumerate(existing_items)]
        selected_update_index = next(
            (idx for idx, name in enumerate(existing_names)
             if self._normalize_name(name) == self._normalize_name(current_name)),
            0
        ) if existing_names else -1
        update_name_var = tk.StringVar(
            value=existing_names[selected_update_index] if selected_update_index >= 0 else ""
        )
        update_combo = ttk.Combobox(content, textvariable=update_name_var, values=existing_names, state="readonly", width=32)
        update_combo.pack(fill="x", pady=(0, 10))
        if selected_update_index >= 0:
            update_combo.current(selected_update_index)
        else:
            update_combo.configure(state="disabled")

        buttons = ttk.Frame(content)
        buttons.pack(fill="x")

        def _save_new():
            normalized_target = self._normalize_name(current_name)
            normalized_existing = {self._normalize_name(name) for name in existing_names}
            if normalized_target in normalized_existing:
                messagebox.showerror("Duplicate Name", "A saved item with this name already exists. Use Update Existing or Save New Version.")
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
            selected_index = next((idx for idx, name in enumerate(existing_names) if name == selected_name), None)
            if selected_index is None:
                return

            normalized_target = self._normalize_name(current_name)
            for idx, name in enumerate(existing_names):
                if idx != selected_index and self._normalize_name(name) == normalized_target:
                    messagebox.showerror("Duplicate Name", "Another saved item already uses this name. Rename current item first.")
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

        ttk.Button(buttons, text="Save New", command=_save_new).pack(side="left")
        ttk.Button(buttons, text="Update Existing", command=_update_existing).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save New Version", command=_save_new_version).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=menu.destroy).pack(side="right")

    def load_items(self):
        items_data = self._read_library_items()
        if items_data is None:
            return
        if not items_data:
            messagebox.showinfo("No Item Library", f"No saved items in:\n{self._get_item_library_path()}")
            return
        self._open_item_load_menu(items_data)

    def _open_item_load_menu(self, items_data):
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
        combo = ttk.Combobox(content, textvariable=selected_name, values=display_names, state="readonly", width=32)
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
            self.clear()
            self.add_item(item_data=valid_items[selected_index])
            menu.destroy()

        def _load_selected_append():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.add_item(item_data=valid_items[selected_index])
            menu.destroy()

        def _load_all_replace():
            self.clear()
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

        ttk.Button(buttons, text="Load Selected", command=_load_selected_replace).pack(side="left")
        ttk.Button(buttons, text="Append Selected", command=_load_selected_append).pack(side="left", padx=5)
        ttk.Button(buttons, text="Load All", command=_load_all_replace).pack(side="left")
        ttk.Button(buttons, text="Delete Selected", command=_delete_selected_saved).pack(side="left", padx=(5, 0))
        ttk.Button(buttons, text="Cancel", command=menu.destroy).pack(side="right")
