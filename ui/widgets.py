"""Reusable UI widgets."""

import tkinter as tk
from tkinter import ttk
from typing import List


class ScrollableFrame(tk.Frame):
    """Vertical-scrolling container. Excluded widgets handle their own wheel."""

    def __init__(self, parent, bg: str, root: tk.Tk, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.root = root
        self.bg = bg
        self.excluded: List[tk.Widget] = []

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            style="Vertical.TScrollbar",
        )
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_wheel()

    def _on_inner_configure(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def add_excluded(self, widget: tk.Widget):
        self.excluded.append(widget)

    def _is_excluded(self, widget) -> bool:
        w = widget
        while w is not None:
            if w in self.excluded:
                return True

            try:
                w = w.master

            except AttributeError:
                return False

        return False

    def _bind_wheel(self):
        self.root.bind_all("<MouseWheel>", self._on_wheel, add="+")
        self.root.bind_all("<Button-4>", self._on_wheel, add="+")
        self.root.bind_all("<Button-5>", self._on_wheel, add="+")

    def _on_wheel(self, event):
        if self._is_excluded(event.widget):
            return

        delta = 0
        if event.num == 4:
            delta = -1

        elif event.num == 5:
            delta = 1

        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1

        if delta:
            self.canvas.yview_scroll(delta * 3, "units")
