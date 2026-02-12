"""SpellWorkbenchSection class - spell creation and persistence"""

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from hero_lab_section import HeroSpellRow


class SpellWorkbenchRow:
    """Single spell row for creating and persisting reusable spells."""

    def __init__(self, parent, spell_id, on_delete, on_save):
        self.parent = parent
        self.spell_id = spell_id
        self.on_delete = on_delete
        self.on_save = on_save
        self.notes_var = tk.StringVar(value="")

        self.frame = ttk.Frame(parent, relief='solid', borderwidth=1, padding="8")
        self._create_widgets()

    def _create_widgets(self):
        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 6))
        ttk.Button(header, text="Save", width=8,
                   command=lambda: self.on_save(self)).pack(side="right", padx=(0, 4))
        ttk.Button(header, text="Delete", width=8,
                   command=lambda: self.on_delete(self)).pack(side="right")

        notes_row = ttk.Frame(self.frame)
        notes_row.pack(fill="x", pady=(0, 4))
        ttk.Label(notes_row, text="Notes:", font=('Arial', 8)).pack(side="left", padx=(0, 4))
        ttk.Entry(notes_row, textvariable=self.notes_var, width=90).pack(side="left", fill="x", expand=True)

        ttk.Separator(self.frame, orient='horizontal').pack(fill="x", pady=5)
        self.spell_editor = HeroSpellRow(self.frame, on_delete=None, show_delete_button=False)
        self.spell_editor.pack(fill="x", pady=2)

    def to_dict(self):
        spell_data = self.spell_editor.to_dict()
        spell_data["spell_id"] = self.spell_id
        spell_data["notes"] = self.notes_var.get()
        return spell_data

    def load_from_dict(self, data):
        self.spell_editor.load_from_dict(data)
        self.notes_var.set(str(data.get("notes", "")))

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def destroy(self):
        self.spell_editor.destroy()
        self.frame.destroy()


class SpellWorkbenchSection:
    """Standalone spell workbench section."""

    SPELL_LIBRARY_FILENAME = "spell_library.json"

    def __init__(self, parent):
        self.parent = parent
        self.visible = False
        self.spell_rows = []
        self.next_spell_id = 1
        self._create_widgets()

    def _create_widgets(self):
        self.section_frame = ttk.Frame(self.parent)
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        header = ttk.Frame(self.section_frame)
        header.pack(fill="x", pady=(5, 5))
        ttk.Label(header, text="SPELL WORKBENCH", font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(header, text="Load Spells",
                   command=self.load_spells).pack(side="right", padx=5)
        ttk.Button(header, text="+ Add Spell",
                   command=self.add_spell).pack(side="right", padx=5)

        self.spells_container = ttk.Frame(self.section_frame)
        self.spells_container.pack(fill="x", pady=5)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def pack_content(self):
        if not self.visible:
            self.section_frame.pack(fill="x", pady=5)
            self.visible = True
            if not self.spell_rows:
                self.add_spell()

    def add_spell(self, spell_data=None):
        if spell_data and isinstance(spell_data.get("spell_id"), int):
            spell_id = spell_data["spell_id"]
            self.next_spell_id = max(self.next_spell_id, spell_id + 1)
        else:
            spell_id = self.next_spell_id
            self.next_spell_id += 1

        spell_row = SpellWorkbenchRow(
            self.spells_container,
            spell_id,
            self.delete_spell,
            self.save_spell,
        )
        if spell_data:
            spell_row.load_from_dict(spell_data)
        spell_row.pack(fill="x", pady=4)
        self.spell_rows.append(spell_row)

    def delete_spell(self, spell_row):
        if spell_row in self.spell_rows:
            self.spell_rows.remove(spell_row)
            spell_row.destroy()

    def clear(self):
        for spell_row in self.spell_rows[:]:
            spell_row.destroy()
        self.spell_rows.clear()
        self.next_spell_id = 1

    def _get_spell_library_path(self):
        return os.path.join(os.path.dirname(__file__), self.SPELL_LIBRARY_FILENAME)

    def _read_library_spells(self):
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

    def _write_library_spells(self, spells):
        file_path = self._get_spell_library_path()
        payload = {"version": 1, "spells": spells}
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _normalize_name(self, name):
        return str(name).strip().lower()

    def _spell_name_from_data(self, spell_data, fallback_index=None):
        spell_name = str(spell_data.get("name", "")).strip()
        if spell_name:
            return spell_name
        if fallback_index is not None:
            return f"Spell {fallback_index + 1}"
        return "Spell"

    def _generate_spell_version_name(self, base_name, existing_spells):
        normalized_existing = {
            self._normalize_name(self._spell_name_from_data(spell, idx))
            for idx, spell in enumerate(existing_spells)
        }
        root = base_name.strip() if base_name.strip() else "Spell"
        version = 2
        while True:
            candidate = f"{root} v{version}"
            if self._normalize_name(candidate) not in normalized_existing:
                return candidate
            version += 1

    def save_spell(self, spell_row):
        spell_data = spell_row.to_dict()
        current_name = spell_data.get("name", "").strip()
        if not current_name:
            messagebox.showerror("Save Failed", "Spell must have a non-empty Name.")
            return

        existing_spells = self._read_library_spells()
        if existing_spells is None:
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Save Spell")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)
        ttk.Label(content, text=f"Spell: {current_name}",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 8))

        existing_names = [self._spell_name_from_data(spell, idx) for idx, spell in enumerate(existing_spells)]
        update_name_var = tk.StringVar(value=existing_names[0] if existing_names else "")
        update_combo = ttk.Combobox(content, textvariable=update_name_var, values=existing_names, state="readonly", width=32)
        update_combo.pack(fill="x", pady=(0, 10))
        if not existing_names:
            update_combo.configure(state="disabled")

        buttons = ttk.Frame(content)
        buttons.pack(fill="x")

        def _save_new():
            normalized_target = self._normalize_name(current_name)
            normalized_existing = {self._normalize_name(name) for name in existing_names}
            if normalized_target in normalized_existing:
                messagebox.showerror("Duplicate Name", "A saved spell with this name already exists. Use Update Existing or Save New Version.")
                return
            existing_spells.append(spell_data)
            try:
                self._write_library_spells(existing_spells)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save spell:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Spell Saved", f"Saved new spell '{current_name}'.")

        def _update_existing():
            if not existing_names:
                messagebox.showerror("Update Failed", "No saved spells to update.")
                return
            selected_name = update_combo.get().strip()
            selected_index = next((idx for idx, name in enumerate(existing_names) if name == selected_name), None)
            if selected_index is None:
                return

            normalized_target = self._normalize_name(current_name)
            for idx, name in enumerate(existing_names):
                if idx != selected_index and self._normalize_name(name) == normalized_target:
                    messagebox.showerror("Duplicate Name", "Another saved spell already uses this name. Rename current spell first.")
                    return

            existing_spells[selected_index] = spell_data
            try:
                self._write_library_spells(existing_spells)
            except OSError as exc:
                messagebox.showerror("Update Failed", f"Could not update spell:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Spell Updated", f"Updated saved spell '{selected_name}'.")

        def _save_new_version():
            version_name = self._generate_spell_version_name(current_name, existing_spells)
            version_data = spell_row.to_dict()
            version_data["name"] = version_name
            existing_spells.append(version_data)
            try:
                self._write_library_spells(existing_spells)
            except OSError as exc:
                messagebox.showerror("Save Failed", f"Could not save spell version:\n{exc}")
                return
            menu.destroy()
            messagebox.showinfo("Spell Version Saved", f"Saved as '{version_name}'.")

        ttk.Button(buttons, text="Save New", command=_save_new).pack(side="left")
        ttk.Button(buttons, text="Update Existing", command=_update_existing).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save New Version", command=_save_new_version).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=menu.destroy).pack(side="right")

    def load_spells(self):
        spells_data = self._read_library_spells()
        if spells_data is None:
            return
        if not spells_data:
            messagebox.showinfo("No Spell Library", f"No saved spells in:\n{self._get_spell_library_path()}")
            return
        self._open_spell_load_menu(spells_data)

    def _open_spell_load_menu(self, spells_data):
        valid_spells = [spell for spell in spells_data if isinstance(spell, dict)]
        if not valid_spells:
            messagebox.showinfo("No Spells", "Spell library is empty.")
            return

        menu = tk.Toplevel(self.parent)
        menu.title("Load Spells")
        menu.transient(self.parent.winfo_toplevel())
        menu.grab_set()
        menu.resizable(False, False)

        content = ttk.Frame(menu, padding="12")
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Select spell from library:",
                  font=('Arial', 9, 'bold')).pack(anchor="w", pady=(0, 6))

        def _build_display_names():
            names = []
            for idx, spell in enumerate(valid_spells):
                spell_name = str(spell.get("name", "")).strip()
                if not spell_name:
                    spell_name = f"Spell {idx + 1}"
                names.append(spell_name)
            return names

        display_names = _build_display_names()
        selected_name = tk.StringVar(value=display_names[0])
        combo = ttk.Combobox(content, textvariable=selected_name, values=display_names, state="readonly", width=32)
        combo.pack(fill="x", pady=(0, 10))

        buttons = ttk.Frame(content)
        buttons.pack(fill="x")

        def _save_library():
            self._write_library_spells(valid_spells)

        def _refresh_combo():
            names = _build_display_names()
            combo["values"] = names
            if names:
                combo.current(0)
            else:
                menu.destroy()
                messagebox.showinfo("Library Updated", "All saved spells were deleted.")

        def _load_selected_replace():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.clear()
            self.add_spell(spell_data=valid_spells[selected_index])
            menu.destroy()

        def _load_selected_append():
            selected_index = combo.current()
            if selected_index < 0:
                return
            self.add_spell(spell_data=valid_spells[selected_index])
            menu.destroy()

        def _load_all_replace():
            self.clear()
            for spell in valid_spells:
                self.add_spell(spell_data=spell)
            menu.destroy()

        def _delete_selected_saved():
            selected_index = combo.current()
            if selected_index < 0:
                return
            selected_name_local = combo.get() or f"Spell {selected_index + 1}"
            should_delete = messagebox.askyesno(
                "Delete Saved Spell",
                f"Delete saved spell '{selected_name_local}' from library?"
            )
            if not should_delete:
                return
            valid_spells.pop(selected_index)
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
