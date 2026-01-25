"""AttackModeSection class - orchestrates entire Attack Mode section"""

import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS, DEFAULT_ATTACK_SPEED, DEFAULT_BAT
from attack_row import AttackRow
from modifiers import Modifier
from attack_calculations import (
    calculate_damage_for_n_hits,
    calculate_time_for_n_hits,
    calculate_dps,
    calculate_damage_in_time
)


class AttackModeSection:
    """Orchestrates the entire Attack Mode section"""

    def __init__(self, parent, get_variables, get_num_columns, on_columns_change_subscribe):
        """
        Initialize the Attack Mode section.

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
        self.attack_rows = []
        self.modifiers = []  # List of all modifiers (formerly complex_modifiers)
        self.attack_row_counter = 0

        # Callback to notify when attack results change
        self.on_attack_results_changed = None

        # Callback to get available targets
        self.get_targets = None

        # Display toggle states (all on by default)
        self.show_n_hits_range = tk.BooleanVar(value=True)
        self.show_time_range = tk.BooleanVar(value=True)
        self.show_dps_range = tk.BooleanVar(value=True)

        self._create_widgets()

        # Subscribe to column changes
        on_columns_change_subscribe(self._on_columns_changed)

    def _create_widgets(self):
        """Create all widgets for the Attack Mode section"""
        # Main section frame
        self.section_frame = ttk.Frame(self.parent)

        # Separator at top
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        # === ATTACK ROWS ===
        attack_header = ttk.Frame(self.section_frame)
        attack_header.pack(fill="x", pady=(5, 5))
        ttk.Label(attack_header, text="ATTACK ROWS",
                  font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(attack_header, text="+ Add",
                   command=self.add_attack_row).pack(side="right", padx=5)

        self.attack_rows_container = ttk.Frame(self.section_frame)
        self.attack_rows_container.pack(fill="x", pady=5)

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

        self.show_n_hits_range.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="Show N hits range (1-10)",
                        variable=self.show_n_hits_range).pack(side="left", padx=5)

        self.show_time_range.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="Show time range (1-10s)",
                        variable=self.show_time_range).pack(side="left", padx=5)

        self.show_dps_range.trace('w', lambda *args: self.calculate())
        ttk.Checkbutton(toggle_frame, text="Show DPS range (1-10s)",
                        variable=self.show_dps_range).pack(side="left", padx=5)

        # N hits range display
        self.n_hits_frame = ttk.Frame(self.section_frame)
        self.n_hits_container = ttk.Frame(self.n_hits_frame)
        self.n_hits_container.pack(fill="x")

        # Time range display
        self.time_frame = ttk.Frame(self.section_frame)
        self.time_container = ttk.Frame(self.time_frame)
        self.time_container.pack(fill="x")

        # DPS range display
        self.dps_frame = ttk.Frame(self.section_frame)
        self.dps_container = ttk.Frame(self.dps_frame)
        self.dps_container.pack(fill="x")

        # Bottom separator
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def _on_columns_changed(self, num_columns):
        """Handle column count changes"""
        for row in self.attack_rows:
            row.update_columns(num_columns)
        self.calculate()

    def pack_content(self):
        """Pack the section content (called by parent's toggle)"""
        if not self.visible:
            self.section_frame.pack(fill="x", pady=5)
            self.visible = True
            # Add initial rows if empty
            if not self.attack_rows:
                self.add_attack_row()

    def get_modifiers_list(self):
        """
        Get list of modifier objects.

        Returns:
            List of Modifier objects
        """
        return self.modifiers

    def add_attack_row(self):
        """Add a new attack row"""
        self.attack_row_counter += 1
        row = AttackRow(
            self.attack_rows_container,
            self.attack_row_counter,
            self.calculate,
            self.delete_attack_row,
            num_columns=self.get_num_columns(),
            get_variables=self.get_variables,
            get_modifiers=self.get_modifiers_list,
            get_targets=self.get_targets
        )
        row.update_target_options()
        row.update_modifier_options()
        row.pack(fill="x", pady=2)
        self.attack_rows.append(row)
        self.calculate()

    def delete_attack_row(self, row):
        """Delete an attack row"""
        if len(self.attack_rows) > 1:
            self.attack_rows.remove(row)
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
        """Update modifier dropdown options for all attack rows"""
        for row in self.attack_rows:
            row.update_modifier_options()

    def set_on_attack_results_changed(self, callback):
        """Set callback to be called when attack results change"""
        self.on_attack_results_changed = callback

    def set_get_targets(self, callback):
        """Set callback to get available targets"""
        self.get_targets = callback

    def update_target_options(self):
        """Update target dropdown options for all attack rows"""
        for row in self.attack_rows:
            row.update_target_options()

    def calculate(self):
        """Calculate and update all displays"""
        if not self.visible:
            return

        # Update modifier displays
        for mod in self.modifiers:
            mod.update_display()

        # Build list of attack row results with their targets
        # Each entry: (attack_label, target_label, row, target, attack_rate)
        # We pass the row object so complex modifiers can calculate per-hit damage
        attack_results = []
        total_dph = 0
        total_damage = 0

        for row in self.attack_rows:
            row.update_display()
            dph, total, attack_rate = row.get_results()
            total_dph += dph
            total_damage += total

            # Get all selected targets for this row
            attack_label = row.get_label()
            targets = row.get_selected_targets()
            for target in targets:
                target_label = target.label_var.get()
                attack_results.append((attack_label, target_label, row, target, attack_rate))

        # Calculate average attack rate
        avg_attack_rate = 1.0
        if attack_results:
            rates = [r[4] for r in attack_results if r[4] > 0]
            if rates:
                avg_attack_rate = sum(rates) / len(rates)

        # Update displays with per-target results
        self._update_n_hits_display(attack_results)
        self._update_time_display(attack_results)
        self._update_dps_display(attack_results)

        # Notify target section of updated attack results (raw damage)
        if self.on_attack_results_changed:
            self.on_attack_results_changed((total_dph, total_damage, avg_attack_rate))

    def _update_n_hits_display(self, attack_results):
        """Update the N hits range display (horizontal layout)"""
        # Clear existing
        for child in self.n_hits_container.winfo_children():
            child.destroy()

        if self.show_n_hits_range.get() and attack_results:
            self.n_hits_frame.pack(fill="x", pady=2)

            # Header row with hit counts 1-10
            header_frame = ttk.Frame(self.n_hits_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Hits:", width=20,
                      font=('Arial', 8, 'bold')).pack(side="left", padx=5)
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}", width=7,
                          font=('Arial', 8)).pack(side="left")

            # One row per attack+target combination showing damage for 1-10 hits
            for i, (attack_label, target_label, row, target, attack_rate) in enumerate(attack_results):
                row_frame = ttk.Frame(self.n_hits_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                label_text = f"{attack_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=20,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                phys_reduction = target.get_physical_reduction()
                magic_reduction = target.get_magic_resistance()
                for n in range(1, 11):
                    # Physical damage reduced by armor
                    phys_damage = row.get_total_damage_for_hits(n)
                    phys_reduced = phys_damage * (1 - phys_reduction)
                    # Magic damage reduced by magic resistance
                    magic_damage = row.get_total_magic_damage_for_hits(n)
                    magic_reduced = magic_damage * (1 - magic_reduction)
                    # Total damage
                    total = phys_reduced + magic_reduced
                    ttk.Label(row_frame, text=f"{total:.0f}", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.n_hits_frame.pack_forget()

    def _update_time_display(self, attack_results):
        """Update the time range display (horizontal layout)"""
        # Clear existing
        for child in self.time_container.winfo_children():
            child.destroy()

        if self.show_time_range.get() and attack_results:
            self.time_frame.pack(fill="x", pady=2)

            # Header row with hit counts 1-10
            header_frame = ttk.Frame(self.time_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Time:", width=20,
                      font=('Arial', 8, 'bold')).pack(side="left", padx=5)
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}", width=7,
                          font=('Arial', 8)).pack(side="left")

            # One row per attack+target combination showing time for 1-10 hits
            for i, (attack_label, target_label, row, target, attack_rate) in enumerate(attack_results):
                row_frame = ttk.Frame(self.time_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                label_text = f"{attack_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=20,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                for n in range(1, 11):
                    time = calculate_time_for_n_hits(n, attack_rate)
                    ttk.Label(row_frame, text=f"{time:.1f}s", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.time_frame.pack_forget()

    def _update_dps_display(self, attack_results):
        """Update the DPS range display (horizontal layout)"""
        # Clear existing
        for child in self.dps_container.winfo_children():
            child.destroy()

        if self.show_dps_range.get() and attack_results:
            self.dps_frame.pack(fill="x", pady=2)

            # Header row with seconds 1-10
            header_frame = ttk.Frame(self.dps_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="DPS:", width=20,
                      font=('Arial', 8, 'bold')).pack(side="left", padx=5)
            ttk.Label(header_frame, text="DPS", width=7,
                      font=('Arial', 8)).pack(side="left")
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}s", width=7,
                          font=('Arial', 8)).pack(side="left")

            # One row per attack+target combination showing DPS and damage over 1-10 seconds
            for i, (attack_label, target_label, row, target, attack_rate) in enumerate(attack_results):
                row_frame = ttk.Frame(self.dps_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                phys_reduction = target.get_physical_reduction()
                magic_reduction = target.get_magic_resistance()

                # For DPS with complex modifiers, calculate damage over 10 seconds and divide
                hits_in_10s = int(attack_rate * 10)
                if hits_in_10s > 0:
                    phys_10s = row.get_total_damage_for_hits(hits_in_10s) * (1 - phys_reduction)
                    magic_10s = row.get_total_magic_damage_for_hits(hits_in_10s) * (1 - magic_reduction)
                    dps = (phys_10s + magic_10s) / 10
                else:
                    dps = 0

                label_text = f"{attack_label} > {target_label}:"
                ttk.Label(row_frame, text=label_text, width=20,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                ttk.Label(row_frame, text=f"{dps:.1f}", width=7,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left")

                for seconds in range(1, 11):
                    # Calculate hits in this time period
                    hits = int(attack_rate * seconds)
                    if hits > 0:
                        phys_damage = row.get_total_damage_for_hits(hits) * (1 - phys_reduction)
                        magic_damage = row.get_total_magic_damage_for_hits(hits) * (1 - magic_reduction)
                        total = phys_damage + magic_damage
                    else:
                        total = 0
                    ttk.Label(row_frame, text=f"{total:.0f}", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.dps_frame.pack_forget()

    def hide_content(self):
        """Hide the section content"""
        if self.visible:
            self.section_frame.pack_forget()
            self.visible = False

    def clear(self):
        """Clear all attack mode data"""
        for row in self.attack_rows[:]:
            row.destroy()
        self.attack_rows.clear()
        self.attack_row_counter = 0

        for mod in self.modifiers[:]:
            mod.destroy()
        self.modifiers.clear()

        self.show_n_hits_range.set(False)
        self.show_time_range.set(False)
        self.show_dps_range.set(False)
