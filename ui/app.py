"""Redesigned Tkinter UI for Project Snapshotter."""

import os
import sys
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog
from typing import List, Optional, Tuple

from core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_LANG,
    DEFAULT_THEME,
    DEFAULT_USE_GITIGNORE,
    DEFAULT_OUTPUT_NAME,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    AUTHOR_NAME,
    AUTHOR_TEAM,
    COPYRIGHT_YEAR,
    GITHUB_URL,
    GITHUB_DISPLAY,
    WEBSITE_URL,
    WEBSITE_DISPLAY,
    MIN_FONT_SCALE,
    MAX_FONT_SCALE,
    FONT_SCALE_STEP,
)
from core.themes import PALETTES, resolve_theme
from core.strings import STRINGS
from core.fonts import FontManager
from core.snapshot_engine import create_snapshot, _format_bytes
from core.icons import get_icon
from ui.widgets import ScrollableFrame

QUICK_PRESETS = ["*.log", "*.lock", "tests/", "docs/", "*.env*"]


def _has_persian(text) -> bool:
    if not text:
        return False
    for c in str(text):
        o = ord(c)
        if 0x0600 <= o <= 0x06FF or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
            return True
    return False


class SnapshotApp:
    def __init__(self, root: tk.Tk, font_mgr: FontManager):
        self.root = root
        self.font_mgr = font_mgr
        self.theme = resolve_theme(DEFAULT_THEME)
        self.lang = DEFAULT_LANG
        self.colors = PALETTES[self.theme]
        self.running = False
        self.cancel_event: Optional[threading.Event] = None
        self._log_entries: List[Tuple[float, str, dict, str]] = []
        self._status_key = "status_ready"
        self._status_state = "idle"
        self._toast_widget = None
        self._toast_after_id = None
        self.font_scale = 1.0
        self._stats = {"processed": 0, "skipped": 0, "bytes": 0}

        self.font_en, self.font_fa = font_mgr.pick_ui_fonts()
        self.font_mono = font_mgr.pick_mono_font()
        self._icon_cache: dict = {}

        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self._build_ui()
        self._apply_theme()
        self._apply_language()
        self._update_stats_bar()
        self._show_empty_log()

        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<Control-l>", lambda e: self._toggle_lang())
        self.root.bind("<F5>", lambda e: self._start())
        self.root.bind("<Control-Return>", lambda e: self._start())
        self.root.bind("<Escape>", lambda e: self._on_escape())
        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-KP_Add>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-KP_Subtract>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())

    # ---- helpers ----
    def _t(self, key, **kw):
        tpl = STRINGS[self.lang].get(key, key)
        try:
            return tpl.format(**kw) if kw else tpl
        except (KeyError, IndexError):
            return tpl

    def _rtl(self):
        return self.lang == "fa"

    def _scaled(self, size):
        return max(6, int(round(size * self.font_scale)))

    def _font_lang(self, size, weight="normal", lang=None):
        if lang is None:
            lang = self.lang
        family = self.font_fa if lang == "fa" else self.font_en
        return (family, self._scaled(size), weight)

    def _font_for(self, text, size, weight="normal"):
        lang = "fa" if _has_persian(text) else "en"
        return self._font_lang(size, weight, lang)

    def _font_mono(self, size):
        return (self.font_mono, self._scaled(size))

    def _font(self, size, weight="normal"):
        return self._font_lang(size, weight)

    # ---- icon helpers ----
    def _icon(self, name, size=16, fg=None):
        fg = fg or self.colors["text"]
        kind, value = get_icon(name, size=size, fg=fg)
        if kind == "image":
            self._icon_cache[(name, size, fg)] = value
        return kind, value

    def _make_icon_label(self, parent, name, size=16, fg=None, **kw):
        kind, value = self._icon(name, size=size, fg=fg)
        if kind == "image":
            lbl = tk.Label(parent, image=value, borderwidth=0, **kw)
        else:
            lbl = tk.Label(
                parent, text=value, font=self._font_lang(size), borderwidth=0, **kw
            )
        lbl._icon_name = name
        lbl._icon_size = size
        return lbl

    def _refresh_icon(self, lbl, fg=None):
        name = getattr(lbl, "_icon_name", None)
        if not name:
            return
        size = getattr(lbl, "_icon_size", 16)
        fg = fg or self.colors["text"]
        kind, value = self._icon(name, size=size, fg=fg)
        if kind == "image":
            lbl.config(image=value, text="")
            self._icon_cache[(name, size, fg)] = value
        else:
            lbl.config(image="", text=value, font=self._font_lang(size))

    # ============================================================
    # Build UI
    # ============================================================
    def _build_ui(self):
        # Top bar
        self.header = tk.Frame(self.root, height=72)
        self.header._role = "header"
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        self.title_block = tk.Frame(self.header)
        self.title_block._role = "header"
        self.title_block.pack(side=tk.LEFT, padx=20, pady=12)

        self.logo_badge = tk.Frame(self.title_block, padx=8, pady=8)
        self.logo_badge._role = "accent_badge"
        self.logo_badge.pack(side=tk.LEFT, padx=(0, 12))

        self.logo_lbl = self._make_icon_label(self.logo_badge, "layers", size=20)
        self.logo_lbl._role = "accent_badge"
        self.logo_lbl.pack()

        text_block = tk.Frame(self.title_block)
        text_block._role = "header"
        text_block.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(text_block, font=self._font(15, "bold"))
        self.title_lbl._text_key = "app_title"
        self.title_lbl._font_size = 15
        self.title_lbl._font_weight = "bold"
        self.title_lbl._role = "title"
        self.title_lbl.pack(anchor=tk.W)

        self.subtitle_lbl = tk.Label(text_block, font=self._font(9))
        self.subtitle_lbl._text_key = "app_subtitle"
        self.subtitle_lbl._font_size = 9
        self.subtitle_lbl._font_weight = "normal"
        self.subtitle_lbl._role = "subtitle"
        self.subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        self.actions = tk.Frame(self.header)
        self.actions._role = "header"
        self.actions.pack(side=tk.RIGHT, padx=18)

        self.theme_btn = self._make_icon_label(
            self.actions, "moon", size=18, padx=6, pady=6
        )
        self.theme_btn._role = "ghost_btn"
        self.theme_btn.pack(side=tk.RIGHT, padx=(3, 0))
        self.theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())
        self._attach_hover(self.theme_btn, "ghost_btn")

        self.lang_btn = self._make_icon_label(
            self.actions, "globe", size=18, padx=6, pady=6
        )
        self.lang_btn._role = "ghost_btn"
        self.lang_btn.pack(side=tk.RIGHT, padx=(3, 0))
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_lang())
        self._attach_hover(self.lang_btn, "ghost_btn")

        self._hsep(self.actions).pack(side=tk.RIGHT, padx=8)

        self.zoom_in_btn = self._make_icon_label(
            self.actions, "zoom-in", size=18, padx=6, pady=6
        )
        self.zoom_in_btn._role = "ghost_btn"
        self.zoom_in_btn.pack(side=tk.RIGHT, padx=(2, 0))
        self.zoom_in_btn.bind("<Button-1>", lambda e: self._zoom_in())
        self._attach_hover(self.zoom_in_btn, "ghost_btn")

        self.zoom_lbl = tk.Label(self.actions, font=self._font(9, "bold"), width=5)
        self.zoom_lbl._role = "zoom_label"
        self.zoom_lbl._font_size = 9
        self.zoom_lbl._font_weight = "bold"
        self.zoom_lbl.pack(side=tk.RIGHT, padx=2)
        self.zoom_lbl.bind("<Button-1>", lambda e: self._zoom_reset())

        self.zoom_out_btn = self._make_icon_label(
            self.actions, "zoom-out", size=18, padx=6, pady=6
        )
        self.zoom_out_btn._role = "ghost_btn"
        self.zoom_out_btn.pack(side=tk.RIGHT, padx=(2, 0))
        self.zoom_out_btn.bind("<Button-1>", lambda e: self._zoom_out())
        self._attach_hover(self.zoom_out_btn, "ghost_btn")

        self.header_line = tk.Frame(self.root, height=1)
        self.header_line._role = "separator"
        self.header_line.pack(fill=tk.X)

        self._build_footer()

        self.body_scroll = ScrollableFrame(
            self.root, bg=self.colors["surface"], root=self.root
        )
        self.body_scroll._role = "surface"
        self.body_scroll.pack(fill=tk.BOTH, expand=True)
        body = self.body_scroll.inner

        inner_wrap = tk.Frame(body)
        inner_wrap._role = "surface"
        inner_wrap.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        self._build_paths_card(inner_wrap)
        self._build_ignore_card(inner_wrap)
        self._build_action_row(inner_wrap)
        self._build_stats_row(inner_wrap)
        self._build_progress(inner_wrap)
        self._build_log_card(inner_wrap)

        self.body_scroll.add_excluded(self.log_text)
        self.body_scroll.add_excluded(self.exclude_text)
        self._bind_log_wheel()

    def _hsep(self, parent):
        f = tk.Frame(parent, width=1, height=20)
        f._role = "separator_vert"
        return f

    def _attach_hover(self, w, role):
        def on_enter(_e):
            c = self.colors
            w.config(bg=c["header_hover"] if role == "ghost_btn" else c["card_hover"])

        def on_leave(_e):
            c = self.colors
            w.config(bg=c["header"] if role == "ghost_btn" else c["card"])

        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

    def _card(self, parent, pady_bottom=12) -> tk.Frame:
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        card.pack(fill=tk.X, pady=(0, pady_bottom))
        return card

    def _section_header(self, parent, key, icon_name):
        f = tk.Frame(parent)
        f._role = "card"
        f.pack(fill=tk.X, pady=(0, 12))
        icon_lbl = self._make_icon_label(f, icon_name, size=16)
        icon_lbl._role = "card"
        icon_lbl.pack(side=tk.LEFT, padx=(0, 8))
        lbl = tk.Label(f, font=self._font(11, "bold"), anchor=tk.W)
        lbl._text_key = key
        lbl._font_size = 11
        lbl._font_weight = "bold"
        lbl._role = "card_title"
        lbl.pack(side=tk.LEFT)
        return f

    def _build_paths_card(self, parent):
        card = self._card(parent)
        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=18, pady=15)

        self._section_header(inner, "section_paths", "folder")

        self.lbl_project = tk.Label(inner, font=self._font(9, "bold"), anchor=tk.W)
        self.lbl_project._text_key = "project_path"
        self.lbl_project._font_size = 9
        self.lbl_project._font_weight = "bold"
        self.lbl_project._role = "field_label"
        self.lbl_project.pack(fill=tk.X, pady=(0, 5))

        self.row_project = tk.Frame(inner)
        self.row_project._role = "card"
        self.row_project.pack(fill=tk.X)

        self.project_var = tk.StringVar()
        self.project_entry = ttk.Entry(
            self.row_project, textvariable=self.project_var, style="TEntry"
        )
        self.project_entry._font_size = 10
        self.project_entry._font_weight = "normal"

        self.browse_btn1 = ttk.Button(
            self.row_project, style="Secondary.TButton", command=self._browse_project
        )
        self.browse_btn1._text_key = "browse"

        self.lbl_output = tk.Label(inner, font=self._font(9, "bold"), anchor=tk.W)
        self.lbl_output._text_key = "output_path"
        self.lbl_output._font_size = 9
        self.lbl_output._font_weight = "bold"
        self.lbl_output._role = "field_label"
        self.lbl_output.pack(fill=tk.X, pady=(12, 5))

        self.row_output = tk.Frame(inner)
        self.row_output._role = "card"
        self.row_output.pack(fill=tk.X)

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(
            self.row_output, textvariable=self.output_var, style="TEntry"
        )
        self.output_entry._font_size = 10
        self.output_entry._font_weight = "normal"

        self.browse_btn2 = ttk.Button(
            self.row_output, style="Secondary.TButton", command=self._browse_output
        )
        self.browse_btn2._text_key = "save_as"

        self._path_rows = [
            (self.project_entry, self.browse_btn1),
            (self.output_entry, self.browse_btn2),
        ]

    def _build_ignore_card(self, parent):
        card = self._card(parent)
        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=18, pady=15)

        self._section_header(inner, "section_ignore", "filter")

        self.use_gitignore_var = tk.BooleanVar(value=DEFAULT_USE_GITIGNORE)
        self.gitignore_cb = ttk.Checkbutton(
            inner, variable=self.use_gitignore_var, style="TCheckbutton"
        )
        self.gitignore_cb._text_key = "use_gitignore"
        self.gitignore_cb.pack(anchor=tk.W, pady=(0, 12))

        lbl = tk.Label(inner, font=self._font(9, "bold"), anchor=tk.W)
        lbl._text_key = "manual_patterns"
        lbl._font_size = 9
        lbl._font_weight = "bold"
        lbl._role = "field_label"
        lbl.pack(fill=tk.X, pady=(0, 5))

        self.exclude_text = tk.Text(
            inner,
            height=3,
            wrap=tk.WORD,
            font=self._font_mono(10),
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=8,
            highlightthickness=1,
        )
        self.exclude_text._role = "text_input"
        self.exclude_text.pack(fill=tk.X)

        # Quick preset chips row
        self.presets_row = tk.Frame(inner)
        self.presets_row._role = "card"
        self.presets_row.pack(fill=tk.X, pady=(8, 2))

        self.presets_lbl = tk.Label(self.presets_row, font=self._font(8, "bold"))
        self.presets_lbl._text_key = "quick_presets"
        self.presets_lbl._font_size = 8
        self.presets_lbl._font_weight = "bold"
        self.presets_lbl._role = "hint"
        self.presets_lbl.pack(side=tk.LEFT, padx=(0, 6))

        for pat in QUICK_PRESETS:
            chip = tk.Label(
                self.presets_row,
                text=pat,
                font=self._font_mono(8),
                padx=8,
                pady=2,
                cursor="hand2",
            )
            chip._role = "chip"
            chip.pack(side=tk.LEFT, padx=(0, 5))
            chip.bind("<Button-1>", lambda _e, p=pat: self._add_preset(p))

        self._pattern_hint = tk.Label(inner, font=self._font(8), anchor=tk.W)
        self._pattern_hint._text_key = "pattern_hint"
        self._pattern_hint._font_size = 8
        self._pattern_hint._font_weight = "normal"
        self._pattern_hint._role = "hint"
        self._pattern_hint.pack(fill=tk.X, pady=(6, 0))

    def _add_preset(self, pattern: str):
        current = self.exclude_text.get("1.0", tk.END).strip()
        existing = [
            x.strip() for x in current.replace(",", "\n").splitlines() if x.strip()
        ]
        if pattern not in existing:
            new_text = f"{current}\n{pattern}" if current else pattern
            self.exclude_text.delete("1.0", tk.END)
            self.exclude_text.insert("1.0", new_text)
        self._show_toast(self._t("toast_preset_added", p=pattern), "info")

    def _build_action_row(self, parent):
        self.action_row = tk.Frame(parent)
        self.action_row._role = "surface"
        self.action_row.pack(fill=tk.X, pady=(0, 8))

        self.start_btn = ttk.Button(
            self.action_row, style="Primary.TButton", command=self._start
        )
        self.start_btn._text_key = "start_btn"

        self.cancel_btn = ttk.Button(
            self.action_row, style="Secondary.TButton", command=self._cancel
        )
        self.cancel_btn._text_key = "cancel_btn"

        self.open_btn = ttk.Button(
            self.action_row, style="Secondary.TButton", command=self._open_output_folder
        )
        self.open_btn._text_key = "open_folder"

        self.copy_btn = ttk.Button(
            self.action_row, style="Secondary.TButton", command=self._copy_output_path
        )
        self.copy_btn._text_key = "copy_path"

        self.status_box = tk.Frame(self.action_row)
        self.status_box._role = "surface"
        self.status_dot = tk.Label(self.status_box, text="●", font=self._font(11))
        self.status_dot._role = "status_dot"
        self.status_label = tk.Label(self.status_box, font=self._font(9, "bold"))
        self.status_label._role = "status_text"
        self.status_label._font_size = 9
        self.status_label._font_weight = "bold"

        self.hint_lbl = tk.Label(self.action_row, font=self._font(8))
        self.hint_lbl._text_key = "btn_hint"
        self.hint_lbl._font_size = 8
        self.hint_lbl._font_weight = "normal"
        self.hint_lbl._role = "hint_surface"

    def _build_stats_row(self, parent):
        self.stats_bar = tk.Frame(parent, highlightthickness=1)
        self.stats_bar._role = "card"
        self.stats_bar.pack(fill=tk.X, pady=(0, 8))

        inner = tk.Frame(self.stats_bar)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=14, pady=7)

        self.stat_processed_lbl = tk.Label(inner, font=self._font(8, "bold"))
        self.stat_processed_lbl._role = "stat_success"
        self.stat_processed_lbl._font_size = 8
        self.stat_processed_lbl._font_weight = "bold"
        self.stat_processed_lbl.pack(side=tk.LEFT, padx=(0, 18))

        self.stat_skipped_lbl = tk.Label(inner, font=self._font(8, "bold"))
        self.stat_skipped_lbl._role = "hint"
        self.stat_skipped_lbl._font_size = 8
        self.stat_skipped_lbl._font_weight = "bold"
        self.stat_skipped_lbl.pack(side=tk.LEFT, padx=(0, 18))

        self.stat_size_lbl = tk.Label(inner, font=self._font(8, "bold"))
        self.stat_size_lbl._role = "stat_accent"
        self.stat_size_lbl._font_size = 8
        self.stat_size_lbl._font_weight = "bold"
        self.stat_size_lbl.pack(side=tk.LEFT)

    def _update_stats_bar(self):
        self.stat_processed_lbl.config(
            text=self._t("stat_processed", n=self._stats["processed"])
        )
        self.stat_skipped_lbl.config(
            text=self._t("stat_skipped", n=self._stats["skipped"])
        )
        self.stat_size_lbl.config(
            text=self._t("stat_size", size=_format_bytes(self._stats["bytes"]))
        )

    def _build_progress(self, parent):
        self.progress = ttk.Progressbar(
            parent, mode="indeterminate", style="Accent.Horizontal.TProgressbar"
        )
        self.progress.pack(fill=tk.X, pady=(0, 10))

    def _build_log_card(self, parent):
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=15)

        head = tk.Frame(inner)
        head._role = "card"
        head.pack(fill=tk.X, pady=(0, 10))

        icon_lbl = self._make_icon_label(head, "terminal", size=16)
        icon_lbl._role = "card"
        icon_lbl.pack(side=tk.LEFT, padx=(0, 8))

        self.log_title = tk.Label(head, font=self._font(11, "bold"), anchor=tk.W)
        self.log_title._text_key = "log_title"
        self.log_title._font_size = 11
        self.log_title._font_weight = "bold"
        self.log_title._role = "card_title"

        self.clear_btn = tk.Frame(head, cursor="hand2", padx=6, pady=2)
        self.clear_btn._role = "ghost_small"
        self.clear_btn_icon = self._make_icon_label(self.clear_btn, "trash", size=12)
        self.clear_btn_icon._role = "ghost_small"
        self.clear_btn_icon.pack(side=tk.LEFT, padx=(0, 4))
        self.clear_btn_lbl = tk.Label(self.clear_btn, font=self._font(9))
        self.clear_btn_lbl._text_key = "log_clear"
        self.clear_btn_lbl._font_size = 9
        self.clear_btn_lbl._font_weight = "normal"
        self.clear_btn_lbl._role = "ghost_small"
        self.clear_btn_lbl.pack(side=tk.LEFT)
        for w in (self.clear_btn, self.clear_btn_lbl, self.clear_btn_icon):
            w.bind("<Button-1>", lambda e: self._clear_log())
        self._attach_hover_small(self.clear_btn)

        text_container = tk.Frame(inner, height=230)
        text_container._role = "card"
        text_container.pack(fill=tk.BOTH, expand=True)
        text_container.pack_propagate(False)

        self.log_text = tk.Text(
            text_container,
            wrap=tk.WORD,
            font=self._font_mono(9),
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            highlightthickness=1,
            height=11,
        )
        self.log_text._role = "log"

        self.log_scroll = ttk.Scrollbar(
            text_container,
            orient=tk.VERTICAL,
            command=self.log_text.yview,
            style="Vertical.TScrollbar",
        )
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.empty_overlay = tk.Frame(self.log_text, bg=self.colors["log_bg"])
        self.empty_title = tk.Label(self.empty_overlay, font=self._font(11, "bold"))
        self.empty_title._text_key = "log_empty"
        self.empty_title._font_size = 11
        self.empty_title._font_weight = "bold"
        self.empty_title._role = "empty_title"
        self.empty_title.pack(pady=(0, 4))
        self.empty_sub = tk.Label(self.empty_overlay, font=self._font(9))
        self.empty_sub._text_key = "log_empty_sub"
        self.empty_sub._font_size = 9
        self.empty_sub._font_weight = "normal"
        self.empty_sub._role = "empty_sub"
        self.empty_sub.pack()

    def _bind_log_wheel(self):
        def wheel_up(e):
            self.log_text.yview_scroll(-2, "units")
            return "break"

        def wheel_down(e):
            self.log_text.yview_scroll(2, "units")
            return "break"

        self.log_text.bind("<Button-4>", wheel_up)
        self.log_text.bind("<Button-5>", wheel_down)

    def _build_footer(self):
        self.footer = tk.Frame(self.root, height=32)
        self.footer._role = "footer"
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        self.footer_hint = tk.Label(self.footer, font=self._font(8))
        self.footer_hint._text_key = "footer_hint"
        self.footer_hint._font_size = 8
        self.footer_hint._font_weight = "normal"
        self.footer_hint._role = "footer_text"
        self.footer_hint.pack(side=tk.LEFT, padx=18)

        self.version_lbl = tk.Label(
            self.footer, text=f"v{APP_VERSION}", font=self._font(8, "bold")
        )
        self.version_lbl._role = "footer_text"
        self.version_lbl._font_size = 8
        self.version_lbl._font_weight = "bold"
        self.version_lbl.pack(side=tk.RIGHT, padx=(0, 18))

        self.author_frame = tk.Frame(self.footer)
        self.author_frame._role = "footer"
        self.author_frame.pack(side=tk.RIGHT, padx=(0, 12))

        self.copyright_lbl = tk.Label(
            self.author_frame,
            text=f"© {COPYRIGHT_YEAR} {AUTHOR_NAME} · {AUTHOR_TEAM}",
            font=self._font(8),
        )
        self.copyright_lbl._role = "footer_text"
        self.copyright_lbl._font_size = 8
        self.copyright_lbl._font_weight = "normal"
        self.copyright_lbl.pack(side=tk.LEFT)

        self._footer_sep(self.author_frame)
        self.github_link = self._make_footer_link(
            self.author_frame, "github", GITHUB_DISPLAY, GITHUB_URL
        )
        self._footer_sep(self.author_frame)
        self.site_link = self._make_footer_link(
            self.author_frame, "external", WEBSITE_DISPLAY, WEBSITE_URL
        )

    def _make_footer_link(self, parent, icon_name, text, url):
        wrapper = tk.Frame(parent, cursor="hand2")
        wrapper._role = "footer"
        icon = self._make_icon_label(wrapper, icon_name, size=11)
        icon._role = "footer_link"
        icon.pack(side=tk.LEFT, padx=(0, 3))
        lbl = tk.Label(wrapper, text=text, font=self._font(8, "bold"))
        lbl._role = "footer_link"
        lbl._font_size = 8
        lbl._font_weight = "bold"
        lbl.pack(side=tk.LEFT)
        for w in (wrapper, icon, lbl):
            w.bind("<Button-1>", lambda e: self._open_url(url))
        self._setup_link_hover(lbl)
        return wrapper

    def _footer_sep(self, parent):
        sep = tk.Label(parent, text="·", font=self._font(8))
        sep._role = "footer_text"
        sep.pack(side=tk.LEFT, padx=6)

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _setup_link_hover(self, w):
        def on_enter(_e):
            w.config(
                fg=self.colors["accent_hover"],
                font=(w.cget("font")[0], w.cget("font")[1], "underline"),
            )

        def on_leave(_e):
            w.config(
                fg=self.colors["accent"],
                font=self._font_lang(w._font_size, w._font_weight),
            )

        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

    def _attach_hover_small(self, w):
        def enter(_e):
            try:
                w.config(bg=self.colors["card_hover"])
            except tk.TclError:
                pass

        def leave(_e):
            try:
                w.config(bg=self.colors["card"])
            except tk.TclError:
                pass

        w.bind("<Enter>", enter, add="+")
        w.bind("<Leave>", leave, add="+")

    # ============================================================
    # Theme
    # ============================================================
    def _apply_theme(self):
        self.colors = PALETTES[self.theme]
        c = self.colors
        self.root.config(bg=c["surface"])
        self._apply_ttk_styles()
        self._apply_roles_recursive(self.root)
        self._update_log_tags()
        self._refresh_header_icons()
        self._update_zoom_label()
        if hasattr(self, "_status_key"):
            self._set_status(self._status_key, self._status_state)
        if self._toast_widget is not None:
            self._hide_toast()

    def _refresh_header_icons(self):
        self._refresh_icon(self.logo_lbl, fg=self.colors["accent_fg"])
        theme_icon = "sun" if self.theme == "dark" else "moon"
        self.theme_btn._icon_name = theme_icon
        self._refresh_icon(self.theme_btn, fg=self.colors["text"])
        self._refresh_icon(self.lang_btn, fg=self.colors["text"])
        self._refresh_icon(self.zoom_in_btn, fg=self.colors["text"])
        self._refresh_icon(self.zoom_out_btn, fg=self.colors["text"])
        self._refresh_icon(self.clear_btn_icon, fg=self.colors["accent"])

    def _apply_roles_recursive(self, w):
        role = getattr(w, "_role", None)
        if role:
            try:
                self._apply_role(w, role)
            except tk.TclError:
                pass
        for child in w.winfo_children():
            self._apply_roles_recursive(child)

    def _apply_role(self, w, role):
        c = self.colors
        mapping = {
            "surface": dict(bg=c["surface"]),
            "header": dict(bg=c["header"]),
            "accent_badge": dict(bg=c["accent"]),
            "card": dict(bg=c["card"], highlightbackground=c["border"]),
            "separator": dict(bg=c["border"]),
            "separator_vert": dict(bg=c["border"]),
            "footer": dict(bg=c["surface"]),
            "title": dict(bg=c["header"], fg=c["text"]),
            "subtitle": dict(bg=c["header"], fg=c["text_sub"]),
            "card_title": dict(bg=c["card"], fg=c["text"]),
            "field_label": dict(bg=c["card"], fg=c["text_sub"]),
            "hint": dict(bg=c["card"], fg=c["muted"]),
            "hint_surface": dict(bg=c["surface"], fg=c["muted"]),
            "chip": dict(bg=c["surface_hover"], fg=c["text_sub"]),
            "stat_success": dict(bg=c["card"], fg=c["success"]),
            "stat_accent": dict(bg=c["card"], fg=c["accent"]),
            "footer_text": dict(bg=c["surface"], fg=c["muted"]),
            "footer_link": dict(bg=c["surface"], fg=c["accent"]),
            "ghost_btn": dict(bg=c["header"], fg=c["text"]),
            "ghost_small": dict(bg=c["card"], fg=c["accent"]),
            "zoom_label": dict(bg=c["header"], fg=c["text_sub"]),
            "status_dot": dict(bg=c["surface"]),
            "status_text": dict(bg=c["surface"], fg=c["text_sub"]),
            "empty_title": dict(bg=c["log_bg"], fg=c["text_sub"]),
            "empty_sub": dict(bg=c["log_bg"], fg=c["muted"]),
            "text_input": dict(
                bg=c["input"],
                fg=c["text"],
                insertbackground=c["text"],
                highlightbackground=c["input_border"],
                highlightcolor=c["accent"],
                selectbackground=c["accent"],
                selectforeground=c["accent_fg"],
            ),
            "log": dict(
                bg=c["log_bg"],
                fg=c["log_fg"],
                insertbackground=c["log_fg"],
                highlightbackground=c["border"],
                selectbackground=c["accent"],
                selectforeground=c["accent_fg"],
            ),
        }
        if role in mapping:
            w.config(**mapping[role])

    def _apply_ttk_styles(self):
        c = self.colors
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass

        s.configure(
            "TEntry",
            fieldbackground=c["input"],
            foreground=c["text"],
            insertcolor=c["text"],
            bordercolor=c["input_border"],
            lightcolor=c["input"],
            darkcolor=c["input"],
            padding=(10, 7),
            relief="flat",
            font=self._font_lang(10),
        )
        s.map(
            "TEntry",
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
            darkcolor=[("focus", c["accent"])],
        )

        s.configure(
            "Error.TEntry",
            fieldbackground=c["input"],
            foreground=c["text"],
            bordercolor=c["danger"],
            lightcolor=c["danger"],
            darkcolor=c["danger"],
        )

        s.configure(
            "Primary.TButton",
            background=c["accent"],
            foreground=c["accent_fg"],
            bordercolor=c["accent"],
            lightcolor=c["accent"],
            darkcolor=c["accent"],
            focuscolor=c["accent"],
            padding=(18, 8),
            font=self._font_lang(10, "bold"),
            relief="flat",
        )
        s.map(
            "Primary.TButton",
            background=[
                ("active", c["accent_hover"]),
                ("pressed", c["accent_hover"]),
                ("disabled", c["muted"]),
            ],
            bordercolor=[("active", c["accent_hover"])],
            lightcolor=[("active", c["accent_hover"])],
            darkcolor=[("active", c["accent_hover"])],
        )

        s.configure(
            "Secondary.TButton",
            background=c["card"],
            foreground=c["text"],
            bordercolor=c["border_strong"],
            lightcolor=c["card"],
            darkcolor=c["card"],
            focuscolor=c["card"],
            padding=(12, 7),
            font=self._font_lang(9, "bold"),
            relief="flat",
        )
        s.map(
            "Secondary.TButton",
            background=[("active", c["card_hover"])],
            bordercolor=[("active", c["accent"])],
        )

        s.configure(
            "TCheckbutton",
            background=c["card"],
            foreground=c["text"],
            focuscolor=c["card"],
            font=self._font_lang(9),
        )
        s.map("TCheckbutton", background=[("active", c["card"])])

        s.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=c["surface"],
            background=c["accent"],
            bordercolor=c["surface"],
            lightcolor=c["accent"],
            darkcolor=c["accent"],
            thickness=4,
        )

        s.configure(
            "Vertical.TScrollbar",
            background=c["scrollbar"],
            troughcolor=c["log_bg"],
            bordercolor=c["log_bg"],
            arrowcolor=c["text_sub"],
            lightcolor=c["scrollbar"],
            darkcolor=c["scrollbar"],
        )

    def _update_log_tags(self):
        c = self.colors
        self.log_text.config(
            bg=c["log_bg"],
            fg=c["log_fg"],
            insertbackground=c["log_fg"],
            highlightbackground=c["border"],
            font=self._font_mono(9),
        )
        self.log_text.tag_configure(
            "time", foreground=c["muted"], font=self._font_mono(8)
        )
        self.log_text.tag_configure("info", foreground=c["log_fg"])
        self.log_text.tag_configure("success", foreground=c["success"])
        self.log_text.tag_configure("warn", foreground=c["warning"])
        self.log_text.tag_configure("error", foreground=c["danger"])
        self.log_text.tag_configure("fa", font=self._font_lang(9, lang="fa"))
        self.log_text.tag_configure("en", font=self._font_lang(9, lang="en"))

    # ============================================================
    # Language & Fonts
    # ============================================================
    def _apply_language(self):
        self._apply_texts_recursive(self.root)
        self._apply_fonts_recursive(self.root)
        self._apply_alignment_recursive(self.root)
        self._apply_ttk_styles()
        self._update_log_tags()
        self._relayout()
        self._update_stats_bar()
        self._rerender_log()
        self._update_zoom_label()
        self._set_status(self._status_key, self._status_state)
        self._update_empty_state()

    def _apply_texts_recursive(self, w):
        key = getattr(w, "_text_key", None)
        if key:
            try:
                w.config(text=self._t(key))
            except tk.TclError:
                pass
        for child in w.winfo_children():
            self._apply_texts_recursive(child)

    def _apply_fonts_recursive(self, w):
        size = getattr(w, "_font_size", None)
        weight = getattr(w, "_font_weight", "normal")
        if size is not None:
            try:
                if isinstance(w, tk.Label):
                    txt = w.cget("text")
                    if txt:
                        w.config(font=self._font_for(txt, size, weight))
                    elif getattr(w, "_icon_name", None):
                        self._refresh_icon(w)
                elif isinstance(w, (tk.Entry, ttk.Entry)):
                    w.config(font=self._font_lang(size, weight))
            except tk.TclError:
                pass
        for child in w.winfo_children():
            self._apply_fonts_recursive(child)

    def _apply_alignment_recursive(self, w):
        rtl = self._rtl()
        anchor = "e" if rtl else "w"
        justify = "right" if rtl else "left"
        if isinstance(w, tk.Label):
            try:
                if str(w.cget("anchor")) in ("w", "e"):
                    w.config(anchor=anchor)
            except tk.TclError:
                pass
        elif isinstance(w, (tk.Entry, ttk.Entry, tk.Text)):
            try:
                w.config(justify=justify)
            except tk.TclError:
                pass
        for child in w.winfo_children():
            self._apply_alignment_recursive(child)

    def _relayout(self):
        rtl = self._rtl()
        for entry, btn in self._path_rows:
            entry.pack_forget()
            btn.pack_forget()
            if rtl:
                btn.pack(side=tk.LEFT, padx=(0, 8))
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                btn.pack(side=tk.LEFT, padx=(8, 0))

        for w in (
            self.start_btn,
            self.cancel_btn,
            self.open_btn,
            self.copy_btn,
            self.status_box,
            self.hint_lbl,
        ):
            w.pack_forget()

        if rtl:
            self.start_btn.pack(side=tk.RIGHT)
            self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 6))
            self.open_btn.pack(side=tk.RIGHT, padx=(0, 6))
            self.copy_btn.pack(side=tk.RIGHT, padx=(0, 6))
            self.status_box.pack(side=tk.RIGHT, padx=14)
            self.hint_lbl.pack(side=tk.LEFT)
        else:
            self.start_btn.pack(side=tk.LEFT)
            self.cancel_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.copy_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.status_box.pack(side=tk.LEFT, padx=14)
            self.hint_lbl.pack(side=tk.RIGHT)

        self.status_dot.pack_forget()
        self.status_label.pack_forget()
        if rtl:
            self.status_dot.pack(side=tk.RIGHT)
            self.status_label.pack(side=tk.RIGHT, padx=(0, 5))
        else:
            self.status_dot.pack(side=tk.LEFT)
            self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        self.log_title.pack_forget()
        self.clear_btn.pack_forget()
        if rtl:
            self.clear_btn.pack(side=tk.LEFT)
            self.log_title.pack(side=tk.RIGHT)
        else:
            self.log_title.pack(side=tk.LEFT)
            self.clear_btn.pack(side=tk.RIGHT)

        self._sync_action_visibility()

    def _sync_action_visibility(self):
        has_out = bool(self.output_var.get().strip())
        if self.running:
            self.open_btn.pack_forget()
            self.copy_btn.pack_forget()
        else:
            self.cancel_btn.pack_forget()
            if not has_out:
                self.open_btn.pack_forget()
                self.copy_btn.pack_forget()

    def _rerender_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for ts, key, kw, tag in self._log_entries:
            self._render_log_line(ts, key, kw, tag)
        self.log_text.see(tk.END)
        self._update_empty_state()

    def _render_log_line(self, ts, key, kw, tag):
        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
        self.log_text.insert(tk.END, time_str + "  ", ("time",))
        text = self._t(key, **kw) + "\n"
        lang_tag = "fa" if _has_persian(text) else "en"
        self.log_text.insert(tk.END, text, (tag, lang_tag))

    def _update_empty_state(self):
        if not self._log_entries:
            self.empty_overlay.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_overlay.place_forget()

    def _show_empty_log(self):
        self._update_empty_state()

    def _toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self._apply_theme()

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "fa" else "fa"
        self._apply_language()

    # ============================================================
    # Zoom
    # ============================================================
    def _zoom_in(self):
        if self.font_scale >= MAX_FONT_SCALE - 1e-6:
            return
        self.font_scale = min(MAX_FONT_SCALE, self.font_scale + FONT_SCALE_STEP)
        self._refresh_after_zoom()

    def _zoom_out(self):
        if self.font_scale <= MIN_FONT_SCALE + 1e-6:
            return
        self.font_scale = max(MIN_FONT_SCALE, self.font_scale - FONT_SCALE_STEP)
        self._refresh_after_zoom()

    def _zoom_reset(self):
        self.font_scale = 1.0
        self._refresh_after_zoom()

    def _refresh_after_zoom(self):
        self._apply_fonts_recursive(self.root)
        self._apply_ttk_styles()
        self._update_log_tags()
        self._rerender_log()
        self._update_zoom_label()
        self._refresh_header_icons()

    def _update_zoom_label(self):
        pct = int(round(self.font_scale * 100))
        self.zoom_lbl.config(text=f"{pct}%")

    # ============================================================
    # Browse / Clipboard / Folder
    # ============================================================
    def _browse_project(self):
        path = filedialog.askdirectory(title=self._t("dlg_project"))
        if path:
            self.project_var.set(path)
            if not self.output_var.get().strip():
                self.output_var.set(os.path.join(path, DEFAULT_OUTPUT_NAME))
            else:
                self.output_var.set(os.path.join(path, DEFAULT_OUTPUT_NAME))
            self._reset_validation()
            self._relayout()
            self._show_toast(self._t("toast_saved"), "success")

    def _browse_output(self):
        initial = self.project_var.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title=self._t("dlg_output"),
            initialdir=initial,
            initialfile=DEFAULT_OUTPUT_NAME,
            defaultextension=".txt",
            filetypes=[
                (self._t("dlg_ft_text"), "*.txt"),
                (self._t("dlg_ft_all"), "*.*"),
            ],
        )
        if path:
            self.output_var.set(path)
            self._reset_validation()
            self._relayout()

    def _copy_output_path(self):
        path = self.output_var.get().strip()
        if not path:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        self._show_toast(self._t("toast_copied"), "success")

    def _open_output_folder(self):
        path = self.output_var.get().strip()
        if not path:
            return
        folder = os.path.dirname(os.path.abspath(path)) or os.getcwd()
        if not os.path.isdir(folder):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}" >/dev/null 2>&1')
        except Exception:
            pass

    # ============================================================
    # Log / Stats / Status / Toast
    # ============================================================
    def _log(self, key, kw=None, tag="info"):
        kw = kw or {}
        self.root.after(0, self._append_log, key, dict(kw), tag)

    def _on_worker_stats(self, stats: dict):
        self.root.after(0, self._apply_worker_stats, stats)

    def _apply_worker_stats(self, stats: dict):
        self._stats = stats
        self._update_stats_bar()

    def _append_log(self, key, kw, tag):
        ts = time.time()
        self._log_entries.append((ts, key, kw, tag))
        self._render_log_line(ts, key, kw, tag)
        self.log_text.see(tk.END)
        self._update_empty_state()

    def _clear_log(self):
        self._log_entries.clear()
        self._stats = {"processed": 0, "skipped": 0, "bytes": 0}
        self._update_stats_bar()
        self.log_text.delete("1.0", tk.END)
        self._update_empty_state()

    def _set_status(self, key, state="idle"):
        self._status_key = key
        self._status_state = state
        c = self.colors
        color = {
            "idle": c["muted"],
            "running": c["accent"],
            "success": c["success"],
            "error": c["danger"],
        }.get(state, c["muted"])
        try:
            self.status_dot.config(fg=color)
            self.status_label.config(text=self._t(key))
        except tk.TclError:
            pass

    def _show_toast(self, text, kind="info"):
        c = self.colors
        color = {
            "info": c["accent"],
            "success": c["success"],
            "error": c["danger"],
        }.get(kind, c["accent"])
        self._hide_toast()
        toast = tk.Label(
            self.root,
            text=text,
            font=self._font_for(text, 9, "bold"),
            bg=color,
            fg="#ffffff",
            padx=18,
            pady=7,
        )
        toast.place(relx=0.5, y=82, anchor="n")
        self._toast_widget = toast
        self._toast_after_id = self.root.after(2400, self._hide_toast)

    def _hide_toast(self):
        if self._toast_after_id is not None:
            try:
                self.root.after_cancel(self._toast_after_id)
            except Exception:
                pass
            self._toast_after_id = None
        if self._toast_widget is not None:
            try:
                self._toast_widget.destroy()
            except tk.TclError:
                pass
            self._toast_widget = None

    # ============================================================
    # Validation / Run
    # ============================================================
    def _reset_validation(self):
        try:
            self.project_entry.config(style="TEntry")
            self.output_entry.config(style="TEntry")
        except tk.TclError:
            pass

    def _mark_error(self, entry):
        try:
            entry.config(style="Error.TEntry")
        except tk.TclError:
            pass

    def _on_escape(self):
        if self.running:
            self._cancel()
        else:
            self.root.destroy()

    def _start(self):
        if self.running:
            return

        self._reset_validation()

        project = self.project_var.get().strip()
        output = self.output_var.get().strip()

        if not project or not os.path.isdir(project):
            self._mark_error(self.project_entry)
            self._log("log_invalid_proj", {}, "error")
            self._set_status("status_error", "error")
            return

        if not output:
            self._mark_error(self.output_entry)
            self._log("log_invalid_out", {}, "error")
            self._set_status("status_error", "error")
            return

        raw = self.exclude_text.get("1.0", tk.END)
        patterns = [p.strip() for p in raw.replace(",", "\n").split("\n") if p.strip()]

        self.running = True
        self.cancel_event = threading.Event()
        self._stats = {"processed": 0, "skipped": 0, "bytes": 0}
        self._update_stats_bar()
        self.start_btn.config(state=tk.DISABLED)
        self._set_status("status_running", "running")
        self.progress.start(12)
        self._clear_log()
        self._relayout()

        if self._rtl():
            self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 6))
        else:
            self.cancel_btn.pack(side=tk.LEFT, padx=(6, 0))

        def worker():
            ok = False
            try:
                ok = create_snapshot(
                    project,
                    include_gitignore=self.use_gitignore_var.get(),
                    extra_patterns=patterns,
                    output_file_path=output,
                    log_func=self._log,
                    cancel_event=self.cancel_event,
                    on_stats=self._on_worker_stats,
                )
            except Exception as e:
                self._log("log_internal", {"err": str(e)}, "error")
            finally:
                self.root.after(0, self._finish, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _cancel(self):
        if self.cancel_event:
            self.cancel_event.set()
            self._set_status("status_running", "running")

    def _finish(self, ok: bool):
        cancelled = self.cancel_event.is_set() if self.cancel_event else False
        self.running = False
        self.cancel_event = None
        self.start_btn.config(state=tk.NORMAL)
        self.progress.stop()
        self.cancel_btn.pack_forget()

        if cancelled:
            self._set_status("status_cancelled", "idle")
            return

        if ok:
            self._set_status("status_success", "success")
            if self._rtl():
                self.open_btn.pack(side=tk.RIGHT, padx=(0, 6))
                self.copy_btn.pack(side=tk.RIGHT, padx=(0, 6))
            else:
                self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
                self.copy_btn.pack(side=tk.LEFT, padx=(6, 0))
        else:
            self._set_status("status_error", "error")
