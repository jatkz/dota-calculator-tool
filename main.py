import tkinter as tk
from calculator import DotaCalculator


def main():
    root = tk.Tk()
    app = DotaCalculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
