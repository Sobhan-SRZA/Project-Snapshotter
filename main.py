"""Project Snapshotter — entry point."""

import tkinter as tk

from core.fonts import FontManager
from core.icons import has_svg_support
from ui.app import SnapshotApp


def main():
    root = tk.Tk()
    if not has_svg_support():
        print("[info] For best icon quality, install: pip install cairosvg pillow")

    font_mgr = FontManager(root)
    font_mgr.scan_and_load()

    SnapshotApp(root, font_mgr)
    root.mainloop()


if __name__ == "__main__":
    main()
