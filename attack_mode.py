"""AttackModeSection class - orchestrates entire Attack Mode section"""

import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS, DEFAULT_ATTACK_SPEED, DEFAULT_BAT
from attack_row import AttackRow
from modifier import Modifier
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
        self.modifiers = []
        self.attack_row_counter = 0

        # Callback to notify when attack results change
        self.on_attack_results_changed = None

        # Display toggle states
        self.show_n_hits_range = tk.BooleanVar(value=False)
        self.show_time_range = tk.BooleanVar(value=False)
        self.show_dps_range = tk.BooleanVar(value=False)

        self._create_widgets()

        # Subscribe to column changes
        on_columns_change_subscribe(self._on_columns_changed)

    def _create_widgets(self):
        """Create all widgets for the Attack Mode section"""
        # Toggle button (always visible)
        self.toggle_frame = ttk.Frame(self.parent)
        self.toggle_button = ttk.Button(self.toggle_frame,
                                        text="▶ Show Attack Mode Section",
                                        command=self.toggle_visibility)
        self.toggle_button.pack(side="left")

        # Main section frame (hidden by default)
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

        # Damage per hit display
        self.dph_frame = ttk.Frame(self.section_frame)
        self.dph_frame.pack(fill="x", pady=2)
        ttk.Label(self.dph_frame, text="Damage/hit:").pack(side="left", padx=5)
        self.dph_labels_frame = ttk.Frame(self.dph_frame)
        self.dph_labels_frame.pack(side="left")
        self.dph_vars = []
        self.dph_labels = []

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

        # Initialize column displays
        self._update_column_displays()

    def _update_column_displays(self):
        """Update displays to match current column count"""
        num_columns = self.get_num_columns()

        # Clear existing dph labels
        for label in self.dph_labels:
            label.destroy()
        self.dph_vars.clear()
        self.dph_labels.clear()

        # Create new dph labels
        for i in range(num_columns):
            color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
            var = tk.StringVar(value="= 0.00")
            label = ttk.Label(self.dph_labels_frame, textvariable=var,
                              foreground=color, font=('Arial', 10, 'bold'))
            label.pack(side="left", padx=5)
            self.dph_vars.append(var)
            self.dph_labels.append(label)

    def _on_columns_changed(self, num_columns):
        """Handle column count changes"""
        self._update_column_displays()
        for row in self.attack_rows:
            row.update_columns(num_columns)
        self.calculate()

    def toggle_visibility(self):
        """Toggle section visibility"""
        if self.visible:
            self.section_frame.pack_forget()
            self.toggle_button.config(text="▶ Show Attack Mode Section")
            self.visible = False
        else:
            self.section_frame.pack(fill="x", pady=5, after=self.toggle_frame)
            self.toggle_button.config(text="▼ Hide Attack Mode Section")
            self.visible = True
            # Add initial rows if empty
            if not self.attack_rows:
                self.add_attack_row()

    def get_modifiers_values(self):
        """
        Get current modifier values.

        Returns:
            (flat_mods, pct_mods) - Lists of flat and percentage modifier values
        """
        flat_mods = []
        pct_mods = []

        for mod in self.modifiers:
            if mod.is_enabled():
                value = mod.get_value()
                if mod.get_type() == "flat":
                    flat_mods.append(value)
                else:
                    pct_mods.append(value)

        return flat_mods, pct_mods

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
            get_modifiers=self.get_modifiers_values
        )
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
        """Add a new modifier"""
        mod = Modifier(
            self.modifiers_container,
            self.calculate,
            self.delete_modifier,
            get_variables=self.get_variables
        )
        mod.pack(fill="x", pady=2)
        self.modifiers.append(mod)
        self.calculate()

    def delete_modifier(self, mod):
        """Delete a modifier"""
        self.modifiers.remove(mod)
        mod.destroy()
        self.calculate()

    def set_on_attack_results_changed(self, callback):
        """Set callback to be called when attack results change"""
        self.on_attack_results_changed = callback

    def calculate(self):
        """Calculate and update all displays"""
        if not self.visible:
            return

        num_columns = self.get_num_columns()
        flat_mods, pct_mods = self.get_modifiers_values()

        # Update modifier displays
        for mod in self.modifiers:
            mod.update_display()

        # Calculate totals per column
        # Each column gets: total_dph, total_damage, avg_attack_rate
        column_dph = [0] * num_columns
        column_total = [0] * num_columns
        column_attack_rates = [[] for _ in range(num_columns)]

        for row in self.attack_rows:
            row.update_display()
            results = row.get_results(flat_mods, pct_mods)
            for i, (dph, total, attack_rate) in enumerate(results):
                if i < num_columns:
                    column_dph[i] += dph
                    column_total[i] += total
                    if attack_rate > 0:
                        column_attack_rates[i].append(attack_rate)

        # Update damage per hit display
        for i in range(num_columns):
            if i < len(self.dph_vars):
                self.dph_vars[i].set(f"= {column_dph[i]:.2f}")

        # Calculate average attack rate per column (for time calculations)
        avg_attack_rates = []
        for rates in column_attack_rates:
            if rates:
                avg_attack_rates.append(sum(rates) / len(rates))
            else:
                avg_attack_rates.append(1.0)

        # Update N hits range display
        self._update_n_hits_display(column_dph, num_columns)

        # Update time range display
        self._update_time_display(column_dph, avg_attack_rates, num_columns)

        # Update DPS range display
        self._update_dps_display(column_dph, avg_attack_rates, num_columns)

        # Notify target section of updated attack results
        if self.on_attack_results_changed:
            attack_results = []
            for i in range(num_columns):
                dph = column_dph[i]
                total = column_total[i]
                rate = avg_attack_rates[i] if i < len(avg_attack_rates) else 1.0
                attack_results.append((dph, total, rate))
            self.on_attack_results_changed(attack_results)

    def _update_n_hits_display(self, column_dph, num_columns):
        """Update the N hits range display (horizontal layout)"""
        # Clear existing
        for child in self.n_hits_container.winfo_children():
            child.destroy()

        if self.show_n_hits_range.get():
            self.n_hits_frame.pack(fill="x", pady=2)

            # Header row with hit counts 1-10
            header_frame = ttk.Frame(self.n_hits_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Hits:", width=8).pack(side="left", padx=5)
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}", width=7,
                          font=('Arial', 8, 'bold')).pack(side="left")

            # One row per column showing damage for 1-10 hits
            for i in range(num_columns):
                row_frame = ttk.Frame(self.n_hits_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                ttk.Label(row_frame, text=f"Col{i+1}:", width=8,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                for n in range(1, 11):
                    damage = calculate_damage_for_n_hits(column_dph[i], n)
                    ttk.Label(row_frame, text=f"{damage:.0f}", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.n_hits_frame.pack_forget()

    def _update_time_display(self, column_dph, attack_rates, num_columns):
        """Update the time range display (horizontal layout)"""
        # Clear existing
        for child in self.time_container.winfo_children():
            child.destroy()

        if self.show_time_range.get():
            self.time_frame.pack(fill="x", pady=2)

            # Header row with hit counts 1-10
            header_frame = ttk.Frame(self.time_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Hits:", width=8).pack(side="left", padx=5)
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}", width=7,
                          font=('Arial', 8, 'bold')).pack(side="left")

            # One row per column showing time for 1-10 hits
            for i in range(num_columns):
                row_frame = ttk.Frame(self.time_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                ttk.Label(row_frame, text=f"Col{i+1}:", width=8,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                rate = attack_rates[i] if i < len(attack_rates) else 1.0
                for n in range(1, 11):
                    time = calculate_time_for_n_hits(n, rate)
                    ttk.Label(row_frame, text=f"{time:.1f}s", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.time_frame.pack_forget()

    def _update_dps_display(self, column_dph, attack_rates, num_columns):
        """Update the DPS range display (horizontal layout)"""
        # Clear existing
        for child in self.dps_container.winfo_children():
            child.destroy()

        if self.show_dps_range.get():
            self.dps_frame.pack(fill="x", pady=2)

            # Header row with seconds 1-10
            header_frame = ttk.Frame(self.dps_container)
            header_frame.pack(fill="x")
            ttk.Label(header_frame, text="Sec:", width=8).pack(side="left", padx=5)
            ttk.Label(header_frame, text="DPS", width=7,
                      font=('Arial', 8, 'bold')).pack(side="left")
            for n in range(1, 11):
                ttk.Label(header_frame, text=f"{n}s", width=7,
                          font=('Arial', 8, 'bold')).pack(side="left")

            # One row per column showing DPS and damage over 1-10 seconds
            for i in range(num_columns):
                row_frame = ttk.Frame(self.dps_container)
                row_frame.pack(fill="x")
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                rate = attack_rates[i] if i < len(attack_rates) else 1.0
                dps = calculate_dps(column_dph[i], rate)
                ttk.Label(row_frame, text=f"Col{i+1}:", width=8,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left", padx=5)
                ttk.Label(row_frame, text=f"{dps:.1f}", width=7,
                          foreground=color, font=('Arial', 8, 'bold')).pack(side="left")
                for n in range(1, 11):
                    damage = calculate_damage_in_time(column_dph[i], rate, n)
                    ttk.Label(row_frame, text=f"{damage:.0f}", width=7,
                              foreground=color, font=('Arial', 8)).pack(side="left")
        else:
            self.dps_frame.pack_forget()

    def pack_toggle(self, **kwargs):
        """Pack just the toggle button frame"""
        self.toggle_frame.pack(**kwargs)

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
