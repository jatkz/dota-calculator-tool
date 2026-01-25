"""AttackRow class - attack configuration with base/bonus damage, hits, AS, BAT"""

import tkinter as tk
from tkinter import ttk

from constants import DEFAULT_ATTACK_SPEED, DEFAULT_BAT
from utils import safe_eval, is_expression
from attack_calculations import calculate_attack_rate, calculate_damage_per_hit


class AttackRow:
    """Represents a single attack configuration row"""

    def __init__(self, parent, row_num, on_change_callback, on_delete_callback,
                 num_columns=1, get_variables=None, get_modifiers=None,
                 get_complex_modifiers=None, get_targets=None):
        """
        Initialize an attack row.

        Args:
            parent: Parent widget
            row_num: Row number for labeling
            on_change_callback: Called when values change
            on_delete_callback: Called when delete button is clicked
            num_columns: Number of comparison columns
            get_variables: Callback to get current variables dict
            get_modifiers: Callback to get simple modifiers list
            get_complex_modifiers: Callback to get complex modifiers list
            get_targets: Callback to get available targets list
        """
        self.parent = parent
        self.row_num = row_num
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.num_columns = num_columns
        self.get_variables = get_variables
        self.get_modifiers = get_modifiers
        self.get_complex_modifiers = get_complex_modifiers
        self.get_targets = get_targets
        self.selected_targets = []  # List of selected target rows
        self.selected_modifiers = []  # List of selected simple modifiers
        self.selected_complex_modifiers = []  # List of selected complex modifiers

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
        self.label_var = tk.StringVar(value=f"Attack {row_num}")
        label_entry = ttk.Entry(input_frame, textvariable=self.label_var, width=10)
        label_entry.pack(side="left", padx=2)

        # Base damage
        ttk.Label(input_frame, text="Base:").pack(side="left", padx=(5, 0))
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

        # Delete button (pack first so it's on right)
        delete_btn = ttk.Button(input_frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="right", padx=5)

        # Evaluated base damage display
        self.eval_var = tk.StringVar(value="")
        eval_label = ttk.Label(input_frame, textvariable=self.eval_var,
                               foreground='#666', font=('Arial', 8))
        eval_label.pack(side="right", padx=5)

        # Row for target and modifier dropdowns
        selection_frame = ttk.Frame(self.frame)
        selection_frame.pack(fill="x", pady=(2, 0), padx=(25, 0))

        # Target dropdown and add button
        ttk.Label(selection_frame, text="Target:").pack(side="left")
        self.target_var = tk.StringVar(value="")
        self.target_combo = ttk.Combobox(selection_frame, textvariable=self.target_var,
                                         state="readonly", width=10)
        self.target_combo['values'] = []
        self.target_combo.pack(side="left", padx=2)

        # Add target button
        self.add_target_btn = ttk.Button(selection_frame, text="+", width=2,
                                         command=self._add_selected_target)
        self.add_target_btn.pack(side="left", padx=(0, 10))

        # Modifier dropdown and add button
        ttk.Label(selection_frame, text="Modifier:").pack(side="left")
        self.modifier_var = tk.StringVar(value="")
        self.modifier_combo = ttk.Combobox(selection_frame, textvariable=self.modifier_var,
                                           state="readonly", width=10)
        self.modifier_combo['values'] = []
        self.modifier_combo.pack(side="left", padx=2)

        # Add modifier button
        self.add_modifier_btn = ttk.Button(selection_frame, text="+", width=2,
                                           command=self._add_selected_modifier)
        self.add_modifier_btn.pack(side="left", padx=(0, 10))

        # Complex modifier dropdown and add button
        ttk.Label(selection_frame, text="Complex:").pack(side="left")
        self.complex_mod_var = tk.StringVar(value="")
        self.complex_mod_combo = ttk.Combobox(selection_frame, textvariable=self.complex_mod_var,
                                              state="readonly", width=12)
        self.complex_mod_combo['values'] = []
        self.complex_mod_combo.pack(side="left", padx=2)

        # Add complex modifier button
        self.add_complex_mod_btn = ttk.Button(selection_frame, text="+", width=2,
                                              command=self._add_selected_complex_modifier)
        self.add_complex_mod_btn.pack(side="left")

        # Row for displaying selected targets
        self.targets_frame = ttk.Frame(self.frame)
        self.targets_frame.pack(fill="x", pady=(2, 0), padx=(25, 0))
        self.target_widgets = []  # List of (target, frame) for removal

        # Row for displaying selected modifiers (simple + complex)
        self.modifiers_frame = ttk.Frame(self.frame)
        self.modifiers_frame.pack(fill="x", pady=(2, 2), padx=(25, 0))
        self.modifier_widgets = []  # List of (modifier, frame) for removal
        self.complex_modifier_widgets = []  # List of (complex_mod, frame) for removal

    def update_columns(self, num_columns):
        """Update the number of columns"""
        self.num_columns = num_columns

    def update_target_options(self):
        """Update the target dropdown with available targets"""
        if not self.get_targets:
            return

        targets = self.get_targets()
        options = []
        for target in targets:
            # Don't show targets already selected
            if target not in self.selected_targets:
                label = target.label_var.get()
                options.append(label)

        self.target_combo['values'] = options
        if options:
            self.target_var.set(options[0])
        else:
            self.target_var.set("")

        # Remove any selected targets that no longer exist
        available_targets = self.get_targets() if self.get_targets else []
        self.selected_targets = [t for t in self.selected_targets if t in available_targets]
        self._update_targets_display()

    def _add_selected_target(self):
        """Add the currently selected target from dropdown"""
        selected_label = self.target_var.get()
        if not selected_label:
            return

        # Find the target with this label
        if self.get_targets:
            for target in self.get_targets():
                if target.label_var.get() == selected_label:
                    if target not in self.selected_targets:
                        self.selected_targets.append(target)
                        self._update_targets_display()
                        self.update_target_options()  # Refresh dropdown
                        self.on_change()
                    break

    def _remove_target(self, target):
        """Remove a specific target from the selection"""
        if target in self.selected_targets:
            self.selected_targets.remove(target)
            self._update_targets_display()
            self.update_target_options()  # Refresh dropdown
            self.on_change()

    def _update_targets_display(self):
        """Update the display of selected targets"""
        # Clear existing widgets
        for _, frame in self.target_widgets:
            frame.destroy()
        self.target_widgets.clear()

        # Create widgets for each selected target
        for target in self.selected_targets:
            target_frame = ttk.Frame(self.targets_frame)
            target_frame.pack(side="left", padx=2)

            label = target.label_var.get()
            ttk.Label(target_frame, text=label, font=('Arial', 8),
                      foreground='#333').pack(side="left")

            # Remove button for this target
            remove_btn = ttk.Button(target_frame, text="✕", width=2,
                                    command=lambda t=target: self._remove_target(t))
            remove_btn.pack(side="left", padx=1)

            self.target_widgets.append((target, target_frame))

    def get_selected_targets(self):
        """Get list of currently selected target rows"""
        return self.selected_targets

    def update_modifier_options(self):
        """Update the modifier dropdown with available modifiers"""
        if not self.get_modifiers:
            return

        modifiers = self.get_modifiers()
        options = []
        for mod in modifiers:
            # Don't show modifiers already selected
            if mod not in self.selected_modifiers:
                name = mod.get_name()
                options.append(name)

        self.modifier_combo['values'] = options
        if options:
            self.modifier_var.set(options[0])
        else:
            self.modifier_var.set("")

        # Remove any selected modifiers that no longer exist
        available_modifiers = self.get_modifiers() if self.get_modifiers else []
        self.selected_modifiers = [m for m in self.selected_modifiers if m in available_modifiers]
        self._update_modifiers_display()

    def _add_selected_modifier(self):
        """Add the currently selected modifier from dropdown"""
        selected_name = self.modifier_var.get()
        if not selected_name:
            return

        # Find the modifier with this name
        if self.get_modifiers:
            for mod in self.get_modifiers():
                if mod.get_name() == selected_name:
                    if mod not in self.selected_modifiers:
                        self.selected_modifiers.append(mod)
                        self._update_modifiers_display()
                        self.update_modifier_options()  # Refresh dropdown
                        self.on_change()
                    break

    def _remove_modifier(self, mod):
        """Remove a specific modifier from the selection"""
        if mod in self.selected_modifiers:
            self.selected_modifiers.remove(mod)
            self._update_modifiers_display()
            self.update_modifier_options()  # Refresh dropdown
            self.on_change()

    def _update_modifiers_display(self):
        """Update the display of selected modifiers"""
        # Clear existing widgets
        for _, frame in self.modifier_widgets:
            frame.destroy()
        self.modifier_widgets.clear()

        # Create widgets for each selected modifier
        for mod in self.selected_modifiers:
            mod_frame = ttk.Frame(self.modifiers_frame)
            mod_frame.pack(side="left", padx=2)

            name = mod.get_name()
            mod_type = mod.get_type()
            value = mod.get_value()
            if mod_type == "flat":
                display = f"{name}: +{value:.0f}"
            else:
                display = f"{name}: {value:.0f}%"

            ttk.Label(mod_frame, text=display, font=('Arial', 8),
                      foreground='#555').pack(side="left")

            # Remove button for this modifier
            remove_btn = ttk.Button(mod_frame, text="✕", width=2,
                                    command=lambda m=mod: self._remove_modifier(m))
            remove_btn.pack(side="left", padx=1)

            self.modifier_widgets.append((mod, mod_frame))

    def get_selected_modifiers(self):
        """Get list of currently selected modifiers"""
        return self.selected_modifiers

    def get_selected_modifier_values(self):
        """Get flat and percentage modifier values from selected modifiers"""
        flat_mods = []
        pct_mods = []
        for mod in self.selected_modifiers:
            if mod.is_enabled():
                value = mod.get_value()
                if mod.get_type() == "flat":
                    flat_mods.append(value)
                else:
                    pct_mods.append(value)
        return flat_mods, pct_mods

    def update_complex_modifier_options(self):
        """Update the complex modifier dropdown with available complex modifiers"""
        if not self.get_complex_modifiers:
            return

        complex_mods = self.get_complex_modifiers()
        options = []
        for mod in complex_mods:
            # Don't show complex modifiers already selected
            if mod not in self.selected_complex_modifiers:
                label = mod.get_label()
                options.append(label)

        self.complex_mod_combo['values'] = options
        if options:
            self.complex_mod_var.set(options[0])
        else:
            self.complex_mod_var.set("")

        # Remove any selected complex modifiers that no longer exist
        available = self.get_complex_modifiers() if self.get_complex_modifiers else []
        self.selected_complex_modifiers = [m for m in self.selected_complex_modifiers if m in available]
        self._update_complex_modifiers_display()

    def _add_selected_complex_modifier(self):
        """Add the currently selected complex modifier from dropdown"""
        selected_label = self.complex_mod_var.get()
        if not selected_label:
            return

        # Find the complex modifier with this label
        if self.get_complex_modifiers:
            for mod in self.get_complex_modifiers():
                if mod.get_label() == selected_label:
                    if mod not in self.selected_complex_modifiers:
                        self.selected_complex_modifiers.append(mod)
                        self._update_complex_modifiers_display()
                        self.update_complex_modifier_options()  # Refresh dropdown
                        self.on_change()
                    break

    def _remove_complex_modifier(self, mod):
        """Remove a specific complex modifier from the selection"""
        if mod in self.selected_complex_modifiers:
            self.selected_complex_modifiers.remove(mod)
            self._update_complex_modifiers_display()
            self.update_complex_modifier_options()  # Refresh dropdown
            self.on_change()

    def _update_complex_modifiers_display(self):
        """Update the display of selected complex modifiers"""
        # Clear existing widgets
        for _, frame in self.complex_modifier_widgets:
            frame.destroy()
        self.complex_modifier_widgets.clear()

        # Create widgets for each selected complex modifier
        for mod in self.selected_complex_modifiers:
            mod_frame = ttk.Frame(self.modifiers_frame)
            mod_frame.pack(side="left", padx=2)

            label = mod.get_label()
            ttk.Label(mod_frame, text=label, font=('Arial', 8, 'bold'),
                      foreground='#8B4513').pack(side="left")

            # Remove button for this complex modifier
            remove_btn = ttk.Button(mod_frame, text="✕", width=2,
                                    command=lambda m=mod: self._remove_complex_modifier(m))
            remove_btn.pack(side="left", padx=1)

            self.complex_modifier_widgets.append((mod, mod_frame))

    def get_selected_complex_modifiers(self):
        """Get list of currently selected complex modifiers"""
        return self.selected_complex_modifiers

    def get_damage_for_hit(self, hit_number):
        """
        Calculate damage for a specific hit number, accounting for complex modifiers.

        Args:
            hit_number: The hit number (1-indexed)

        Returns:
            Damage for this specific hit
        """
        flat_mods, pct_mods = self.get_selected_modifier_values()
        base_dph = calculate_damage_per_hit(
            self.get_base_damage(),
            self.get_bonus_damage(),
            flat_mods,
            pct_mods
        )

        # Apply complex modifiers
        damage = base_dph
        for mod in self.selected_complex_modifiers:
            if mod.is_enabled():
                damage = mod.get_damage_for_hit(hit_number, damage)

        return damage

    def get_total_damage_for_hits(self, num_hits):
        """
        Calculate total damage for N hits, accounting for complex modifiers.

        Args:
            num_hits: Number of hits

        Returns:
            Total damage across all hits
        """
        flat_mods, pct_mods = self.get_selected_modifier_values()
        base_dph = calculate_damage_per_hit(
            self.get_base_damage(),
            self.get_bonus_damage(),
            flat_mods,
            pct_mods
        )

        # If no complex modifiers, simple multiplication
        if not self.selected_complex_modifiers:
            return base_dph * num_hits

        # Apply complex modifiers - they may change damage per hit
        total = 0
        current_dph = base_dph
        for hit in range(1, num_hits + 1):
            hit_damage = current_dph
            for mod in self.selected_complex_modifiers:
                if mod.is_enabled():
                    hit_damage = mod.get_damage_for_hit(hit, current_dph)
            total += hit_damage
        return total

    def is_enabled(self):
        """Check if row is enabled"""
        return self.enabled_var.get()

    def get_label(self):
        """Get the attack row label"""
        return self.label_var.get()

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
            return

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

    def get_results(self):
        """
        Get calculation results using selected modifiers.

        Returns:
            Tuple of (damage_per_hit, total_damage, attack_rate),
            or (0, 0, 0) if disabled
        """
        if not self.enabled_var.get():
            return (0, 0, 0)

        flat_mods, pct_mods = self.get_selected_modifier_values()
        dph = self.calculate_damage_per_hit(flat_mods, pct_mods)
        hits = self.get_hits()
        total = dph * hits
        attack_rate = self.get_attack_rate()

        return (dph, total, attack_rate)

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this row"""
        self.frame.destroy()
