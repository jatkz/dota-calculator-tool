import tkinter as tk
from tkinter import ttk

from calculator import DotaCalculator
from dataset_hero_app import DatasetHeroApp


def main():
    root = tk.Tk()
    root.title("Dota 2 Tools")
    root.geometry("1200x1050")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    calculator_tab = ttk.Frame(notebook)
    hero_stats_tab = ttk.Frame(notebook)

    notebook.add(calculator_tab, text="Damage Calculator")
    notebook.add(hero_stats_tab, text="Hero Stats Lab")

    DotaCalculator(calculator_tab)
    DatasetHeroApp(hero_stats_tab)
    root.mainloop()


if __name__ == "__main__":
    main()
