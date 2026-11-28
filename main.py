"""Entry point for Project Snapshotter."""

import tkinter as tk

import os
from core.config import APP_NAME
from core.fonts import FontManager
from ui.app import SnapshotApp


def main():
    root = tk.Tk()
    root.title(APP_NAME)
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(ico_path):
        root.iconbitmap(ico_path)

    font_mgr = FontManager(root)
    font_mgr.scan_and_load()

    SnapshotApp(root, font_mgr)
    root.mainloop()


if __name__ == "__main__":
    main()
