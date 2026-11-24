"""Project Snapshotter — entry point."""

import tkinter as tk

from core.fonts import FontManager
from ui.app import SnapshotApp


def main():
    root = tk.Tk()
    font_mgr = FontManager(root)
    font_mgr.scan_and_load()
    SnapshotApp(root, font_mgr)
    root.mainloop()


if __name__ == "__main__":
    main()
