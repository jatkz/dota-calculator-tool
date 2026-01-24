"""AttackRow class - attack configuration with base/bonus damage, hits, AS, BAT"""

import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS, DEFAULT_ATTACK_SPEED, DEFAULT_BAT
from utils import safe_eval, is_expression
from attack_calculations import calculate_attack_rate, calculate_damage_per_hit


class AttackRow:
    """Represents a single attack configuration row"""

    def __init__(self, parent, row_num, on_change_callback, on_delete_callback,
                 num_columns=1, get_variables=None, get_modifiers=None):
        """
        Initialize an attack row.

        Args:
            parent: Parent widget
            row_num: Row number for labeling
            on_change_callback: Called when values change
            on_delete_callback: Called when delete button is clicked
            num_columns: Number of comparison columns
            get_variables: Callback to get current variables dict
            get_modifiers: Callback to get current modifiers (flat_list, pct_list)
        """
        self.parent = parent
        self.row_num = row_num
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.num_columns = num_columns
        self.get_variables = get_variables
        self.get_modifiers = get_modifiers

        self.frame = ttk.Frame(parent)

        # Row 0: Main inputs
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill="x", pady=2)

        # Enabled checkbox
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(input_frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Base damage
        ttk.Label(input_frame, text="Base:").pack(side="left")
        self.base_var = tk.StringVar(value="0")
        self.base_var.trace('w', lambda *args: self.on_change())
        base_entry = ttk.Entry(input_frame, textvariable=self.base_var, width=6)
        base_entry.pack(side="left", padx=2)

        # Plus sign
        ttk.Label(input_frame, text="+").pack(side="left")

        # Bonus damage
        ttk.Label(input_frame, text="Bonus:").pack(side="left")
        self.bonus_var = tk.StringVar(value="0")
        self.bonus_var.trace('w', lambda *args: self.on_change())
        bonus_entry = ttk.Entry(input_frame, textvariable=self.bonus_var, width=6)
        bonus_entry.pack(side="left", padx=2)

        # Number of hits
        ttk.Label(input_frame, text="Hits:").pack(side="left", padx=(10, 0))
        self.hits_var = tk.StringVar(value="1")
        self.hits_var.trace('w', lambda *args: self.on_change())
        hits_entry = ttk.Entry(input_frame, textvariable=self.hits_var, width=4)
        hits_entry.pack(side="left", padx=2)

        # Attack speed
        ttk.Label(input_frame, text="AS:").pack(side="left", padx=(10, 0))
        self.as_var = tk.StringVar(value=str(DEFAULT_ATTACK_SPEED))
        self.as_var.trace('w', lambda *args: self.on_change())
        as_entry = ttk.Entry(input_frame, textvariable=self.as_var, width=4)
        as_entry.pack(side="left", padx=2)

        # BAT
        ttk.Label(input_frame, text="BAT:").pack(side="left", padx=(5, 0))
        self.bat_var = tk.StringVar(value=str(DEFAULT_BAT))
        self.bat_var.trace('w', lambda *args: self.on_change())
        bat_entry = ttk.Entry(input_frame, textvariable=self.bat_var, width=4)
        bat_entry.pack(side="left", padx=2)

        # Evaluated base damage display
        self.eval_var = tk.StringVar(value="")
        eval_label = ttk.Label(input_frame, textvariable=self.eval_var,
                               foreground='#666', font=('Arial', 8))
        eval_label.pack(side="left", padx=5)

        # Delete button
        delete_btn = ttk.Button(input_frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="right", padx=5)

        # Row 1: Per-column checkboxes and results
        self.results_frame = ttk.Frame(self.frame)
        self.results_frame.pack(fill="x", pady=(0, 2), padx=(25, 0))

        # Column-specific widgets
        self.column_enabled_vars = []
        self.column_checkboxes = []
        self.result_vars = []
        self.result_labels = []
        self.column_frames = []

        self._create_column_widgets()

    def _create_column_widgets(self):
        """Create per-column checkboxes and result labels"""
        # Clear existing
        for frame in self.column_frames:
            frame.destroy()
        self.column_enabled_vars.clear()
        self.column_checkboxes.clear()
        self.result_vars.clear()
        self.result_labels.clear()
        self.column_frames.clear()

        for i in range(self.num_columns):
            col_frame = ttk.Frame(self.results_frame)
            col_frame.pack(side="left", padx=5)
            self.column_frames.append(col_frame)

            # Per-column checkbox
            col_enabled_var = tk.BooleanVar(value=True)
            col_enabled_var.trace('w', lambda *args: self.on_change())
            col_checkbox = ttk.Checkbutton(col_frame, variable=col_enabled_var)
            col_checkbox.pack(side="left")
            self.column_enabled_vars.append(col_enabled_var)
            self.column_checkboxes.append(col_checkbox)

            # Column label
            col_label = ttk.Label(col_frame, text=f"Col{i+1}",
                                  foreground=COLUMN_COLORS[i % len(COLUMN_COLORS)],
                                  font=('Arial', 8))
            col_label.pack(side="left")

            # Result label
            result_var = tk.StringVar(value="= 0.00")
            result_label = ttk.Label(col_frame, textvariable=result_var,
                                     font=('Arial', 9, 'bold'),
                                     foreground=COLUMN_COLORS[i % len(COLUMN_COLORS)],
                                     width=10)
            result_label.pack(side="left", padx=(5, 0))
            self.result_vars.append(result_var)
            self.result_labels.append(result_label)

    def update_columns(self, num_columns):
        """Update the number of columns"""
        old_enabled = [var.get() for var in self.column_enabled_vars]
        self.num_columns = num_columns
        self._create_column_widgets()

        # Restore enabled states
        for i, enabled in enumerate(old_enabled):
            if i < len(self.column_enabled_vars):
                self.column_enabled_vars[i].set(enabled)

    def is_enabled(self):
        """Check if row is enabled"""
        return self.enabled_var.get()

    def is_column_enabled(self, col_idx):
        """Check if specific column is enabled for this row"""
        if col_idx < len(self.column_enabled_vars):
            return self.column_enabled_vars[col_idx].get()
        return True

    def get_base_damage(self):
        """Get evaluated base damage value"""
        variables = self.get_variables() if self.get_variables else None
        return safe_eval(self.base_var.get(), variables) or 0

    def get_bonus_damage(self):
        """Get evaluated bonus damage value"""
        variables = self.get_variables() if self.get_variables else None
        return safe_eval(self.bonus_var.get(), variables) or 0

    def get_hits(self):
        """Get number of hits"""
        variables = self.get_variables() if self.get_variables else None
        hits = safe_eval(self.hits_var.get(), variables)
        return max(1, int(hits)) if hits is not None else 1

    def get_attack_speed(self):
        """Get attack speed value"""
        variables = self.get_variables() if self.get_variables else None
        return safe_eval(self.as_var.get(), variables) or DEFAULT_ATTACK_SPEED

    def get_bat(self):
        """Get BAT value"""
        variables = self.get_variables() if self.get_variables else None
        bat = safe_eval(self.bat_var.get(), variables)
        return bat if bat and bat > 0 else DEFAULT_BAT

    def get_attack_rate(self):
        """Get attacks per second"""
        return calculate_attack_rate(self.get_attack_speed(), self.get_bat())

    def calculate_damage_per_hit(self, flat_mods=None, pct_mods=None):
        """
        Calculate damage per hit with modifiers.

        Args:
            flat_mods: List of flat modifier values
            pct_mods: List of percentage modifier values (as decimals)

        Returns:
            Damage per hit
        """
        flat_mods = flat_mods or []
        pct_mods = pct_mods or []
        return calculate_damage_per_hit(
            self.get_base_damage(),
            self.get_bonus_damage(),
            flat_mods,
            pct_mods
        )

    def calculate_total_damage(self, flat_mods=None, pct_mods=None):
        """
        Calculate total damage for all hits.

        Args:
            flat_mods: List of flat modifier values
            pct_mods: List of percentage modifier values (as decimals)

        Returns:
            Total damage for N hits
        """
        dph = self.calculate_damage_per_hit(flat_mods, pct_mods)
        return dph * self.get_hits()

    def update_display(self):
        """Update the display with calculated values"""
        if not self.enabled_var.get():
            self.eval_var.set("(disabled)")
            for i, var in enumerate(self.result_vars):
                var.set("= (off)")
                self.result_labels[i].configure(foreground='#999')
            return

        # Get modifiers
        flat_mods, pct_mods = [], []
        if self.get_modifiers:
            flat_mods, pct_mods = self.get_modifiers()

        # Calculate base values
        base = self.get_base_damage()
        bonus = self.get_bonus_damage()
        total_base = base + bonus

        # Show evaluated expression if input contains operators
        base_str = self.base_var.get()
        bonus_str = self.bonus_var.get()
        if is_expression(base_str) or is_expression(bonus_str):
            self.eval_var.set(f"= {total_base:.0f}")
        else:
            self.eval_var.set("")

        # Calculate damage per hit
        dph = self.calculate_damage_per_hit(flat_mods, pct_mods)
        hits = self.get_hits()
        total = dph * hits

        # Update per-column results
        for i in range(self.num_columns):
            if i < len(self.column_enabled_vars) and self.column_enabled_vars[i].get():
                color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                self.result_labels[i].configure(foreground=color)
                if hits > 1:
                    self.result_vars[i].set(f"= {total:.2f}")
                else:
                    self.result_vars[i].set(f"= {dph:.2f}")
            else:
                self.result_labels[i].configure(foreground='#999')
                self.result_vars[i].set("= (off)")

    def get_results(self, flat_mods=None, pct_mods=None):
        """
        Get calculation results for all columns.

        Returns:
            List of (damage_per_hit, total_damage, attack_rate) for each column,
            or (0, 0, 0) for disabled columns
        """
        if not self.enabled_var.get():
            return [(0, 0, 0)] * self.num_columns

        dph = self.calculate_damage_per_hit(flat_mods, pct_mods)
        hits = self.get_hits()
        total = dph * hits
        attack_rate = self.get_attack_rate()

        results = []
        for i in range(self.num_columns):
            if i < len(self.column_enabled_vars) and self.column_enabled_vars[i].get():
                results.append((dph, total, attack_rate))
            else:
                results.append((0, 0, 0))
        return results

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this row"""
        self.frame.destroy()
