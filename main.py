import tkinter as tk
from tkinter import ttk, messagebox
import re


class DamageRow:
    """Represents a single damage calculation row"""
    def __init__(self, parent, row_num, damage_type, on_change_callback, on_delete_callback):
        self.parent = parent
        self.row_num = row_num
        self.damage_type = damage_type
        self.on_change = on_change_callback
        self.on_delete = on_delete_callback
        
        self.frame = ttk.Frame(parent)
        
        # Damage input
        ttk.Label(self.frame, text=f"{damage_type} #{row_num}:", width=12).grid(
            row=0, column=0, sticky=tk.W, padx=5)
        
        self.damage_var = tk.StringVar(value="0")
        self.damage_var.trace('w', lambda *args: self.on_change())
        damage_entry = ttk.Entry(self.frame, textvariable=self.damage_var, width=20)
        damage_entry.grid(row=0, column=1, padx=5)
        
        # Result label
        self.result_var = tk.StringVar(value="= 0.00")
        result_label = ttk.Label(self.frame, textvariable=self.result_var, 
                                font=('Arial', 9, 'bold'), foreground='#2e7d32', width=15)
        result_label.grid(row=0, column=2, padx=10)
        
        # Delete button
        delete_btn = ttk.Button(self.frame, text="✕", width=3, 
                               command=lambda: self.on_delete(self))
        delete_btn.grid(row=0, column=3, padx=5)
    
    def safe_eval(self, expression):
        """Safely evaluate mathematical expressions"""
        try:
            # Remove whitespace
            expression = expression.strip()
            
            # Only allow numbers, basic operators, parentheses, and decimal points
            if not re.match(r'^[\d+\-*/().\s]+$', expression):
                return None
            
            # Evaluate the expression
            result = eval(expression, {"__builtins__": {}}, {})
            return float(result)
        except:
            return None
    
    def calculate(self, reduction_percent):
        """Calculate damage for this row with given reduction"""
        try:
            # Parse damage (support expressions like "66*4")
            damage_str = self.damage_var.get()
            damage = self.safe_eval(damage_str)
            
            if damage is None:
                self.result_var.set("= Invalid")
                return 0
            
            # Calculate final damage
            final_damage = damage * (1 - reduction_percent / 100)
            self.result_var.set(f"= {final_damage:.2f}")
            
            return final_damage
            
        except ValueError:
            self.result_var.set("= Invalid")
            return 0
    
    def get_damage(self, reduction_percent):
        """Get the calculated damage value"""
        return self.calculate(reduction_percent)
    
    def destroy(self):
        """Remove this row"""
        self.frame.destroy()
    
    def pack(self, **kwargs):
        """Pack the frame"""
        self.frame.pack(**kwargs)


class DotaCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Dota 2 Damage Calculator")
        self.root.geometry("700x700")
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.physical_rows = []
        self.magic_rows = []
        self.physical_counter = 0
        self.magic_counter = 0
        
        self.create_widgets()
        
        # Add initial rows
        self.add_physical_row()
        self.add_magic_row()
    
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
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)
        
        # Main frame inside scrollable area
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
        instructions.pack(pady=(0, 15))
        
        # Physical Damage Section
        physical_header = ttk.Frame(main_frame)
        physical_header.pack(fill="x", pady=(10, 5))
        
        ttk.Label(physical_header, text="Physical Damage", 
                 font=('Arial', 12, 'bold')).pack(side="left")
        
        ttk.Button(physical_header, text="+ Add Row", 
                  command=self.add_physical_row).pack(side="right", padx=5)
        
        # Physical reduction (shared across all physical rows)
        physical_reduction_frame = ttk.Frame(main_frame)
        physical_reduction_frame.pack(fill="x", pady=5)
        
        ttk.Label(physical_reduction_frame, text="Physical Reduction (%):").pack(side="left", padx=5)
        self.physical_reduction_var = tk.StringVar(value="0")
        self.physical_reduction_var.trace('w', lambda *args: self.calculate_all())
        physical_reduction_entry = ttk.Entry(physical_reduction_frame, 
                                            textvariable=self.physical_reduction_var, 
                                            width=10)
        physical_reduction_entry.pack(side="left", padx=5)
        
        # Physical rows container
        self.physical_container = ttk.Frame(main_frame)
        self.physical_container.pack(fill="x", pady=5)
        
        # Physical total
        physical_total_frame = ttk.Frame(main_frame)
        physical_total_frame.pack(fill="x", pady=(5, 10))
        self.physical_total_var = tk.StringVar(value="Physical Total: 0.00")
        ttk.Label(physical_total_frame, textvariable=self.physical_total_var,
                 font=('Arial', 11, 'bold')).pack(side="right", padx=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill="x", pady=15)
        
        # Magic Damage Section
        magic_header = ttk.Frame(main_frame)
        magic_header.pack(fill="x", pady=(10, 5))
        
        ttk.Label(magic_header, text="Magic Damage", 
                 font=('Arial', 12, 'bold')).pack(side="left")
        
        ttk.Button(magic_header, text="+ Add Row", 
                  command=self.add_magic_row).pack(side="right", padx=5)
        
        # Magic reduction (shared across all magic rows)
        magic_reduction_frame = ttk.Frame(main_frame)
        magic_reduction_frame.pack(fill="x", pady=5)
        
        ttk.Label(magic_reduction_frame, text="Magic Reduction (%):").pack(side="left", padx=5)
        self.magic_reduction_var = tk.StringVar(value="0")
        self.magic_reduction_var.trace('w', lambda *args: self.calculate_all())
        magic_reduction_entry = ttk.Entry(magic_reduction_frame, 
                                         textvariable=self.magic_reduction_var, 
                                         width=10)
        magic_reduction_entry.pack(side="left", padx=5)
        
        # Magic rows container
        self.magic_container = ttk.Frame(main_frame)
        self.magic_container.pack(fill="x", pady=5)
        
        # Magic total
        magic_total_frame = ttk.Frame(main_frame)
        magic_total_frame.pack(fill="x", pady=(5, 10))
        self.magic_total_var = tk.StringVar(value="Magic Total: 0.00")
        ttk.Label(magic_total_frame, textvariable=self.magic_total_var,
                 font=('Arial', 11, 'bold')).pack(side="right", padx=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill="x", pady=15)
        
        # Grand Total Section
        total_frame = ttk.Frame(main_frame, relief='solid', borderwidth=2, padding="10")
        total_frame.pack(fill="x", pady=10)
        
        self.grand_total_var = tk.StringVar(value="TOTAL DAMAGE: 0.00")
        ttk.Label(total_frame, textvariable=self.grand_total_var,
                 font=('Arial', 14, 'bold'), foreground='#d32f2f').pack()
        
        # Clear button
        ttk.Button(main_frame, text="Clear All", 
                  command=self.clear_all).pack(pady=10)
    
    def add_physical_row(self):
        """Add a new physical damage row"""
        self.physical_counter += 1
        row = DamageRow(self.physical_container, self.physical_counter, "Physical",
                       self.calculate_all, self.delete_physical_row)
        row.pack(pady=2, fill="x")
        self.physical_rows.append(row)
        self.calculate_all()
    
    def add_magic_row(self):
        """Add a new magic damage row"""
        self.magic_counter += 1
        row = DamageRow(self.magic_container, self.magic_counter, "Magic",
                       self.calculate_all, self.delete_magic_row)
        row.pack(pady=2, fill="x")
        self.magic_rows.append(row)
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
    
    def calculate_all(self):
        """Calculate all damage totals automatically"""
        try:
            # Get reduction percentages
            physical_reduction = float(self.physical_reduction_var.get())
            magic_reduction = float(self.magic_reduction_var.get())
            
            # Validate percentages
            if physical_reduction < 0 or physical_reduction > 100:
                physical_reduction = 0
            if magic_reduction < 0 or magic_reduction > 100:
                magic_reduction = 0
            
            # Calculate physical total
            physical_total = sum(row.get_damage(physical_reduction) for row in self.physical_rows)
            self.physical_total_var.set(f"Physical Total: {physical_total:.2f}")
            
            # Calculate magic total
            magic_total = sum(row.get_damage(magic_reduction) for row in self.magic_rows)
            self.magic_total_var.set(f"Magic Total: {magic_total:.2f}")
            
            # Calculate grand total
            grand_total = physical_total + magic_total
            self.grand_total_var.set(f"TOTAL DAMAGE: {grand_total:.2f}")
            
        except ValueError:
            pass
    
    def clear_all(self):
        """Clear all rows and reset"""
        # Clear physical rows
        for row in self.physical_rows[:]:
            row.destroy()
        self.physical_rows.clear()
        self.physical_counter = 0
        
        # Clear magic rows
        for row in self.magic_rows[:]:
            row.destroy()
        self.magic_rows.clear()
        self.magic_counter = 0
        
        # Reset reductions
        self.physical_reduction_var.set("0")
        self.magic_reduction_var.set("0")
        
        # Add initial rows back
        self.add_physical_row()
        self.add_magic_row()


def main():
    root = tk.Tk()
    app = DotaCalculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()