"""TargetsSection class - orchestrates the Targets section"""

import tkinter as tk
from tkinter import ttk

from constants import COLUMN_COLORS
from target_row import TargetRow


class TargetsSection:
    """Orchestrates the Targets section"""

    def __init__(self, parent, get_variables, get_num_columns, on_columns_change_subscribe):
        """
        Initialize the Target section.

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
        self.target_rows = []
        self.target_row_counter = 0
        self.armor_mode = True  # True = armor input, False = reduction input

        # Store attack results from attack mode for calculations
        self.attack_results_per_column = []

        self._create_widgets()

        # Subscribe to column changes
        on_columns_change_subscribe(self._on_columns_changed)

    def _create_widgets(self):
        """Create all widgets for the Target section"""
        # Toggle button (always visible)
        self.toggle_frame = ttk.Frame(self.parent)
        self.toggle_button = ttk.Button(self.toggle_frame,
                                        text="▶ Show Targets Section",
                                        command=self.toggle_visibility)
        self.toggle_button.pack(side="left")

        # Main section frame (hidden by default)
        self.section_frame = ttk.Frame(self.parent)

        # Separator at top
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

        # === TARGETS ===
        target_header = ttk.Frame(self.section_frame)
        target_header.pack(fill="x", pady=(5, 5))
        ttk.Label(target_header, text="TARGETS",
                  font=('Arial', 10, 'bold')).pack(side="left")
        ttk.Button(target_header, text="+ Add",
                   command=self.add_target_row).pack(side="right", padx=5)

        # Armor/Reduction toggle
        armor_toggle_frame = ttk.Frame(self.section_frame)
        armor_toggle_frame.pack(fill="x", pady=(0, 5))
        self.armor_toggle_button = ttk.Button(armor_toggle_frame,
                                              text="Switch to Reduction",
                                              command=self.toggle_armor_mode,
                                              width=18)
        self.armor_toggle_button.pack(side="left", padx=5)
        self.armor_label_var = tk.StringVar(value="(Armor input mode)")
        ttk.Label(armor_toggle_frame, textvariable=self.armor_label_var,
                  foreground='#666', font=('Arial', 8)).pack(side="left", padx=5)

        self.targets_container = ttk.Frame(self.section_frame)
        self.targets_container.pack(fill="x", pady=5)

        # Bottom separator
        ttk.Separator(self.section_frame, orient='horizontal').pack(fill="x", pady=5)

    def _on_columns_changed(self, num_columns):
        """Handle column count changes"""
        for row in self.target_rows:
            row.update_columns(num_columns)
        self.calculate()

    def toggle_armor_mode(self):
        """Toggle between armor and reduction input mode"""
        self.armor_mode = not self.armor_mode

        if self.armor_mode:
            self.armor_toggle_button.config(text="Switch to Reduction")
            self.armor_label_var.set("(Armor input mode)")
        else:
            self.armor_toggle_button.config(text="Switch to Armor")
            self.armor_label_var.set("(Reduction % input mode)")

        # Update all target rows with new mode
        for row in self.target_rows:
            row.set_armor_mode(self.armor_mode)
        self.calculate()

    def toggle_visibility(self):
        """Toggle section visibility"""
        if self.visible:
            self.section_frame.pack_forget()
            self.toggle_button.config(text="▶ Show Targets Section")
            self.visible = False
        else:
            self.section_frame.pack(fill="x", pady=5, after=self.toggle_frame)
            self.toggle_button.config(text="▼ Hide Targets Section")
            self.visible = True
            # Add initial row if empty
            if not self.target_rows:
                self.add_target_row()

    def add_target_row(self):
        """Add a new target row"""
        self.target_row_counter += 1
        row = TargetRow(
            self.targets_container,
            self.target_row_counter,
            self.calculate,
            self.delete_target_row,
            num_columns=self.get_num_columns(),
            get_variables=self.get_variables,
            armor_mode=self.armor_mode
        )
        row.pack(fill="x", pady=2)
        self.target_rows.append(row)
        self.calculate()

    def delete_target_row(self, row):
        """Delete a target row"""
        if len(self.target_rows) > 1:
            self.target_rows.remove(row)
            row.destroy()
            self.calculate()

    def set_attack_results(self, attack_results_per_column):
        """
        Set the attack results from attack mode for target calculations.

        Args:
            attack_results_per_column: List of (damage_per_hit, total_damage, attack_rate) per column
        """
        self.attack_results_per_column = attack_results_per_column
        self.calculate()

    def calculate(self):
        """Calculate and update all target displays"""
        if not self.visible:
            return

        # Use stored attack results or default to zeros
        num_columns = self.get_num_columns()
        if not self.attack_results_per_column:
            attack_results = [(0, 0, 1.0)] * num_columns
        else:
            attack_results = self.attack_results_per_column

        for target in self.target_rows:
            target.update_display(attack_results)

    def pack_toggle(self, **kwargs):
        """Pack just the toggle button frame"""
        self.toggle_frame.pack(**kwargs)

    def clear(self):
        """Clear all target data"""
        for row in self.target_rows[:]:
            row.destroy()
        self.target_rows.clear()
        self.target_row_counter = 0
        self.attack_results_per_column = []
