import tkinter as tk
from tkinter import ttk, messagebox

from constants import COLUMN_COLORS, MAX_COLUMNS
from utils import (
    safe_eval, armor_to_reduction, reduction_to_armor,
    has_operators, eval_armor_expression, eval_reduction_expression
)
from damage_row import DamageRow
from targets_section import TargetsSection
from attack_mode import AttackModeSection
from spells_section import SpellsSection
from hero_lab_section import HeroLabSection
from item_workbench_section import ItemWorkbenchSection
from spell_workbench_section import SpellWorkbenchSection


class DotaCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Dota 2 Damage Calculator")
        self.root.geometry("1000x1050")

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

        # Variables
        self.variable_rows = []  # List of variable row widgets

        # Column change subscribers
        self.column_change_subscribers = []

        self.create_widgets()
        self._add_column_inputs()

        # Add initial rows
        self.add_physical_row()
        self.add_magic_row()
        self.add_pure_row()

    def _bind_mousewheel(self, canvas):
        """Bind mouse wheel events for scrolling"""
        def _on_mousewheel(event):
            # Linux uses Button-4 and Button-5
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                # Windows/Mac uses event.delta
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind for Linux
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)
        # Bind for Windows/Mac
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _on_targets_changed(self):
        """Called when target values or list changes - update attack mode and spells"""
        self.attack_mode.update_target_options()
        self.attack_mode.calculate()
        self.spells_section.update_target_options()
        self.spells_section.calculate()

    def create_widgets(self):
        # Main canvas and scrollbar for scrolling
        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        scrollable_frame = ttk.Frame(self.main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

        # Bind mouse wheel scrolling
        self._bind_mousewheel(self.main_canvas)

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

        # Variables Section (always visible)
        variables_header = ttk.Frame(main_frame)
        variables_header.pack(fill="x", pady=(10, 5))

        ttk.Label(variables_header, text="Variables",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Button(variables_header, text="+ Add Variable",
                   command=self.add_variable).pack(side="right", padx=5)

        self.variables_container = ttk.Frame(main_frame)
        self.variables_container.pack(fill="x", pady=5)

        # Separator after variables
        ttk.Separator(main_frame, orient='horizontal').pack(fill="x", pady=10)

        # ============ SIMPLE GRID TOGGLE ============
        self.simple_grid_visible = False
        self.simple_grid_toggle_frame = ttk.Frame(main_frame)
        self.simple_grid_toggle_frame.pack(fill="x", pady=(5, 5))
        self.simple_grid_toggle_btn = ttk.Button(
            self.simple_grid_toggle_frame,
            text="▶ Show Simple Grid",
            command=self.toggle_simple_grid
        )
        self.simple_grid_toggle_btn.pack(side="left")

        # Container for Simple Grid content
        self.simple_grid_container = ttk.Frame(main_frame)

        # Column controls (inside simple grid)
        column_control_frame = ttk.Frame(self.simple_grid_container)
        column_control_frame.pack(fill="x", pady=(10, 15))

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
        physical_header = ttk.Frame(self.simple_grid_container)
        physical_header.pack(fill="x", pady=(10, 5))

        ttk.Label(physical_header, text="Physical Damage",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Button(physical_header, text="+ Add Row",
                   command=self.add_physical_row).pack(side="right", padx=5)

        # Physical reduction/armor toggle section
        physical_toggle_frame = ttk.Frame(self.simple_grid_container)
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
        self.physical_container = ttk.Frame(self.simple_grid_container)
        self.physical_container.pack(fill="x", pady=5)

        # Physical total frame
        self.physical_total_frame = ttk.Frame(self.simple_grid_container)
        self.physical_total_frame.pack(fill="x", pady=(5, 10))

        # Separator
        ttk.Separator(self.simple_grid_container, orient='horizontal').pack(fill="x", pady=15)

        # Magic Damage Section
        magic_header = ttk.Frame(self.simple_grid_container)
        magic_header.pack(fill="x", pady=(10, 5))

        ttk.Label(magic_header, text="Magic Damage",
                  font=('Arial', 12, 'bold')).pack(side="left")

        ttk.Button(magic_header, text="+ Add Row",
                   command=self.add_magic_row).pack(side="right", padx=5)

        # Magic reduction frame
        magic_reduction_frame = ttk.Frame(self.simple_grid_container)
        magic_reduction_frame.pack(fill="x", pady=5)

        ttk.Label(magic_reduction_frame, text="Magic Reduction (%):").pack(side="left", padx=5)

        # Container for magic input entries (dynamic)
        self.magic_inputs_frame = ttk.Frame(magic_reduction_frame)
        self.magic_inputs_frame.pack(side="left", fill="x")

        # Magic rows container
        self.magic_container = ttk.Frame(self.simple_grid_container)
        self.magic_container.pack(fill="x", pady=5)

        # Magic total frame
        self.magic_total_frame = ttk.Frame(self.simple_grid_container)
        self.magic_total_frame.pack(fill="x", pady=(5, 10))

        # Separator
        ttk.Separator(self.simple_grid_container, orient='horizontal').pack(fill="x", pady=15)

        # Pure Damage Toggle Button
        pure_toggle_frame = ttk.Frame(self.simple_grid_container)
        pure_toggle_frame.pack(fill="x", pady=(5, 5))

        self.pure_toggle_button = ttk.Button(pure_toggle_frame,
                                             text="▶ Show Pure Damage Section",
                                             command=self.toggle_pure_section)
        self.pure_toggle_button.pack(side="left")

        # Pure Damage Section (collapsible within simple grid)
        self.pure_section_frame = ttk.Frame(self.simple_grid_container)

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

        self.pure_separator = ttk.Separator(self.simple_grid_container, orient='horizontal')

        # Grand Total Section (inside simple grid)
        self.total_separator = ttk.Separator(self.simple_grid_container, orient='horizontal')
        self.total_separator.pack(fill="x", pady=15)

        self.total_frame = ttk.Frame(self.simple_grid_container, relief='solid', borderwidth=2, padding="10")
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

        # Separator at end of simple grid
        self.simple_grid_separator = ttk.Separator(main_frame, orient='horizontal')

        # ============ ATTACK > TARGET SECTION TOGGLE ============
        self.attack_target_visible = False
        self.attack_target_toggle_frame = ttk.Frame(main_frame)
        self.attack_target_toggle_frame.pack(fill="x", pady=(5, 5))
        self.attack_target_toggle_btn = ttk.Button(
            self.attack_target_toggle_frame,
            text="▶ Show Attack > Target Section",
            command=self.toggle_attack_target_section
        )
        self.attack_target_toggle_btn.pack(side="left")

        # Container for both sections
        self.attack_target_container = ttk.Frame(main_frame)

        # Targets Section
        self.targets_section = TargetsSection(
            self.attack_target_container,
            get_variables=self.get_variables,
            get_num_columns=lambda: self.num_columns,
            on_columns_change_subscribe=self.subscribe_to_column_changes
        )

        # Attack Mode Section
        self.attack_mode = AttackModeSection(
            self.attack_target_container,
            get_variables=self.get_variables,
            get_num_columns=lambda: self.num_columns,
            on_columns_change_subscribe=self.subscribe_to_column_changes
        )

        # Connect attack mode results to target section
        self.attack_mode.set_on_attack_results_changed(self.targets_section.set_attack_results)

        # Connect targets to attack mode for target selection dropdown
        self.attack_mode.set_get_targets(self.targets_section.get_target_rows)
        self.targets_section.set_on_targets_changed(self._on_targets_changed)

        self.attack_mode_separator = ttk.Separator(main_frame, orient='horizontal')

        # ============ SPELLS SECTION TOGGLE (inside Attack > Target) ============
        self.spells_visible = False
        ttk.Separator(self.attack_target_container, orient='horizontal').pack(fill="x", pady=10)
        self.spells_toggle_frame = ttk.Frame(self.attack_target_container)
        self.spells_toggle_frame.pack(fill="x", pady=(5, 5))
        self.spells_toggle_btn = ttk.Button(
            self.spells_toggle_frame,
            text="▶ Show Spells Section",
            command=self.toggle_spells_section
        )
        self.spells_toggle_btn.pack(side="left")

        # Container for Spells section
        self.spells_container = ttk.Frame(self.attack_target_container)

        # Spells Section
        self.spells_section = SpellsSection(
            self.spells_container,
            get_variables=self.get_variables,
            get_num_columns=lambda: self.num_columns,
            on_columns_change_subscribe=self.subscribe_to_column_changes
        )

        # Connect targets to spells section for target selection dropdown
        self.spells_section.set_get_targets(self.targets_section.get_target_rows)

        # ============ HERO LAB SECTION TOGGLE ============
        self.hero_lab_visible = False
        self.hero_lab_toggle_frame = ttk.Frame(main_frame)
        self.hero_lab_toggle_frame.pack(fill="x", pady=(5, 5))
        self.hero_lab_toggle_btn = ttk.Button(
            self.hero_lab_toggle_frame,
            text="▶ Show Hero Lab Section",
            command=self.toggle_hero_lab_section
        )
        self.hero_lab_toggle_btn.pack(side="left")

        self.hero_lab_container = ttk.Frame(main_frame)
        self.hero_lab_section = HeroLabSection(
            self.hero_lab_container,
            get_variables=self.get_variables
        )
        self.hero_lab_separator = ttk.Separator(main_frame, orient='horizontal')

        # ============ ITEM WORKBENCH SECTION TOGGLE ============
        self.item_workbench_visible = False
        self.item_workbench_toggle_frame = ttk.Frame(main_frame)
        self.item_workbench_toggle_frame.pack(fill="x", pady=(5, 5))
        self.item_workbench_toggle_btn = ttk.Button(
            self.item_workbench_toggle_frame,
            text="▶ Show Item Workbench Section",
            command=self.toggle_item_workbench_section
        )
        self.item_workbench_toggle_btn.pack(side="left")

        self.item_workbench_container = ttk.Frame(main_frame)
        self.item_workbench_section = ItemWorkbenchSection(
            self.item_workbench_container,
            get_variables=self.get_variables
        )
        self.item_workbench_separator = ttk.Separator(main_frame, orient='horizontal')

        # ============ SPELL WORKBENCH SECTION TOGGLE ============
        self.spell_workbench_visible = False
        self.spell_workbench_toggle_frame = ttk.Frame(main_frame)
        self.spell_workbench_toggle_frame.pack(fill="x", pady=(5, 5))
        self.spell_workbench_toggle_btn = ttk.Button(
            self.spell_workbench_toggle_frame,
            text="▶ Show Spell Workbench Section",
            command=self.toggle_spell_workbench_section
        )
        self.spell_workbench_toggle_btn.pack(side="left")

        self.spell_workbench_container = ttk.Frame(main_frame)
        self.spell_workbench_section = SpellWorkbenchSection(
            self.spell_workbench_container,
            get_variables=self.get_variables
        )
        self.spell_workbench_separator = ttk.Separator(main_frame, orient='horizontal')

        # Clear button (always visible at bottom)
        self.clear_button = ttk.Button(main_frame, text="Clear All", command=self.clear_all)
        self.clear_button.pack(pady=10)

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
        self._notify_column_change()
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
        self._notify_column_change()
        self.column_count_var.set(f"({self.num_columns} column{'s' if self.num_columns > 1 else ''})")
        self.calculate_all()

    def subscribe_to_column_changes(self, callback):
        """Subscribe to column count changes"""
        self.column_change_subscribers.append(callback)

    def _notify_column_change(self):
        """Notify all subscribers of column count change"""
        for callback in self.column_change_subscribers:
            callback(self.num_columns)

    def _update_all_rows_columns(self):
        """Update all rows to match current column count"""
        for row in self.physical_rows:
            row.update_columns(self.num_columns)
        for row in self.magic_rows:
            row.update_columns(self.num_columns)
        # Pure rows stay at 1 column

    def toggle_simple_grid(self):
        """Toggle the visibility of the Simple Grid section"""
        if self.simple_grid_visible:
            self.simple_grid_container.pack_forget()
            self.simple_grid_separator.pack_forget()
            self.simple_grid_toggle_btn.config(text="▶ Show Simple Grid")
            self.simple_grid_visible = False
        else:
            self.simple_grid_container.pack(fill="x", pady=5, after=self.simple_grid_toggle_frame)
            self.simple_grid_separator.pack(fill="x", pady=15, after=self.simple_grid_container)
            self.simple_grid_toggle_btn.config(text="▼ Hide Simple Grid")
            self.simple_grid_visible = True
            self.calculate_all()

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

    def toggle_attack_target_section(self):
        """Toggle the visibility of the combined Attack > Target section"""
        if self.attack_target_visible:
            self.attack_target_container.pack_forget()
            self.attack_mode_separator.pack_forget()
            self.attack_target_toggle_btn.config(text="▶ Show Attack > Target Section")
            self.attack_target_visible = False
        else:
            self.attack_target_container.pack(fill="x", pady=5, after=self.attack_target_toggle_frame)
            self.attack_mode_separator.pack(fill="x", pady=15, after=self.attack_target_container)
            self.attack_target_toggle_btn.config(text="▼ Hide Attack > Target Section")
            self.attack_target_visible = True
            # Pack section contents if not already packed
            self.targets_section.pack_content()
            self.attack_mode.pack_content()
            self.calculate_all()

    def toggle_spells_section(self):
        """Toggle the visibility of the Spells section"""
        if self.spells_visible:
            self.spells_container.pack_forget()
            self.spells_toggle_btn.config(text="▶ Show Spells Section")
            self.spells_visible = False
        else:
            self.spells_container.pack(fill="x", pady=5, after=self.spells_toggle_frame)
            self.spells_toggle_btn.config(text="▼ Hide Spells Section")
            self.spells_visible = True
            # Pack section content if not already packed
            self.spells_section.pack_content()
            self.calculate_all()

    def toggle_hero_lab_section(self):
        """Toggle the visibility of the Hero Lab section"""
        if self.hero_lab_visible:
            self.hero_lab_container.pack_forget()
            self.hero_lab_separator.pack_forget()
            self.hero_lab_toggle_btn.config(text="▶ Show Hero Lab Section")
            self.hero_lab_visible = False
        else:
            self.hero_lab_container.pack(fill="x", pady=5, after=self.hero_lab_toggle_frame)
            self.hero_lab_separator.pack(fill="x", pady=15, after=self.hero_lab_container)
            self.hero_lab_toggle_btn.config(text="▼ Hide Hero Lab Section")
            self.hero_lab_visible = True
            self.hero_lab_section.pack_content()

    def toggle_item_workbench_section(self):
        """Toggle the visibility of the Item Workbench section"""
        if self.item_workbench_visible:
            self.item_workbench_container.pack_forget()
            self.item_workbench_separator.pack_forget()
            self.item_workbench_toggle_btn.config(text="▶ Show Item Workbench Section")
            self.item_workbench_visible = False
        else:
            self.item_workbench_container.pack(fill="x", pady=5, after=self.item_workbench_toggle_frame)
            self.item_workbench_separator.pack(fill="x", pady=15, after=self.item_workbench_container)
            self.item_workbench_toggle_btn.config(text="▼ Hide Item Workbench Section")
            self.item_workbench_visible = True
            self.item_workbench_section.pack_content()

    def toggle_spell_workbench_section(self):
        """Toggle the visibility of the Spell Workbench section"""
        if self.spell_workbench_visible:
            self.spell_workbench_container.pack_forget()
            self.spell_workbench_separator.pack_forget()
            self.spell_workbench_toggle_btn.config(text="▶ Show Spell Workbench Section")
            self.spell_workbench_visible = False
        else:
            self.spell_workbench_container.pack(fill="x", pady=5, after=self.spell_workbench_toggle_frame)
            self.spell_workbench_separator.pack(fill="x", pady=15, after=self.spell_workbench_container)
            self.spell_workbench_toggle_btn.config(text="▼ Hide Spell Workbench Section")
            self.spell_workbench_visible = True
            self.spell_workbench_section.pack_content()

    def toggle_armor_mode(self):
        """Toggle between Armor and Physical Reduction mode"""
        self.physical_armor_mode = not self.physical_armor_mode
        variables = self.get_variables()

        if self.physical_armor_mode:
            self.physical_label_var.set("Armor:")
            self.physical_toggle_button.config(text="Switch to Reduction")
            # Convert all reduction values to armor
            for var in self.physical_vars:
                reduction = eval_reduction_expression(var.get() or "0", variables)
                armor = reduction_to_armor(reduction)
                var.set(f"{armor:.1f}")
        else:
            self.physical_label_var.set("Reduction (%):")
            self.physical_toggle_button.config(text="Switch to Armor")
            # Convert all armor values to reduction
            for var in self.physical_vars:
                reduction, _ = eval_armor_expression(var.get() or "0", variables)
                var.set(f"{reduction:.1f}")

        self.update_physical_display()

    def update_physical_display(self):
        """Update the physical reduction display based on current mode"""
        try:
            variables = self.get_variables()
            for i, var in enumerate(self.physical_vars):
                expr_str = var.get() or "0"
                if self.physical_armor_mode:
                    reduction, armor = eval_armor_expression(expr_str, variables)
                    reduction = max(0, min(100, reduction))
                    if armor is not None and has_operators(expr_str):
                        self.physical_converted_vars[i].set(f"={armor:.0f} ({reduction:.0f}%)")
                    else:
                        self.physical_converted_vars[i].set(f"({reduction:.0f}%)")
                else:
                    reduction = eval_reduction_expression(expr_str, variables)
                    if has_operators(expr_str):
                        self.physical_converted_vars[i].set(f"={reduction:.1f}%")
                    else:
                        self.physical_converted_vars[i].set("")
        except (ValueError, ZeroDivisionError):
            for conv_var in self.physical_converted_vars:
                conv_var.set("")

    def get_variables(self):
        """Get dictionary of enabled variables"""
        variables = {}
        for var_row in self.variable_rows:
            if var_row['enabled_var'].get():
                name = var_row['name_var'].get().strip()
                value_str = var_row['value_var'].get().strip()
                if name and value_str:
                    # Evaluate the value (can be an expression using other variables)
                    value = safe_eval(value_str, variables)
                    if value is not None:
                        variables[name] = value
        return variables

    def add_variable(self):
        """Add a new variable row"""
        var_frame = ttk.Frame(self.variables_container)
        var_frame.pack(fill="x", pady=2)

        # Enabled checkbox
        enabled_var = tk.BooleanVar(value=True)
        enabled_var.trace('w', lambda *args: self.calculate_all())
        enabled_cb = ttk.Checkbutton(var_frame, variable=enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Variable name
        name_var = tk.StringVar(value="")
        name_entry = ttk.Entry(var_frame, textvariable=name_var, width=10)
        name_entry.pack(side="left", padx=2)
        name_var.trace('w', lambda *args: self.calculate_all())

        ttk.Label(var_frame, text="=").pack(side="left", padx=5)

        # Variable value
        value_var = tk.StringVar(value="0")
        value_entry = ttk.Entry(var_frame, textvariable=value_var, width=15)
        value_entry.pack(side="left", padx=2)
        value_var.trace('w', lambda *args: self.calculate_all())

        # Evaluated display
        eval_var = tk.StringVar(value="")
        eval_label = ttk.Label(var_frame, textvariable=eval_var, foreground='#666',
                               font=('Arial', 9))
        eval_label.pack(side="left", padx=5)

        # Store reference for deletion
        var_row = {
            'frame': var_frame,
            'enabled_var': enabled_var,
            'name_var': name_var,
            'value_var': value_var,
            'eval_var': eval_var
        }

        # Delete button
        delete_btn = ttk.Button(var_frame, text="✕", width=3,
                                command=lambda: self.delete_variable(var_row))
        delete_btn.pack(side="left", padx=5)

        self.variable_rows.append(var_row)
        self.calculate_all()

    def delete_variable(self, var_row):
        """Delete a variable row"""
        var_row['frame'].destroy()
        self.variable_rows.remove(var_row)
        self.calculate_all()

    def update_variable_displays(self):
        """Update the evaluated value displays for variables"""
        variables = {}
        for var_row in self.variable_rows:
            name = var_row['name_var'].get().strip()
            value_str = var_row['value_var'].get().strip()
            if var_row['enabled_var'].get() and name and value_str:
                value = safe_eval(value_str, variables)
                if value is not None:
                    variables[name] = value
                    var_row['eval_var'].set(f"→ {value:.2f}")
                else:
                    var_row['eval_var'].set("→ Invalid")
            else:
                if not var_row['enabled_var'].get():
                    var_row['eval_var'].set("(disabled)")
                else:
                    var_row['eval_var'].set("")

    def add_physical_row(self):
        """Add a new physical damage row"""
        self.physical_counter += 1
        row = DamageRow(self.physical_container, self.physical_counter, "Physical",
                        self.calculate_all, self.delete_physical_row,
                        num_columns=self.num_columns, is_pure=False,
                        get_variables=self.get_variables)
        row.pack(pady=2, fill="x")
        self.physical_rows.append(row)
        self.calculate_all()

    def add_magic_row(self):
        """Add a new magic damage row"""
        self.magic_counter += 1
        row = DamageRow(self.magic_container, self.magic_counter, "Magic",
                        self.calculate_all, self.delete_magic_row,
                        num_columns=self.num_columns, is_pure=False,
                        get_variables=self.get_variables)
        row.pack(pady=2, fill="x")
        self.magic_rows.append(row)
        self.calculate_all()

    def add_pure_row(self):
        """Add a new pure damage row"""
        self.pure_counter += 1
        row = DamageRow(self.pure_container, self.pure_counter, "Pure",
                        self.calculate_all, self.delete_pure_row,
                        num_columns=1, is_pure=True,
                        get_variables=self.get_variables)
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
            # Update variable displays first
            self.update_variable_displays()

            # Get variables for use in expressions
            variables = self.get_variables()

            # Get physical reductions for all columns
            physical_reductions = []
            for var in self.physical_vars:
                expr_str = var.get() or "0"
                if self.physical_armor_mode:
                    reduction, _ = eval_armor_expression(expr_str, variables)
                else:
                    reduction = eval_reduction_expression(expr_str, variables)
                reduction = max(0, min(100, reduction))
                physical_reductions.append(reduction)

            # Get magic reductions for all columns
            magic_reductions = []
            for var in self.magic_vars:
                expr_str = var.get() or "0"
                reduction = eval_reduction_expression(expr_str, variables)
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
                        hp = safe_eval(hp_str, variables)
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

            # Update attack mode calculations
            self.attack_mode.calculate()

            # Update target mode calculations
            self.targets_section.calculate()

            # Update spells section calculations
            self.spells_section.calculate()

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

        # Clear all variables
        for var_row in self.variable_rows[:]:
            var_row['frame'].destroy()
        self.variable_rows.clear()

        # Clear attack mode, target mode, and spells
        self.attack_mode.clear()
        self.targets_section.clear()
        self.spells_section.clear()
        self.hero_lab_section.clear()
        self.item_workbench_section.clear()
        self.spell_workbench_section.clear()

        self.add_physical_row()
        self.add_magic_row()
        self.add_pure_row()
