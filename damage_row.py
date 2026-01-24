import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS, PURE_DAMAGE_COLOR, DEFAULT_ATTACK_SPEED, DEFAULT_BAT
from utils import safe_eval, is_expression


class DamageRow:
    """Represents a single damage calculation row"""

    def __init__(self, parent, row_num, damage_type, on_change_callback, on_delete_callback, num_columns=1, is_pure=False):
        self.parent = parent
        self.row_num = row_num
        self.damage_type = damage_type
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.is_pure = is_pure
        self.num_columns = num_columns
        self.row_mode = "basic"  # "basic" or "dps"

        self.frame = ttk.Frame(parent)

        # Enabled checkbox
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_checkbox = ttk.Checkbutton(self.frame, variable=self.enabled_var)
        enabled_checkbox.grid(row=0, column=0, padx=(0, 2))

        # Row type toggle button
        self.mode_btn_var = tk.StringVar(value="DMG")
        self.mode_btn = ttk.Button(self.frame, textvariable=self.mode_btn_var, width=4,
                                   command=self._toggle_mode)
        self.mode_btn.grid(row=0, column=1, padx=2)

        # Damage input
        ttk.Label(self.frame, text=f"{damage_type} #{row_num}:", width=10).grid(
            row=0, column=2, sticky=tk.W, padx=2)

        self.damage_var = tk.StringVar(value="0")
        self.damage_var.trace('w', lambda *args: self.on_change())
        damage_entry = ttk.Entry(self.frame, textvariable=self.damage_var, width=10)
        damage_entry.grid(row=0, column=3, padx=2)

        # Attack speed and BAT inputs (for DPS mode, hidden by default)
        self.as_frame = ttk.Frame(self.frame)
        ttk.Label(self.as_frame, text="AS:", font=('Arial', 8)).pack(side="left")
        self.attack_speed_var = tk.StringVar(value=str(DEFAULT_ATTACK_SPEED))
        self.attack_speed_var.trace('w', lambda *args: self.on_change())
        self.as_entry = ttk.Entry(self.as_frame, textvariable=self.attack_speed_var, width=4)
        self.as_entry.pack(side="left", padx=1)
        ttk.Label(self.as_frame, text="BAT:", font=('Arial', 8)).pack(side="left", padx=(3, 0))
        self.bat_var = tk.StringVar(value=str(DEFAULT_BAT))
        self.bat_var.trace('w', lambda *args: self.on_change())
        self.bat_entry = ttk.Entry(self.as_frame, textvariable=self.bat_var, width=4)
        self.bat_entry.pack(side="left", padx=1)
        # Don't grid as_frame yet - it's hidden by default

        # Base damage label (shows evaluated expression)
        self.base_damage_var = tk.StringVar(value="")
        self.base_damage_label = ttk.Label(self.frame, textvariable=self.base_damage_var,
                                           font=('Arial', 9), foreground='#666', width=8)
        self.base_damage_label.grid(row=0, column=5, padx=2)

        # Result labels and per-column checkboxes (dynamic)
        self.result_vars = []
        self.result_labels = []
        self.column_enabled_vars = []
        self.column_checkboxes = []
        self.column_frames = []
        self._create_result_labels()

        # Delete button
        self.delete_btn = ttk.Button(self.frame, text="✕", width=3,
                                     command=lambda: self.on_delete(self))
        self._position_delete_button()

    def _toggle_mode(self):
        """Toggle between basic damage and DPS mode"""
        if self.row_mode == "basic":
            self.row_mode = "dps"
            self.mode_btn_var.set("DPS")
            self.as_frame.grid(row=0, column=4, padx=2)
        else:
            self.row_mode = "basic"
            self.mode_btn_var.set("DMG")
            self.as_frame.grid_forget()
        self.on_change()

    def _create_result_labels(self):
        """Create result labels with per-column checkboxes"""
        # Clear existing
        for frame in self.column_frames:
            frame.destroy()
        self.result_vars.clear()
        self.result_labels.clear()
        self.column_enabled_vars.clear()
        self.column_checkboxes.clear()
        self.column_frames.clear()

        # For pure damage, only show one column
        cols_to_show = 1 if self.is_pure else self.num_columns

        for i in range(cols_to_show):
            # Create a frame to hold checkbox and result together
            col_frame = ttk.Frame(self.frame)
            col_frame.grid(row=0, column=6 + i, padx=1)
            self.column_frames.append(col_frame)

            # Per-column checkbox
            col_enabled_var = tk.BooleanVar(value=True)
            col_enabled_var.trace('w', lambda *args: self.on_change())
            col_checkbox = ttk.Checkbutton(col_frame, variable=col_enabled_var)
            col_checkbox.pack(side="left")
            self.column_enabled_vars.append(col_enabled_var)
            self.column_checkboxes.append(col_checkbox)

            # Result label
            result_var = tk.StringVar(value="= 0.00")
            color = PURE_DAMAGE_COLOR if self.is_pure else COLUMN_COLORS[i % len(COLUMN_COLORS)]
            result_label = ttk.Label(col_frame, textvariable=result_var,
                                     font=('Arial', 9, 'bold'), foreground=color, width=9)
            result_label.pack(side="left")
            self.result_vars.append(result_var)
            self.result_labels.append(result_label)

    def _position_delete_button(self):
        """Position delete button after all result columns"""
        cols_to_show = 1 if self.is_pure else self.num_columns
        self.delete_btn.grid(row=0, column=6 + cols_to_show, padx=5)

    def update_columns(self, num_columns):
        """Update the number of result columns"""
        # Save current enabled states
        old_enabled = [var.get() for var in self.column_enabled_vars]

        self.num_columns = num_columns
        self._create_result_labels()
        self._position_delete_button()

        # Restore enabled states for existing columns
        for i, enabled in enumerate(old_enabled):
            if i < len(self.column_enabled_vars):
                self.column_enabled_vars[i].set(enabled)

    def calculate(self, reductions):
        """Calculate damage for this row with given reductions (list)"""
        # Check if entire row is disabled
        if not self.enabled_var.get():
            self.base_damage_var.set("")
            for i, var in enumerate(self.result_vars):
                var.set("= (off)")
                self.result_labels[i].configure(foreground='#999')
            return [0] * len(reductions)

        try:
            damage_str = self.damage_var.get()
            damage = safe_eval(damage_str)

            if damage is None:
                self.base_damage_var.set("")
                for var in self.result_vars:
                    var.set("= Invalid")
                return [0] * len(reductions)

            # Get attack rate for DPS mode: r = AS / (100 × BAT)
            attack_rate = 1.0
            if self.row_mode == "dps":
                as_str = self.attack_speed_var.get()
                bat_str = self.bat_var.get()
                as_val = safe_eval(as_str)
                bat_val = safe_eval(bat_str)
                if as_val is not None and bat_val is not None and bat_val > 0:
                    attack_rate = as_val / (100 * bat_val)
                else:
                    attack_rate = 1.0

            # Show base damage/dps info if input is an expression
            if is_expression(damage_str):
                if self.row_mode == "dps":
                    self.base_damage_var.set(f"({damage:.0f}@{attack_rate:.2f}/s)")
                else:
                    self.base_damage_var.set(f"({damage:.0f})")
            else:
                if self.row_mode == "dps":
                    self.base_damage_var.set(f"(@{attack_rate:.2f}/s)")
                else:
                    self.base_damage_var.set("")

            results = []
            for i, reduction in enumerate(reductions):
                # Check if this specific column is enabled
                col_enabled = True
                if i < len(self.column_enabled_vars):
                    col_enabled = self.column_enabled_vars[i].get()

                if col_enabled:
                    final_damage = damage * (1 - reduction / 100)
                    # Apply attack rate for DPS mode: DPS = damage * attack_rate
                    if self.row_mode == "dps":
                        final_damage = final_damage * attack_rate
                    if i < len(self.result_vars):
                        color = PURE_DAMAGE_COLOR if self.is_pure else COLUMN_COLORS[i % len(COLUMN_COLORS)]
                        self.result_labels[i].configure(foreground=color)
                        self.result_vars[i].set(f"= {final_damage:.2f}")
                    results.append(final_damage)
                else:
                    # Column disabled for this row
                    if i < len(self.result_vars):
                        self.result_labels[i].configure(foreground='#999')
                        self.result_vars[i].set("= (off)")
                    results.append(0)

            return results

        except ValueError:
            self.base_damage_var.set("")
            for var in self.result_vars:
                var.set("= Invalid")
            return [0] * len(reductions)

    def get_damage(self, reductions):
        """Get the calculated damage value"""
        return self.calculate(reductions)

    def destroy(self):
        """Remove this row"""
        self.frame.destroy()

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)
