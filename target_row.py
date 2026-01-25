"""TargetRow class - target with HP, regen, armor, magic resistance"""

import tkinter as tk
from tkinter import ttk

from utils import safe_eval, armor_to_reduction, reduction_to_armor
from attack_calculations import (
    apply_physical_reduction,
    calculate_hits_to_kill,
    calculate_time_to_kill
)


class TargetRow:
    """Represents a single target configuration row"""

    def __init__(self, parent, row_num, on_change_callback, on_delete_callback,
                 num_columns=1, get_variables=None, armor_mode=True):
        """
        Initialize a target row.

        Args:
            parent: Parent widget
            row_num: Row number for labeling
            on_change_callback: Called when values change
            on_delete_callback: Called when delete button is clicked
            num_columns: Number of comparison columns
            get_variables: Callback to get current variables dict
            armor_mode: True for armor input, False for reduction % input
        """
        self.parent = parent
        self.row_num = row_num
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.num_columns = num_columns
        self.get_variables = get_variables
        self.armor_mode = armor_mode

        self.frame = ttk.Frame(parent)

        # Row 0: Main inputs
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill="x", pady=2)

        # Enabled checkbox
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(input_frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Label/name
        ttk.Label(input_frame, text="Label:").pack(side="left")
        self.label_var = tk.StringVar(value=f"Target {row_num}")
        label_entry = ttk.Entry(input_frame, textvariable=self.label_var, width=10)
        label_entry.pack(side="left", padx=2)

        # HP
        ttk.Label(input_frame, text="HP:").pack(side="left", padx=(10, 0))
        self.hp_var = tk.StringVar(value="")
        self.hp_var.trace('w', lambda *args: self.on_change())
        hp_entry = ttk.Entry(input_frame, textvariable=self.hp_var, width=6)
        hp_entry.pack(side="left", padx=2)

        # HP Regen
        ttk.Label(input_frame, text="Regen:").pack(side="left", padx=(5, 0))
        self.regen_var = tk.StringVar(value="0")
        self.regen_var.trace('w', lambda *args: self.on_change())
        regen_entry = ttk.Entry(input_frame, textvariable=self.regen_var, width=4)
        regen_entry.pack(side="left", padx=2)
        ttk.Label(input_frame, text="/s").pack(side="left")

        # Armor/Reduction input
        self.armor_label_var = tk.StringVar(value="Armor:" if armor_mode else "Reduc%:")
        self.armor_label = ttk.Label(input_frame, textvariable=self.armor_label_var)
        self.armor_label.pack(side="left", padx=(10, 0))
        self.armor_var = tk.StringVar(value="0")
        self.armor_var.trace('w', lambda *args: self.on_change())
        armor_entry = ttk.Entry(input_frame, textvariable=self.armor_var, width=4)
        armor_entry.pack(side="left", padx=2)

        # Armor/reduction conversion display (always shown)
        self.armor_reduction_var = tk.StringVar(value="(0%)")
        armor_reduction_label = ttk.Label(input_frame, textvariable=self.armor_reduction_var,
                                          foreground='#666', font=('Arial', 8))
        armor_reduction_label.pack(side="left")

        # Magic Resistance
        ttk.Label(input_frame, text="MR:").pack(side="left", padx=(10, 0))
        self.mr_var = tk.StringVar(value="25")
        self.mr_var.trace('w', lambda *args: self.on_change())
        mr_entry = ttk.Entry(input_frame, textvariable=self.mr_var, width=4)
        mr_entry.pack(side="left", padx=2)
        ttk.Label(input_frame, text="%").pack(side="left")

        # Delete button
        delete_btn = ttk.Button(input_frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="right", padx=5)

        # Results display (single row)
        self.results_frame = ttk.Frame(self.frame)
        self.results_frame.pack(fill="x", pady=(0, 5), padx=(25, 0))

        self.result_var = tk.StringVar(value="")
        result_label = ttk.Label(self.results_frame, textvariable=self.result_var,
                                 foreground='#333', font=('Arial', 9))
        result_label.pack(side="left")

    def update_columns(self, num_columns):
        """Update the number of columns"""
        self.num_columns = num_columns

    def set_armor_mode(self, armor_mode):
        """Set armor input mode and convert current value"""
        if armor_mode == self.armor_mode:
            return

        variables = self.get_variables() if self.get_variables else None
        current_val = safe_eval(self.armor_var.get(), variables) or 0

        if armor_mode:
            # Switching to armor mode - convert reduction to armor
            self.armor_label_var.set("Armor:")
            armor = reduction_to_armor(current_val)
            self.armor_var.set(f"{armor:.1f}")
        else:
            # Switching to reduction mode - convert armor to reduction
            self.armor_label_var.set("Reduc%:")
            reduction = armor_to_reduction(current_val)
            self.armor_var.set(f"{reduction:.1f}")

        self.armor_mode = armor_mode

    def is_enabled(self):
        """Check if target is enabled"""
        return self.enabled_var.get()

    def get_hp(self):
        """Get evaluated HP value"""
        variables = self.get_variables() if self.get_variables else None
        hp = safe_eval(self.hp_var.get(), variables)
        return hp if hp and hp > 0 else None

    def get_regen(self):
        """Get HP regen per second"""
        variables = self.get_variables() if self.get_variables else None
        regen = safe_eval(self.regen_var.get(), variables)
        return regen if regen is not None else 0

    def get_armor(self):
        """Get armor value"""
        variables = self.get_variables() if self.get_variables else None
        armor = safe_eval(self.armor_var.get(), variables)
        return armor if armor is not None else 0

    def get_physical_reduction(self):
        """Get physical damage reduction as decimal"""
        variables = self.get_variables() if self.get_variables else None
        val = safe_eval(self.armor_var.get(), variables) or 0

        if self.armor_mode:
            # Value is armor, convert to reduction
            return armor_to_reduction(val) / 100  # Convert percentage to decimal
        else:
            # Value is already reduction percentage
            return val / 100

    def get_magic_resistance(self):
        """Get magic resistance as decimal"""
        variables = self.get_variables() if self.get_variables else None
        mr = safe_eval(self.mr_var.get(), variables)
        return (mr / 100) if mr is not None else 0.25

    def apply_reductions(self, physical_damage, magic_damage=0):
        """
        Apply armor and magic resistance reductions.

        Args:
            physical_damage: Raw physical damage
            magic_damage: Raw magic damage (default 0)

        Returns:
            Total reduced damage (physical + magic after reductions)
        """
        phys_reduced = physical_damage * (1 - self.get_physical_reduction())
        magic_reduced = magic_damage * (1 - self.get_magic_resistance())
        return phys_reduced + magic_reduced

    def update_display(self, attack_results):
        """
        Update the display with calculated results.

        Args:
            attack_results: Tuple of (damage_per_hit, total_damage, attack_rate)
        """
        if not self.enabled_var.get():
            self.result_var.set("(disabled)")
            return

        # Update armor/reduction conversion display
        variables = self.get_variables() if self.get_variables else None
        val = safe_eval(self.armor_var.get(), variables) or 0

        if self.armor_mode:
            # Show reduction percentage for armor input
            reduction_pct = armor_to_reduction(val)
            self.armor_reduction_var.set(f"({reduction_pct:.0f}%)")
        else:
            # Show armor equivalent for reduction input
            armor = reduction_to_armor(val)
            self.armor_reduction_var.set(f"(={armor:.0f} armor)")

        # Get attack values
        dph, total, attack_rate = attack_results

        if dph == 0:
            self.result_var.set("")
            return

        hp = self.get_hp()
        regen = self.get_regen()
        phys_reduction = self.get_physical_reduction()

        # Apply physical reduction to damage per hit
        reduced_dph = dph * (1 - phys_reduction)
        reduced_total = total * (1 - phys_reduction)

        parts = [f"Dmg/hit: {reduced_dph:.0f}"]

        if hp:
            parts.append(f"Total: {reduced_total:.0f}")

            # Calculate hits and time to kill
            hits_to_kill = calculate_hits_to_kill(hp, reduced_dph, regen, attack_rate)
            if hits_to_kill == float('inf'):
                parts.append("Hits: INF")
                parts.append("Time: INF")
            else:
                parts.append(f"Hits: {hits_to_kill}")
                time_to_kill = calculate_time_to_kill(hp, reduced_dph, attack_rate, regen)
                if time_to_kill == float('inf'):
                    parts.append("Time: INF")
                else:
                    parts.append(f"Time: {time_to_kill:.1f}s")

        self.result_var.set(" | ".join(parts))

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this row"""
        self.frame.destroy()
