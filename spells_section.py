"""SpellsSection class - orchestrates entire Spells section"""

import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS
from spell_row import SpellRow
from modifiers import Modifier
from utils import armor_to_reduction
from spell_calculations import (
    calculate_spell_dps,
    calculate_mana_efficiency
)


class SpellsSection:
    """Orchestrates the entire Spells section"""

    def __init__(self, parent, get_variables, get_num_columns, on_columns_change_subscribe):
        """
        Initialize the Spells section.

        Args:
            parent: Parent widget to add section to
            get_variables: Callback to get current variables dict
            get_num_columns: Callback to get current number of columns
            on_columns_change_subscribe: Callback to subscribe to column changes
        """
        self.parent = parent
        self.get_variables = get_variables
        self.get_num_columns = get_num_columns

        self.visible = False
        self.spell_rows = []
        self.modifiers = []
        self.spell_row_counter = 0

        # Callback to get available targets
        self.get_targets = None

        # Display toggle states
        self.show_burst = tk.BooleanVar(value=True)
        self.show_dps = tk.BooleanVar(value=True)
        self.show_mana_eff = tk.BooleanVar(value=True)

        self._create_widgets()

        # Subscribe to column changes
        on_columns_change_subscribe(self._on_columns_changed)

    def _create_widgets(self):
        """Create all widgets for the Spells section"""
        # Main section frame
        self.section_frame = ttk.Frame(self.parent)

        # Separator at top
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        # === SPELL ROWS ===
        spell_header = ttk.Frame(self.section_frame)
        spell_header.pack(fill="x", pady=(5, 5))
        ttk.Label(spell_header, text="SPELL ROWS",
                  font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(spell_header, text="+ Add",
                   command=self.add_spell_row).pack(side="right", padx=5)

        self.spell_rows_container = ttk.Frame(self.section_frame)
        self.spell_rows_container.pack(fill="x", pady=5)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        # === MODIFIERS ===
        modifier_header = ttk.Frame(self.section_frame)
        modifier_header.pack(fill="x", pady=(5, 5))
        ttk.Label(modifier_header, text="MODIFIERS",
                  font=('Arial', 10, 'bold')).pack(side="left")

        # Modifier type dropdown and add button
        self.modifier_type_var = tk.StringVar(value="")
        self.modifier_combo = ttk.Combobox(modifier_header, textvariable=self.modifier_type_var,
                                           state="readonly", width=18)
        self.modifier_combo['values'] = Modifier.get_available_types()
        if self.modifier_combo['values']:
            self.modifier_type_var.set(self.modifier_combo['values'][0])
        self.modifier_combo.pack(side="right", padx=2)
        ttk.Button(modifier_header, text="+ Add",
                   command=self.add_modifier).pack(side="right", padx=5)

        self.modifiers_container = ttk.Frame(self.section_frame)
        self.modifiers_container.pack(fill="x", pady=5)

        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        # === CALCULATIONS ===
        calc_header = ttk.Frame(self.section_frame)
        calc_header.pack(fill="x", pady=(5, 5))
        ttk.Label(calc_header, text="CALCULATIONS",
                  font=('Arial', 10, 'bold')).pack(side="left")

        # Toggle options
        toggle_frame = ttk.Frame(self.section_frame)
        toggle_frame.pack(fill="x", pady=5)

        self.show_burst.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="Burst Damage",
                        variable=self.show_burst).pack(side="left", padx=5)

        self.show_dps.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="DPS (over CD)",
                        variable=self.show_dps).pack(side="left", padx=5)

        self.show_mana_eff.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="Mana Efficiency",
                        variable=self.show_mana_eff).pack(side="left", padx=5)

        # Burst damage display
        self.burst_frame = ttk.Frame(self.section_frame)
        self.burst_container = ttk.Frame(self.burst_frame)
        self.burst_container.pack(fill="x")

        # DPS display
        self.dps_frame = ttk.Frame(self.section_frame)
        self.dps_container = ttk.Frame(self.dps_frame)
        self.dps_container.pack(fill="x")

        # Mana efficiency display
        self.mana_frame = ttk.Frame(self.section_frame)
        self.mana_container = ttk.Frame(self.mana_frame)
        self.mana_container.pack(fill="x")

        # Bottom separator
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def _on_columns_changed(self, num_columns):
        """Handle column count changes"""
        for row in self.spell_rows:
            row.update_columns(num_columns)
        self.calculate()

    def pack_content(self):
        """Pack the section content (called by parent's toggle)"""
        if not self.visible:
            self.section_frame.pack(fill="x", pady=5)
            self.visible = True
            # Add initial rows if empty
            if not self.spell_rows:
                self.add_spell_row()

    def get_modifiers_list(self):
        """
        Get list of modifier objects.

        Returns:
            List of Modifier objects
        """
        return self.modifiers

    def add_spell_row(self):
        """Add a new spell row"""
        self.spell_row_counter += 1
        row = SpellRow(
            self.spell_rows_container,
            self.spell_row_counter,
            self.calculate,
            self.delete_spell_row,
            num_columns=self.get_num_columns(),
            get_variables=self.get_variables,
            get_modifiers=self.get_modifiers_list,
            get_targets=self.get_targets
        )
        row.update_target_options()
        row.update_modifier_options()
        row.pack(fill="x", pady=2)
        self.spell_rows.append(row)
        self.calculate()

    def delete_spell_row(self, row):
        """Delete a spell row"""
        if len(self.spell_rows) > 1:
            self.spell_rows.remove(row)
            row.destroy()
            self.calculate()

    def add_modifier(self):
        """Add a new modifier from dropdown selection"""
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
            self.update_modifier_options()
            self.calculate()

    def delete_modifier(self, mod):
        """Delete a modifier"""
        self.modifiers.remove(mod)
        mod.destroy()
        self.update_modifier_options()
        self.calculate()

    def _on_modifier_changed(self):
        """Called when a modifier's values change"""
        self.update_modifier_options()
        self.calculate()

    def update_modifier_options(self):
        """Update modifier dropdown options for all spell rows"""
        for row in self.spell_rows:
            row.update_modifier_options()

    def set_get_targets(self, callback):
        """Set callback to get available targets"""
        self.get_targets = callback

    def update_target_options(self):
        """Update target dropdown options for all spell rows"""
        for row in self.spell_rows:
            row.update_target_options()

    def calculate(self):
        """Calculate and update all displays"""
        if not self.visible:
            return

        # Update modifier displays
        for mod in self.modifiers:
            mod.update_display()

        # Build list of spell row results with their targets
        spell_results = []

        for row in self.spell_rows:
            row.update_display()

            if not row.is_enabled():
                continue

            spell_label = row.get_label()
            targets = row.get_selected_targets()
            for target in targets:
                if target.is_enabled():
                    target_label = target.label_var.get()
                    spell_results.append((spell_label, target_label, row, target))

        # Update displays
        self._update_burst_display(spell_results)
        self._update_dps_display(spell_results)
        self._update_mana_display(spell_results)

    def _update_burst_display(self, spell_results):
        """Update the burst damage display"""
        # Clear existing
        for child in self.burst_container.winfo_children():
            child.destroy()

        if self.show_burst.get() and spell_results:
            self.burst_frame.pack(fill="x", pady=2)

            # Header
            header_frame = ttk.Frame(self.burst_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Burst Damage:",
                      font=('Arial', 9, 'bold')).pack(side="left", padx=5)

            # One row per spell+target combination
            for i, (spell_label, target_label, row, target) in enumerate(spell_results):
                row_frame = ttk.Frame(self.burst_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]

                # Get damage values
                raw_damage = row.get_total_damage()
                reduced_damage = row.get_damage_against_target(target)
                damage_type = row.get_damage_type()

                label_text = f"  {spell_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=25,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)

                # Show raw -> reduced
                if damage_type == "Pure":
                    result_text = f"{raw_damage:.0f} (Pure)"
                else:
                    reduction_pct = ((raw_damage - reduced_damage) / raw_damage * 100) if raw_damage > 0 else 0
                    result_text = f"{raw_damage:.0f} → {reduced_damage:.0f} ({damage_type}, -{reduction_pct:.0f}%)"

                ttk.Label(row_frame, text=result_text, width=35,
                          foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.burst_frame.pack_forget()

    def _update_dps_display(self, spell_results):
        """Update the DPS display"""
        # Clear existing
        for child in self.dps_container.winfo_children():
            child.destroy()

        if self.show_dps.get() and spell_results:
            self.dps_frame.pack(fill="x", pady=2)

            # Header
            header_frame = ttk.Frame(self.dps_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="DPS (over CD):",
                      font=('Arial', 9, 'bold')).pack(side="left", padx=5)

            # One row per spell+target combination
            for i, (spell_label, target_label, row, target) in enumerate(spell_results):
                row_frame = ttk.Frame(self.dps_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]

                dps = row.get_dps_against_target(target)
                cooldown = row.get_cooldown()
                cast_time = row.get_cast_time()

                label_text = f"  {spell_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=25,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)

                cycle_time = max(cast_time, cooldown)
                if cycle_time > 0:
                    result_text = f"{dps:.1f}/s (cycle: {cycle_time:.1f}s)"
                else:
                    result_text = "N/A (no CD)"

                ttk.Label(row_frame, text=result_text, width=35,
                          foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.dps_frame.pack_forget()

    def _update_mana_display(self, spell_results):
        """Update the mana efficiency display"""
        # Clear existing
        for child in self.mana_container.winfo_children():
            child.destroy()

        if self.show_mana_eff.get() and spell_results:
            self.mana_frame.pack(fill="x", pady=2)

            # Header
            header_frame = ttk.Frame(self.mana_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Mana Efficiency:",
                      font=('Arial', 9, 'bold')).pack(side="left", padx=5)

            # One row per spell+target combination
            for i, (spell_label, target_label, row, target) in enumerate(spell_results):
                row_frame = ttk.Frame(self.mana_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]

                mana_eff = row.get_mana_efficiency_against_target(target)
                mana_cost = row.get_mana_cost()

                label_text = f"  {spell_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=25,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)

                if mana_cost > 0:
                    result_text = f"{mana_eff:.2f} dmg/mana ({mana_cost:.0f} mana)"
                else:
                    result_text = "Free cast (0 mana)"

                ttk.Label(row_frame, text=result_text, width=35,
                          foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.mana_frame.pack_forget()

    def hide_content(self):
        """Hide the section content"""
        if self.visible:
            self.section_frame.pack_forget()
            self.visible = False

    def clear(self):
        """Clear all spell mode data"""
        for row in self.spell_rows[:]:
            row.destroy()
        self.spell_rows.clear()
        self.spell_row_counter = 0

        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()

        self.show_burst.set(True)
        self.show_dps.set(True)
        self.show_mana_eff.set(True)
