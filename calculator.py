import tkinter as tk
from tkinter import ttk, messagebox

from constants import COLUMN_COLORS, MAX_COLUMNS
from utils import (
    safe_eval, armor_to_reduction, reduction_to_armor,
    has_operators, eval_armor_expression, eval_reduction_expression
)
from damage_row import DamageRow


class DotaCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Dota 2 Damage Calculator")
        self.root.geometry("900x950")

        style = ttk.Style()
        style.theme_use('clam')

        self.physical_rows = []
        self.magic_rows = []
        self.pure_rows = []
        self.physical_counter = 0
        self.magic_counter = 0
        self.pure_counter = 0

        self.pure_section_visible = False
        self.physical_armor_mode = True

        # Dynamic columns - store as lists
        self.num_columns = 1
        self.physical_vars = []
        self.physical_converted_vars = []
        self.physical_entries = []
        self.physical_converted_labels = []
        self.magic_vars = []
        self.magic_entries = []

        # Total display vars
        self.physical_total_vars = []
        self.physical_total_labels = []
        self.magic_total_vars = []
        self.magic_total_labels = []
        self.grand_total_vars = []
        self.grand_total_labels = []

        # HP and delta vars
        self.hp_vars = []
        self.hp_entries = []
        self.delta_vars = []
        self.delta_labels = []

        self.create_widgets()
        self._add_column_inputs()

        # Add initial rows
        self.add_physical_row()
        self.add_magic_row()
        self.add_pure_row()

    def create_widgets(self):
        # Main canvas and scrollbar for scrolling
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(main_frame, text="Dota 2 Damage Calculator",
                          font=('Arial', 16, 'bold'))
        title.pack(pady=(0, 20))

        # Instructions
        instructions = ttk.Label(main_frame,
                                 text="Enter damage values or expressions (e.g., '66*4' or '100+50'). Calculations update automatically.",
                                 font=('Arial', 9), foreground='#555')
        instructions.pack(pady=(0, 10))

        # Column controls
        column_control_frame = ttk.Frame(main_frame)
        column_control_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(column_control_frame, text="Comparison Columns:",
                  font=('Arial', 10, 'bold')).pack(side="left", padx=5)

        ttk.Button(column_control_frame, text="+ Add Column",
                   command=self.add_column).pack(side="left", padx=5)

        ttk.Button(column_control_frame, text="- Remove Column",
                   command=self.remove_column).pack(side="left", padx=5)

        self.column_count_var = tk.StringVar(value="(1 column)")
        ttk.Label(column_control_frame, textvariable=self.column_count_var,
                  foreground='#666').pack(side="left", padx=10)

        # Physical Damage Section
        physical_header = ttk.Frame(main_frame)
        physical_header.pack(fill="x", pady=(10, 5))

        ttk.Label(physical_header, text="Physical Damage",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Button(physical_header, text="+ Add Row",
                   command=self.add_physical_row).pack(side="right", padx=5)

        # Physical reduction/armor toggle section
        physical_toggle_frame = ttk.Frame(main_frame)
        physical_toggle_frame.pack(fill="x", pady=5)

        self.physical_toggle_button = ttk.Button(physical_toggle_frame,
                                                 text="Switch to Reduction",
                                                 command=self.toggle_armor_mode,
                                                 width=15)
        self.physical_toggle_button.pack(side="left", padx=5)

        self.physical_label_var = tk.StringVar(value="Armor:")
        ttk.Label(physical_toggle_frame, textvariable=self.physical_label_var).pack(side="left", padx=5)

        # Container for physical input entries (dynamic)
        self.physical_inputs_frame = ttk.Frame(physical_toggle_frame)
        self.physical_inputs_frame.pack(side="left", fill="x")

        # Physical rows container
        self.physical_container = ttk.Frame(main_frame)
        self.physical_container.pack(fill="x", pady=5)

        # Physical total frame
        self.physical_total_frame = ttk.Frame(main_frame)
        self.physical_total_frame.pack(fill="x", pady=(5, 10))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill="x", pady=15)

        # Magic Damage Section
        magic_header = ttk.Frame(main_frame)
        magic_header.pack(fill="x", pady=(10, 5))

        ttk.Label(magic_header, text="Magic Damage",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Button(magic_header, text="+ Add Row",
                   command=self.add_magic_row).pack(side="right", padx=5)

        # Magic reduction frame
        magic_reduction_frame = ttk.Frame(main_frame)
        magic_reduction_frame.pack(fill="x", pady=5)

        ttk.Label(magic_reduction_frame, text="Magic Reduction (%):").pack(side="left", padx=5)

        # Container for magic input entries (dynamic)
        self.magic_inputs_frame = ttk.Frame(magic_reduction_frame)
        self.magic_inputs_frame.pack(side="left", fill="x")

        # Magic rows container
        self.magic_container = ttk.Frame(main_frame)
        self.magic_container.pack(fill="x", pady=5)

        # Magic total frame
        self.magic_total_frame = ttk.Frame(main_frame)
        self.magic_total_frame.pack(fill="x", pady=(5, 10))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill="x", pady=15)

        # Pure Damage Toggle Button
        pure_toggle_frame = ttk.Frame(main_frame)
        pure_toggle_frame.pack(fill="x", pady=(5, 5))

        self.pure_toggle_button = ttk.Button(pure_toggle_frame,
                                             text="▶ Show Pure Damage Section",
                                             command=self.toggle_pure_section)
        self.pure_toggle_button.pack(side="left")

        # Pure Damage Section (collapsible)
        self.pure_section_frame = ttk.Frame(main_frame)

        pure_header = ttk.Frame(self.pure_section_frame)
        pure_header.pack(fill="x", pady=(10, 5))

        ttk.Label(pure_header, text="Pure Damage",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Label(pure_header, text="(Ignores all resistances, same for all columns)",
                  font=('Arial', 9, 'italic'), foreground='#666').pack(side="left", padx=(10, 0))

        ttk.Button(pure_header, text="+ Add Row",
                   command=self.add_pure_row).pack(side="right", padx=5)

        self.pure_container = ttk.Frame(self.pure_section_frame)
        self.pure_container.pack(fill="x", pady=5)

        pure_total_frame = ttk.Frame(self.pure_section_frame)
        pure_total_frame.pack(fill="x", pady=(5, 10))
        self.pure_total_var = tk.StringVar(value="Pure: 0.00")
        ttk.Label(pure_total_frame, textvariable=self.pure_total_var,
                  font=('Arial', 10, 'bold'), foreground='#e69500').pack(side="left", padx=5)

        self.pure_separator = ttk.Separator(main_frame, orient='horizontal')

        # Grand Total Section
        self.total_separator = ttk.Separator(main_frame, orient='horizontal')
        self.total_separator.pack(fill="x", pady=15)

        self.total_frame = ttk.Frame(main_frame, relief='solid', borderwidth=2, padding="10")
        self.total_frame.pack(fill="x", pady=10)

        self.grand_totals_container = ttk.Frame(self.total_frame)
        self.grand_totals_container.pack()

        # HP input row
        hp_row = ttk.Frame(self.total_frame)
        hp_row.pack(fill="x", pady=(10, 0))
        ttk.Label(hp_row, text="HP:", font=('Arial', 10)).pack(side="left", padx=5)
        self.hp_inputs_frame = ttk.Frame(hp_row)
        self.hp_inputs_frame.pack(side="left")

        # Remaining HP (delta) display row
        delta_row = ttk.Frame(self.total_frame)
        delta_row.pack(fill="x", pady=(5, 0))
        ttk.Label(delta_row, text="Remaining:", font=('Arial', 10)).pack(side="left", padx=5)
        self.delta_display_frame = ttk.Frame(delta_row)
        self.delta_display_frame.pack(side="left")

        # Clear button
        ttk.Button(main_frame, text="Clear All",
                   command=self.clear_all).pack(pady=10)

    def _add_column_inputs(self):
        """Add input fields for a new column"""
        col_idx = len(self.physical_vars)
        color = COLUMN_COLORS[col_idx % len(COLUMN_COLORS)]

        # Physical input
        if col_idx > 0:
            ttk.Label(self.physical_inputs_frame, text="vs", foreground='#666').pack(side="left", padx=3)

        phys_var = tk.StringVar(value="0")
        phys_var.trace('w', lambda *args: self.calculate_all())
        phys_entry = ttk.Entry(self.physical_inputs_frame, textvariable=phys_var, width=6)
        phys_entry.pack(side="left", padx=2)
        self.physical_vars.append(phys_var)
        self.physical_entries.append(phys_entry)

        # Physical converted display
        conv_var = tk.StringVar(value="")
        conv_label = ttk.Label(self.physical_inputs_frame, textvariable=conv_var,
                               foreground=color, font=('Arial', 8))
        conv_label.pack(side="left", padx=(0, 5))
        self.physical_converted_vars.append(conv_var)
        self.physical_converted_labels.append(conv_label)

        # Magic input
        if col_idx > 0:
            ttk.Label(self.magic_inputs_frame, text="vs", foreground='#666').pack(side="left", padx=3)

        magic_var = tk.StringVar(value="0")
        magic_var.trace('w', lambda *args: self.calculate_all())
        magic_entry = ttk.Entry(self.magic_inputs_frame, textvariable=magic_var, width=6)
        magic_entry.pack(side="left", padx=2)
        self.magic_vars.append(magic_var)
        self.magic_entries.append(magic_entry)

        # Physical total label
        phys_total_var = tk.StringVar(value="0.00")
        phys_total_label = ttk.Label(self.physical_total_frame, textvariable=phys_total_var,
                                     font=('Arial', 10, 'bold'), foreground=color)
        phys_total_label.pack(side="left", padx=5)
        self.physical_total_vars.append(phys_total_var)
        self.physical_total_labels.append(phys_total_label)

        # Magic total label
        magic_total_var = tk.StringVar(value="0.00")
        magic_total_label = ttk.Label(self.magic_total_frame, textvariable=magic_total_var,
                                      font=('Arial', 10, 'bold'), foreground=color)
        magic_total_label.pack(side="left", padx=5)
        self.magic_total_vars.append(magic_total_var)
        self.magic_total_labels.append(magic_total_label)

        # Grand total label
        grand_var = tk.StringVar(value="TOTAL: 0.00")
        grand_label = ttk.Label(self.grand_totals_container, textvariable=grand_var,
                                font=('Arial', 12, 'bold'), foreground=color)
        grand_label.pack(side="left", padx=10)
        self.grand_total_vars.append(grand_var)
        self.grand_total_labels.append(grand_label)

        # HP input
        if col_idx > 0:
            ttk.Label(self.hp_inputs_frame, text="vs", foreground='#666').pack(side="left", padx=3)

        hp_var = tk.StringVar(value="")
        hp_var.trace('w', lambda *args: self.calculate_all())
        hp_entry = ttk.Entry(self.hp_inputs_frame, textvariable=hp_var, width=7)
        hp_entry.pack(side="left", padx=2)
        self.hp_vars.append(hp_var)
        self.hp_entries.append(hp_entry)

        # Delta (remaining HP) label
        delta_var = tk.StringVar(value="")
        delta_label = ttk.Label(self.delta_display_frame, textvariable=delta_var,
                                font=('Arial', 11, 'bold'), foreground=color, width=12)
        delta_label.pack(side="left", padx=5)
        self.delta_vars.append(delta_var)
        self.delta_labels.append(delta_label)

    def _remove_column_inputs(self):
        """Remove input fields for last column"""
        if len(self.physical_vars) <= 1:
            return

        # Remove physical
        self.physical_vars.pop()
        entry = self.physical_entries.pop()
        entry.destroy()
        self.physical_converted_vars.pop()
        conv_label = self.physical_converted_labels.pop()
        conv_label.destroy()

        # Remove "vs" label if exists
        children = self.physical_inputs_frame.winfo_children()
        if children and isinstance(children[-1], ttk.Label):
            children[-1].destroy()

        # Remove magic
        self.magic_vars.pop()
        magic_entry = self.magic_entries.pop()
        magic_entry.destroy()

        children = self.magic_inputs_frame.winfo_children()
        if children and isinstance(children[-1], ttk.Label):
            children[-1].destroy()

        # Remove totals
        self.physical_total_vars.pop()
        self.physical_total_labels.pop().destroy()

        self.magic_total_vars.pop()
        self.magic_total_labels.pop().destroy()

        self.grand_total_vars.pop()
        self.grand_total_labels.pop().destroy()

        # Remove HP input
        self.hp_vars.pop()
        self.hp_entries.pop().destroy()

        children = self.hp_inputs_frame.winfo_children()
        if children and isinstance(children[-1], ttk.Label):
            children[-1].destroy()

        # Remove delta label
        self.delta_vars.pop()
        self.delta_labels.pop().destroy()

    def add_column(self):
        """Add a new comparison column"""
        if self.num_columns >= MAX_COLUMNS:
            messagebox.showinfo("Info", f"Maximum {MAX_COLUMNS} columns allowed")
            return

        self.num_columns += 1
        self._add_column_inputs()
        self._update_all_rows_columns()
        self.column_count_var.set(f"({self.num_columns} column{'s' if self.num_columns > 1 else ''})")
        self.calculate_all()

    def remove_column(self):
        """Remove the last comparison column"""
        if self.num_columns <= 1:
            messagebox.showinfo("Info", "Must keep at least one column")
            return

        self.num_columns -= 1
        self._remove_column_inputs()
        self._update_all_rows_columns()
        self.column_count_var.set(f"({self.num_columns} column{'s' if self.num_columns > 1 else ''})")
        self.calculate_all()

    def _update_all_rows_columns(self):
        """Update all rows to match current column count"""
        for row in self.physical_rows:
            row.update_columns(self.num_columns)
        for row in self.magic_rows:
            row.update_columns(self.num_columns)
        # Pure rows stay at 1 column

    def toggle_pure_section(self):
        """Toggle the visibility of the pure damage section"""
        if self.pure_section_visible:
            self.pure_section_frame.pack_forget()
            self.pure_separator.pack_forget()
            self.pure_toggle_button.config(text="▶ Show Pure Damage Section")
            self.pure_section_visible = False
        else:
            self.pure_section_frame.pack(fill="x", pady=5, before=self.total_separator)
            self.pure_separator.pack(fill="x", pady=15, before=self.total_separator)
            self.pure_toggle_button.config(text="▼ Hide Pure Damage Section")
            self.pure_section_visible = True

    def toggle_armor_mode(self):
        """Toggle between Armor and Physical Reduction mode"""
        self.physical_armor_mode = not self.physical_armor_mode

        if self.physical_armor_mode:
            self.physical_label_var.set("Armor:")
            self.physical_toggle_button.config(text="Switch to Reduction")
            # Convert all reduction values to armor
            for var in self.physical_vars:
                reduction = eval_reduction_expression(var.get() or "0")
                armor = reduction_to_armor(reduction)
                var.set(f"{armor:.1f}")
        else:
            self.physical_label_var.set("Reduction (%):")
            self.physical_toggle_button.config(text="Switch to Armor")
            # Convert all armor values to reduction
            for var in self.physical_vars:
                reduction, _ = eval_armor_expression(var.get() or "0")
                var.set(f"{reduction:.1f}")

        self.update_physical_display()

    def update_physical_display(self):
        """Update the physical reduction display based on current mode"""
        try:
            for i, var in enumerate(self.physical_vars):
                expr_str = var.get() or "0"
                if self.physical_armor_mode:
                    reduction, armor = eval_armor_expression(expr_str)
                    reduction = max(0, min(100, reduction))
                    if armor is not None and has_operators(expr_str):
                        self.physical_converted_vars[i].set(f"={armor:.0f} ({reduction:.0f}%)")
                    else:
                        self.physical_converted_vars[i].set(f"({reduction:.0f}%)")
                else:
                    reduction = eval_reduction_expression(expr_str)
                    if has_operators(expr_str):
                        self.physical_converted_vars[i].set(f"={reduction:.1f}%")
                    else:
                        self.physical_converted_vars[i].set("")
        except (ValueError, ZeroDivisionError):
            for conv_var in self.physical_converted_vars:
                conv_var.set("")

    def add_physical_row(self):
        """Add a new physical damage row"""
        self.physical_counter += 1
        row = DamageRow(self.physical_container, self.physical_counter, "Physical",
                        self.calculate_all, self.delete_physical_row,
                        num_columns=self.num_columns, is_pure=False)
        row.pack(pady=2, fill="x")
        self.physical_rows.append(row)
        self.calculate_all()

    def add_magic_row(self):
        """Add a new magic damage row"""
        self.magic_counter += 1
        row = DamageRow(self.magic_container, self.magic_counter, "Magic",
                        self.calculate_all, self.delete_magic_row,
                        num_columns=self.num_columns, is_pure=False)
        row.pack(pady=2, fill="x")
        self.magic_rows.append(row)
        self.calculate_all()

    def add_pure_row(self):
        """Add a new pure damage row"""
        self.pure_counter += 1
        row = DamageRow(self.pure_container, self.pure_counter, "Pure",
                        self.calculate_all, self.delete_pure_row,
                        num_columns=1, is_pure=True)
        row.pack(pady=2, fill="x")
        self.pure_rows.append(row)
        self.calculate_all()

    def delete_physical_row(self, row):
        """Delete a physical damage row"""
        if len(self.physical_rows) > 1:
            self.physical_rows.remove(row)
            row.destroy()
            self.calculate_all()
        else:
            messagebox.showinfo("Info", "Must keep at least one physical damage row")

    def delete_magic_row(self, row):
        """Delete a magic damage row"""
        if len(self.magic_rows) > 1:
            self.magic_rows.remove(row)
            row.destroy()
            self.calculate_all()
        else:
            messagebox.showinfo("Info", "Must keep at least one magic damage row")

    def delete_pure_row(self, row):
        """Delete a pure damage row"""
        if len(self.pure_rows) > 1:
            self.pure_rows.remove(row)
            row.destroy()
            self.calculate_all()
        else:
            messagebox.showinfo("Info", "Must keep at least one pure damage row")

    def calculate_all(self):
        """Calculate all damage totals automatically"""
        try:
            # Get physical reductions for all columns
            physical_reductions = []
            for var in self.physical_vars:
                expr_str = var.get() or "0"
                if self.physical_armor_mode:
                    reduction, _ = eval_armor_expression(expr_str)
                else:
                    reduction = eval_reduction_expression(expr_str)
                reduction = max(0, min(100, reduction))
                physical_reductions.append(reduction)

            # Get magic reductions for all columns
            magic_reductions = []
            for var in self.magic_vars:
                expr_str = var.get() or "0"
                reduction = eval_reduction_expression(expr_str)
                reduction = max(0, min(100, reduction))
                magic_reductions.append(reduction)

            # Calculate physical totals
            physical_totals = [0] * self.num_columns
            for row in self.physical_rows:
                results = row.get_damage(physical_reductions)
                for i, r in enumerate(results):
                    if i < self.num_columns:
                        physical_totals[i] += r

            for i, total in enumerate(physical_totals):
                prefix = "Phys: " if i == 0 else "vs "
                self.physical_total_vars[i].set(f"{prefix}{total:.2f}")

            # Calculate magic totals
            magic_totals = [0] * self.num_columns
            for row in self.magic_rows:
                results = row.get_damage(magic_reductions)
                for i, r in enumerate(results):
                    if i < self.num_columns:
                        magic_totals[i] += r

            for i, total in enumerate(magic_totals):
                prefix = "Magic: " if i == 0 else "vs "
                self.magic_total_vars[i].set(f"{prefix}{total:.2f}")

            # Calculate pure total (same for all columns)
            pure_total = 0
            for row in self.pure_rows:
                results = row.get_damage([0])
                pure_total += results[0]
            self.pure_total_var.set(f"Pure: {pure_total:.2f}")

            # Calculate grand totals and delta (remaining HP)
            for i in range(self.num_columns):
                grand = physical_totals[i] + magic_totals[i] + pure_total
                prefix = "TOTAL: " if i == 0 else "vs "
                self.grand_total_vars[i].set(f"{prefix}{grand:.2f}")

                # Calculate remaining HP if HP is specified
                if i < len(self.hp_vars):
                    hp_str = self.hp_vars[i].get().strip()
                    if hp_str:
                        hp = safe_eval(hp_str)
                        if hp is not None:
                            remaining = hp - grand
                            color = COLUMN_COLORS[i % len(COLUMN_COLORS)]
                            if remaining < 0:
                                self.delta_labels[i].configure(foreground='#c62828')
                                self.delta_vars[i].set(f"{remaining:.0f} (dead)")
                            else:
                                self.delta_labels[i].configure(foreground=color)
                                self.delta_vars[i].set(f"{remaining:.0f}")
                        else:
                            self.delta_vars[i].set("")
                    else:
                        self.delta_vars[i].set("")

            self.update_physical_display()

        except ValueError:
            pass

    def clear_all(self):
        """Clear all rows and reset"""
        for row in self.physical_rows[:]:
            row.destroy()
        self.physical_rows.clear()
        self.physical_counter = 0

        for row in self.magic_rows[:]:
            row.destroy()
        self.magic_rows.clear()
        self.magic_counter = 0

        for row in self.pure_rows[:]:
            row.destroy()
        self.pure_rows.clear()
        self.pure_counter = 0

        # Reset all reduction values
        for var in self.physical_vars:
            var.set("0")
        for var in self.magic_vars:
            var.set("0")
        for var in self.hp_vars:
            var.set("")

        self.add_physical_row()
        self.add_magic_row()
        self.add_pure_row()
