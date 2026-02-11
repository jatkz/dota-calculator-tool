"""SpellRow class - spell configuration with damage, instances, cooldown, etc."""

import tkinter as tk
from tkinter import ttk

from utils import safe_eval, is_expression, armor_to_reduction
from spell_calculations import (
    calculate_spell_damage,
    apply_magic_resistance,
    apply_physical_resistance,
    calculate_spell_dps,
    calculate_mana_efficiency
)


class SpellRow:
    """Represents a single spell configuration row"""

    DAMAGE_TYPES = ["Magic", "Physical", "Pure"]

    def __init__(self, parent, row_num, on_change_callback, on_delete_callback,
                 num_columns=1, get_variables=None, get_modifiers=None, get_targets=None):
        """
        Initialize a spell row.

        Args:
            parent: Parent widget
            row_num: Row number for labeling
            on_change_callback: Called when values change
            on_delete_callback: Called when delete button is clicked
            num_columns: Number of comparison columns
            get_variables: Callback to get current variables dict
            get_modifiers: Callback to get modifiers list
            get_targets: Callback to get available targets list
        """
        self.parent = parent
        self.row_num = row_num
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.num_columns = num_columns
        self.get_variables = get_variables
        self.get_modifiers = get_modifiers
        self.get_targets = get_targets
        self.selected_targets = []
        self.selected_modifiers = []

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
        self.label_var = tk.StringVar(value=f"Spell {row_num}")
        label_entry = ttk.Entry(input_frame, textvariable=self.label_var, width=10)
        label_entry.pack(side="left", padx=2)

        # Damage
        ttk.Label(input_frame, text="Dmg:").pack(side="left", padx=(5, 0))
        self.damage_var = tk.StringVar(value="0")
        self.damage_var.trace('w', lambda *args: self.on_change())
        damage_entry = ttk.Entry(input_frame, textvariable=self.damage_var, width=6)
        damage_entry.pack(side="left", padx=2)

        # Instances
        ttk.Label(input_frame, text="Inst:").pack(side="left", padx=(5, 0))
        self.instances_var = tk.StringVar(value="1")
        self.instances_var.trace('w', lambda *args: self.on_change())
        instances_entry = ttk.Entry(input_frame, textvariable=self.instances_var, width=3)
        instances_entry.pack(side="left", padx=2)

        # Damage type dropdown
        ttk.Label(input_frame, text="Type:").pack(side="left", padx=(5, 0))
        self.damage_type_var = tk.StringVar(value="Magic")
        self.damage_type_var.trace('w', lambda *args: self.on_change())
        damage_type_combo = ttk.Combobox(input_frame, textvariable=self.damage_type_var,
                                         state="readonly", width=7, values=self.DAMAGE_TYPES)
        damage_type_combo.pack(side="left", padx=2)

        # Cast time
        ttk.Label(input_frame, text="Cast:").pack(side="left", padx=(5, 0))
        self.cast_var = tk.StringVar(value="0")
        self.cast_var.trace('w', lambda *args: self.on_change())
        cast_entry = ttk.Entry(input_frame, textvariable=self.cast_var, width=4)
        cast_entry.pack(side="left", padx=2)
        ttk.Label(input_frame, text="s").pack(side="left")

        # Delete button (pack first so it's on right)
        delete_btn = ttk.Button(input_frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="right", padx=5)

        # Evaluated damage display
        self.eval_var = tk.StringVar(value="")
        eval_label = ttk.Label(input_frame, textvariable=self.eval_var,
                               foreground='#666', font=('Arial', 8))
        eval_label.pack(side="right", padx=5)

        # Row 1: Secondary inputs (CD, Mana, Duration)
        secondary_frame = ttk.Frame(self.frame)
        secondary_frame.pack(fill="x", pady=(0, 2), padx=(25, 0))

        # Cooldown
        ttk.Label(secondary_frame, text="CD:").pack(side="left")
        self.cooldown_var = tk.StringVar(value="0")
        self.cooldown_var.trace('w', lambda *args: self.on_change())
        cooldown_entry = ttk.Entry(secondary_frame, textvariable=self.cooldown_var, width=4)
        cooldown_entry.pack(side="left", padx=2)
        ttk.Label(secondary_frame, text="s").pack(side="left")

        # Mana cost
        ttk.Label(secondary_frame, text="Mana:").pack(side="left", padx=(10, 0))
        self.mana_var = tk.StringVar(value="0")
        self.mana_var.trace('w', lambda *args: self.on_change())
        mana_entry = ttk.Entry(secondary_frame, textvariable=self.mana_var, width=5)
        mana_entry.pack(side="left", padx=2)

        # Duration
        ttk.Label(secondary_frame, text="Dur:").pack(side="left", padx=(10, 0))
        self.duration_var = tk.StringVar(value="0")
        self.duration_var.trace('w', lambda *args: self.on_change())
        duration_entry = ttk.Entry(secondary_frame, textvariable=self.duration_var, width=4)
        duration_entry.pack(side="left", padx=2)
        ttk.Label(secondary_frame, text="s").pack(side="left")

        # Stun duration (display only)
        ttk.Label(secondary_frame, text="Stun:").pack(side="left", padx=(10, 0))
        self.stun_var = tk.StringVar(value="0")
        stun_entry = ttk.Entry(secondary_frame, textvariable=self.stun_var, width=4)
        stun_entry.pack(side="left", padx=2)
        ttk.Label(secondary_frame, text="s").pack(side="left")

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
                                           state="readonly", width=14)
        self.modifier_combo['values'] = []
        self.modifier_combo.pack(side="left", padx=2)

        # Add modifier button
        self.add_modifier_btn = ttk.Button(selection_frame, text="+", width=2,
                                           command=self._add_selected_modifier)
        self.add_modifier_btn.pack(side="left")

        # Row for displaying selected targets
        self.targets_frame = ttk.Frame(self.frame)
        self.targets_frame.pack(fill="x", pady=(2, 0), padx=(25, 0))
        self.target_widgets = []

        # Row for displaying selected modifiers
        self.modifiers_frame = ttk.Frame(self.frame)
        self.modifiers_frame.pack(fill="x", pady=(2, 2), padx=(25, 0))
        self.modifier_widgets = []

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

        if self.get_targets:
            for target in self.get_targets():
                if target.label_var.get() == selected_label:
                    if target not in self.selected_targets:
                        self.selected_targets.append(target)
                        self._update_targets_display()
                        self.update_target_options()
                        self.on_change()
                    break

    def _remove_target(self, target):
        """Remove a specific target from the selection"""
        if target in self.selected_targets:
            self.selected_targets.remove(target)
            self._update_targets_display()
            self.update_target_options()
            self.on_change()

    def _update_targets_display(self):
        """Update the display of selected targets"""
        for _, frame in self.target_widgets:
            frame.destroy()
        self.target_widgets.clear()

        for target in self.selected_targets:
            target_frame = ttk.Frame(self.targets_frame)
            target_frame.pack(side="left", padx=2)

            label = target.label_var.get()
            ttk.Label(target_frame, text=label, font=('Arial', 8),
                      foreground='#333').pack(side="left")

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
            if mod not in self.selected_modifiers:
                label = mod.get_label()
                options.append(label)

        self.modifier_combo['values'] = options
        if options:
            self.modifier_var.set(options[0])
        else:
            self.modifier_var.set("")

        available_modifiers = self.get_modifiers() if self.get_modifiers else []
        self.selected_modifiers = [m for m in self.selected_modifiers if m in available_modifiers]
        self._update_modifiers_display()

    def _add_selected_modifier(self):
        """Add the currently selected modifier from dropdown"""
        selected_label = self.modifier_var.get()
        if not selected_label:
            return

        if self.get_modifiers:
            for mod in self.get_modifiers():
                if mod.get_label() == selected_label:
                    if mod not in self.selected_modifiers:
                        self.selected_modifiers.append(mod)
                        self._update_modifiers_display()
                        self.update_modifier_options()
                        self.on_change()
                    break

    def _remove_modifier(self, mod):
        """Remove a specific modifier from the selection"""
        if mod in self.selected_modifiers:
            self.selected_modifiers.remove(mod)
            self._update_modifiers_display()
            self.update_modifier_options()
            self.on_change()

    def _update_modifiers_display(self):
        """Update the display of selected modifiers"""
        for _, frame in self.modifier_widgets:
            frame.destroy()
        self.modifier_widgets.clear()

        for mod in self.selected_modifiers:
            mod_frame = ttk.Frame(self.modifiers_frame)
            mod_frame.pack(side="left", padx=2)

            label = mod.get_label()
            ttk.Label(mod_frame, text=label, font=('Arial', 8, 'bold'),
                      foreground='#8B4513').pack(side="left")

            remove_btn = ttk.Button(mod_frame, text="✕", width=2,
                                    command=lambda m=mod: self._remove_modifier(m))
            remove_btn.pack(side="left", padx=1)

            self.modifier_widgets.append((mod, mod_frame))

    def get_selected_modifiers(self):
        """Get list of currently selected modifiers"""
        return self.selected_modifiers

    def is_enabled(self):
        """Check if row is enabled"""
        return self.enabled_var.get()

    def get_label(self):
        """Get the spell row label"""
        return self.label_var.get()

    def get_base_damage(self):
        """Get evaluated base damage value"""
        variables = self.get_variables() if self.get_variables else None
        return safe_eval(self.damage_var.get(), variables) or 0

    def get_instances(self):
        """Get number of damage instances"""
        variables = self.get_variables() if self.get_variables else None
        instances = safe_eval(self.instances_var.get(), variables)
        return max(1, int(instances)) if instances is not None else 1

    def get_damage_type(self):
        """Get damage type (Magic, Physical, Pure)"""
        return self.damage_type_var.get()

    def get_cast_time(self):
        """Get cast time in seconds"""
        variables = self.get_variables() if self.get_variables else None
        cast = safe_eval(self.cast_var.get(), variables)
        return cast if cast is not None and cast >= 0 else 0

    def get_cooldown(self):
        """Get cooldown in seconds"""
        variables = self.get_variables() if self.get_variables else None
        cd = safe_eval(self.cooldown_var.get(), variables)
        return cd if cd is not None and cd >= 0 else 0

    def get_mana_cost(self):
        """Get mana cost"""
        variables = self.get_variables() if self.get_variables else None
        mana = safe_eval(self.mana_var.get(), variables)
        return mana if mana is not None and mana >= 0 else 0

    def get_duration(self):
        """Get spell duration in seconds"""
        variables = self.get_variables() if self.get_variables else None
        dur = safe_eval(self.duration_var.get(), variables)
        return dur if dur is not None and dur >= 0 else 0

    def get_stun_duration(self):
        """Get stun duration in seconds (display only, no calculation effect)"""
        variables = self.get_variables() if self.get_variables else None
        stun = safe_eval(self.stun_var.get(), variables)
        return stun if stun is not None and stun >= 0 else 0

    def get_total_damage(self):
        """
        Get total damage with modifiers applied (before target resistance).

        Returns:
            Total spell damage after modifiers
        """
        base_damage = self.get_base_damage()
        instances = self.get_instances()

        # Apply modifiers
        damage = base_damage
        for mod in self.selected_modifiers:
            if mod.is_enabled():
                # Use modifier's damage calculation (treating spell damage like a hit)
                damage = mod.apply_damage_for_hit(1, damage, base_damage)

        return damage * instances

    def get_damage_against_target(self, target):
        """
        Calculate damage against a specific target.

        Args:
            target: TargetRow object

        Returns:
            Damage after applying target's resistances
        """
        total_damage = self.get_total_damage()
        damage_type = self.get_damage_type()

        if damage_type == "Magic":
            return apply_magic_resistance(total_damage, target.get_magic_resistance())
        elif damage_type == "Physical":
            return apply_physical_resistance(total_damage, target.get_armor())
        else:  # Pure
            return total_damage

    def get_dps_against_target(self, target):
        """
        Calculate DPS against a specific target.

        Args:
            target: TargetRow object

        Returns:
            DPS over cooldown cycle
        """
        damage = self.get_damage_against_target(target)
        cast_time = self.get_cast_time()
        cooldown = self.get_cooldown()
        return calculate_spell_dps(damage, cast_time, cooldown)

    def get_mana_efficiency_against_target(self, target):
        """
        Calculate mana efficiency against a specific target.

        Args:
            target: TargetRow object

        Returns:
            Damage per mana point
        """
        damage = self.get_damage_against_target(target)
        mana_cost = self.get_mana_cost()
        return calculate_mana_efficiency(damage, mana_cost)

    def update_display(self):
        """Update the display with calculated values"""
        if not self.enabled_var.get():
            self.eval_var.set("(disabled)")
            return

        # Calculate total damage
        base = self.get_base_damage()
        instances = self.get_instances()
        total = self.get_total_damage()

        # Show evaluated expression if input contains operators
        damage_str = self.damage_var.get()
        if is_expression(damage_str) or instances > 1 or self.selected_modifiers:
            self.eval_var.set(f"= {total:.0f} total")
        else:
            self.eval_var.set("")

    def get_results(self):
        """
        Get calculation results.

        Returns:
            Tuple of (total_damage, damage_type, cast_time, cooldown, mana),
            or zeros if disabled
        """
        if not self.enabled_var.get():
            return (0, "Magic", 0, 0, 0)

        return (
            self.get_total_damage(),
            self.get_damage_type(),
            self.get_cast_time(),
            self.get_cooldown(),
            self.get_mana_cost()
        )

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this row"""
        self.frame.destroy()
