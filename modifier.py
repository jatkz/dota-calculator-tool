"""Modifier class for toggleable flat/percentage damage modifiers"""

import tkinter as tk
from tkinter import ttk

from utils import safe_eval


class Modifier:
    """Represents a single damage modifier (flat or percentage)"""

    def __init__(self, parent, on_change_callback, on_delete_callback, get_variables=None):
        """
        Initialize a modifier row.

        Args:
            parent: Parent widget
            on_change_callback: Called when modifier values change
            on_delete_callback: Called when delete button is clicked
            get_variables: Callback to get current variables dict
        """
        self.parent = parent
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        self.get_variables = get_variables

        self.frame = ttk.Frame(parent)

        # Enabled checkbox
        self.enabled_var = tk.BooleanVar(value=True)
        self.enabled_var.trace('w', lambda *args: self.on_change())
        enabled_cb = ttk.Checkbutton(self.frame, variable=self.enabled_var)
        enabled_cb.pack(side="left", padx=(0, 5))

        # Name input
        ttk.Label(self.frame, text="Name:").pack(side="left")
        self.name_var = tk.StringVar(value="")
        name_entry = ttk.Entry(self.frame, textvariable=self.name_var, width=12)
        name_entry.pack(side="left", padx=2)

        # Value input
        ttk.Label(self.frame, text="Value:").pack(side="left", padx=(5, 0))
        self.value_var = tk.StringVar(value="0")
        self.value_var.trace('w', lambda *args: self.on_change())
        value_entry = ttk.Entry(self.frame, textvariable=self.value_var, width=8)
        value_entry.pack(side="left", padx=2)

        # Evaluated value display
        self.eval_var = tk.StringVar(value="")
        eval_label = ttk.Label(self.frame, textvariable=self.eval_var,
                               foreground='#666', font=('Arial', 8), width=8)
        eval_label.pack(side="left")

        # Type dropdown (Flat + or Percentage %)
        ttk.Label(self.frame, text="Type:").pack(side="left", padx=(5, 0))
        self.type_var = tk.StringVar(value="Flat +")
        type_combo = ttk.Combobox(self.frame, textvariable=self.type_var,
                                  values=["Flat +", "Percent %"], state="readonly", width=8)
        type_combo.pack(side="left", padx=2)
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.on_change())

        # Delete button
        delete_btn = ttk.Button(self.frame, text="X", width=2,
                                command=lambda: self.on_delete(self))
        delete_btn.pack(side="left", padx=5)

    def is_enabled(self):
        """Check if modifier is enabled"""
        return self.enabled_var.get()

    def get_name(self):
        """Get modifier name"""
        return self.name_var.get()

    def get_type(self):
        """Get modifier type ('flat' or 'percent')"""
        return "flat" if self.type_var.get() == "Flat +" else "percent"

    def get_value(self):
        """
        Get the evaluated modifier value.

        Returns:
            For flat: the raw value
            For percent: the value as a decimal (e.g., 25 input -> 0.25)
        """
        if not self.enabled_var.get():
            return 0

        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.value_var.get(), variables)

        if value is None:
            return 0

        if self.get_type() == "percent":
            return value / 100  # Convert percentage to decimal
        return value

    def update_display(self):
        """Update the evaluated value display"""
        if not self.enabled_var.get():
            self.eval_var.set("(off)")
            return

        variables = self.get_variables() if self.get_variables else None
        value = safe_eval(self.value_var.get(), variables)

        if value is None:
            self.eval_var.set("= ???")
        else:
            if self.get_type() == "percent":
                self.eval_var.set(f"= {value:.1f}%")
            else:
                self.eval_var.set(f"= {value:.1f}")

    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)

    def destroy(self):
        """Remove this modifier"""
        self.frame.destroy()
