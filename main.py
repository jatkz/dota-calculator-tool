import tkinter as tk
from tkinter import ttk

from calculator import DotaCalculator
from build_planner_app import BuildPlannerApp
from dataset_hero_app import DatasetHeroApp
from draft_library_app import HeroDraftLibraryApp
from hero_core_table_app import HeroCoreTableApp


def main():
    root = tk.Tk()
    root.title("Dota 2 Tools")
    root.geometry("1500x1200")

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    calculator_tab = ttk.Frame(notebook)
    hero_stats_tab = ttk.Frame(notebook)
    draft_library_tab = ttk.Frame(notebook)
    build_planner_tab = ttk.Frame(notebook)
    hero_core_table_tab = ttk.Frame(notebook)

    notebook.add(calculator_tab, text="Damage Calculator")
    notebook.add(hero_stats_tab, text="Hero Stats Lab")
    notebook.add(draft_library_tab, text="Draft Library")
    notebook.add(build_planner_tab, text="Build Planner")
    notebook.add(hero_core_table_tab, text="Hero Core Table")
    notebook.select(2)

    DotaCalculator(calculator_tab)
    DatasetHeroApp(hero_stats_tab)
    HeroDraftLibraryApp(draft_library_tab)
    BuildPlannerApp(build_planner_tab)
    HeroCoreTableApp(hero_core_table_tab)
    root.mainloop()


if __name__ == "__main__":
    main()
