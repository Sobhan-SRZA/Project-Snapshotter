"""Tkinter UI for Project Snapshotter."""

import os
import sys
import time
import threading
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
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
)
from core.themes import PALETTES, resolve_theme
from core.strings import STRINGS
from core.fonts import FontManager
from core.snapshot_engine import create_snapshot


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

        self.font_ui = font_mgr.pick_ui_font()
        self.font_mono = font_mgr.pick_mono_font()

        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self._build_ui()
        self._apply_theme()
        self._apply_language()
        self._show_empty_log()

        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<Control-l>", lambda e: self._toggle_lang())
        self.root.bind("<F5>", lambda e: self._start())
        self.root.bind("<Control-Return>", lambda e: self._start())
        self.root.bind("<Escape>", lambda e: self._on_escape())

    # ---- helpers ----
    def _t(self, key, **kw):
        tpl = STRINGS[self.lang].get(key, key)
        try:
            return tpl.format(**kw) if kw else tpl
        except (KeyError, IndexError):
            return tpl

    def _rtl(self):
        return self.lang == "fa"

    def _font(self, size, weight="normal"):
        return (self.font_ui, size, weight)

    # ============================================================
    # Build UI
    # ============================================================
    def _build_ui(self):
        # --- Header ---
        self.header = tk.Frame(self.root, height=72)
        self.header._role = "header"
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        self.title_block = tk.Frame(self.header)
        self.title_block._role = "header"
        self.title_block.pack(side=tk.LEFT, padx=24, pady=14)

        self.title_lbl = tk.Label(self.title_block, font=self._font(16, "bold"))
        self.title_lbl._text_key = "app_title"
        self.title_lbl._role = "title"
        self.title_lbl.pack(anchor=tk.W)

        self.subtitle_lbl = tk.Label(self.title_block, font=self._font(10))
        self.subtitle_lbl._text_key = "app_subtitle"
        self.subtitle_lbl._role = "subtitle"
        self.subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        self.actions = tk.Frame(self.header)
        self.actions._role = "header"
        self.actions.pack(side=tk.RIGHT, padx=20)

        self.theme_btn = self._make_ghost_icon(
            self.actions, self._toggle_theme, role="ghost_btn"
        )
        self.theme_btn.pack(side=tk.RIGHT, padx=(0, 6))

        self.lang_btn = tk.Label(
            self.actions, font=self._font(10, "bold"), padx=14, pady=8, cursor="hand2"
        )
        self.lang_btn._role = "ghost_btn"
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 6))
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_lang())
        self._attach_hover(self.lang_btn, "ghost_btn")

        self.header_line = tk.Frame(self.root, height=1)
        self.header_line._role = "separator"
        self.header_line.pack(fill=tk.X)

        # --- Body ---
        body = tk.Frame(self.root)
        body._role = "surface"
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        self._build_paths_card(body)
        self._build_ignore_card(body)
        self._build_action_row(body)
        self._build_log_card(body)
        self._build_footer()

    def _make_ghost_icon(self, parent, command, role="ghost_btn") -> tk.Label:
        lbl = tk.Label(parent, font=self._font(14), padx=12, pady=6, cursor="hand2")
        lbl._role = role
        lbl.bind("<Button-1>", lambda e: command())
        self._attach_hover(lbl, role)
        return lbl

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

    def _section_title(self, parent, key):
        f = tk.Frame(parent)
        f._role = "card"
        f.pack(fill=tk.X, pady=(0, 12))
        lbl = tk.Label(f, font=self._font(11, "bold"), anchor=tk.W)
        lbl._text_key = key
        lbl._role = "card_title"
        lbl.pack(side=tk.LEFT)
        return f

    def _build_paths_card(self, parent):
        card = self._card(parent)
        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=20, pady=18)

        self._section_title(inner, "section_paths")

        self.lbl_project = tk.Label(inner, font=self._font(9), anchor=tk.W)
        self.lbl_project._text_key = "project_path"
        self.lbl_project._role = "field_label"
        self.lbl_project.pack(fill=tk.X, pady=(0, 6))

        self.row_project = tk.Frame(inner)
        self.row_project._role = "card"
        self.row_project.pack(fill=tk.X)

        self.project_var = tk.StringVar()
        self.project_entry = ttk.Entry(
            self.row_project,
            textvariable=self.project_var,
            font=self._font(10),
            style="TEntry",
        )
        self.browse_btn1 = ttk.Button(
            self.row_project, style="Secondary.TButton", command=self._browse_project
        )
        self.browse_btn1._text_key = "browse"

        self.lbl_output = tk.Label(inner, font=self._font(9), anchor=tk.W)
        self.lbl_output._text_key = "output_path"
        self.lbl_output._role = "field_label"
        self.lbl_output.pack(fill=tk.X, pady=(14, 6))

        self.row_output = tk.Frame(inner)
        self.row_output._role = "card"
        self.row_output.pack(fill=tk.X)

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(
            self.row_output,
            textvariable=self.output_var,
            font=self._font(10),
            style="TEntry",
        )
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
        inner.pack(fill=tk.X, padx=20, pady=18)

        self._section_title(inner, "section_ignore")

        self.use_gitignore_var = tk.BooleanVar(value=DEFAULT_USE_GITIGNORE)
        self.gitignore_cb = ttk.Checkbutton(
            inner, variable=self.use_gitignore_var, style="TCheckbutton"
        )
        self.gitignore_cb._text_key = "use_gitignore"
        self.gitignore_cb.pack(anchor=tk.W, pady=(0, 12))

        lbl = tk.Label(inner, font=self._font(9), anchor=tk.W)
        lbl._text_key = "manual_patterns"
        lbl._role = "field_label"
        lbl.pack(fill=tk.X, pady=(0, 6))

        self.exclude_text = tk.Text(
            inner,
            height=3,
            wrap=tk.WORD,
            font=(self.font_mono, 10),
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=8,
            highlightthickness=1,
        )
        self.exclude_text._role = "text_input"
        self.exclude_text.pack(fill=tk.X)

        self.pattern_ph = self.exclude_text
        self._pattern_hint = tk.Label(inner, font=self._font(8), anchor=tk.W)
        self._pattern_hint._text_key = "pattern_hint"
        self._pattern_hint._role = "hint"
        self._pattern_hint.pack(fill=tk.X, pady=(6, 0))

    def _build_action_row(self, parent):
        self.action_row = tk.Frame(parent)
        self.action_row._role = "surface"
        self.action_row.pack(fill=tk.X, pady=(0, 12))

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

        self.status_box = tk.Frame(self.action_row)
        self.status_box._role = "surface"
        self.status_dot = tk.Label(self.status_box, text="●", font=self._font(11))
        self.status_dot._role = "status_dot"
        self.status_label = tk.Label(self.status_box, font=self._font(9))
        self.status_label._role = "status_text"

        self.hint_lbl = tk.Label(self.action_row, font=self._font(8))
        self.hint_lbl._text_key = "btn_hint"
        self.hint_lbl._role = "hint_surface"

        self.progress = ttk.Progressbar(
            parent, mode="indeterminate", style="Accent.Horizontal.TProgressbar"
        )
        self.progress.pack(fill=tk.X, pady=(0, 12))

    def _build_log_card(self, parent):
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

        head = tk.Frame(inner)
        head._role = "card"
        head.pack(fill=tk.X, pady=(0, 10))

        self.log_title = tk.Label(head, font=self._font(11, "bold"), anchor=tk.W)
        self.log_title._text_key = "log_title"
        self.log_title._role = "card_title"

        self.clear_btn = tk.Label(head, font=self._font(9), cursor="hand2")
        self.clear_btn._text_key = "log_clear"
        self.clear_btn._role = "ghost_small"
        self.clear_btn.bind("<Button-1>", lambda e: self._clear_log())
        self._attach_hover_small(self.clear_btn)

        text_container = tk.Frame(inner)
        text_container._role = "card"
        text_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            text_container,
            wrap=tk.WORD,
            font=(self.font_mono, 9),
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            highlightthickness=1,
            height=14,
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

        self.empty_overlay = tk.Frame(text_container)
        self.empty_overlay._role = "log"
        self.empty_title = tk.Label(self.empty_overlay, font=self._font(11, "bold"))
        self.empty_title._text_key = "log_empty"
        self.empty_title._role = "empty_title"
        self.empty_title.pack(pady=(0, 4))
        self.empty_sub = tk.Label(self.empty_overlay, font=self._font(9))
        self.empty_sub._text_key = "log_empty_sub"
        self.empty_sub._role = "empty_sub"
        self.empty_sub.pack()

    # ------------------------------------------------------------
    # FOOTER — با اطلاعات نویسنده و لینک‌های کلیک‌پذیر
    # ------------------------------------------------------------
    def _build_footer(self):
        self.footer = tk.Frame(self.root, height=32)
        self.footer._role = "footer"
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        # چپ: کلیدهای میانبر
        self.footer_hint = tk.Label(self.footer, font=self._font(8))
        self.footer_hint._text_key = "footer_hint"
        self.footer_hint._role = "footer_text"
        self.footer_hint.pack(side=tk.LEFT, padx=(20, 0))

        # راست: نسخه
        self.version_lbl = tk.Label(
            self.footer, text=f"v{APP_VERSION}", font=self._font(8)
        )
        self.version_lbl._role = "footer_text"
        self.version_lbl.pack(side=tk.RIGHT, padx=(0, 20))

        # راست (داخلی): بلوک نویسنده
        self.author_frame = tk.Frame(self.footer)
        self.author_frame._role = "footer"
        self.author_frame.pack(side=tk.RIGHT, padx=(0, 16))

        self.copyright_lbl = tk.Label(
            self.author_frame,
            text=f"© {COPYRIGHT_YEAR} {AUTHOR_NAME} · {AUTHOR_TEAM}",
            font=self._font(8),
        )
        self.copyright_lbl._role = "footer_text"
        self.copyright_lbl.pack(side=tk.LEFT)

        self._footer_sep(self.author_frame)

        # GitHub (قابل کلیک)
        self.github_link = tk.Label(
            self.author_frame,
            text=GITHUB_DISPLAY,
            font=self._font(8, "bold"),
            cursor="hand2",
        )
        self.github_link._role = "footer_link"
        self.github_link.pack(side=tk.LEFT)
        self.github_link.bind("<Button-1>", lambda e: self._open_url(GITHUB_URL))
        self._setup_link_hover(self.github_link)

        self._footer_sep(self.author_frame)

        # Website (قابل کلیک)
        self.site_link = tk.Label(
            self.author_frame,
            text=WEBSITE_DISPLAY,
            font=self._font(8, "bold"),
            cursor="hand2",
        )
        self.site_link._role = "footer_link"
        self.site_link.pack(side=tk.LEFT)
        self.site_link.bind("<Button-1>", lambda e: self._open_url(WEBSITE_URL))
        self._setup_link_hover(self.site_link)

    def _footer_sep(self, parent):
        sep = tk.Label(parent, text=" · ", font=self._font(8))
        sep._role = "footer_text"
        sep.pack(side=tk.LEFT)

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _ensure_link_fonts(self):
        if hasattr(self, "_link_fonts"):
            return self._link_fonts
        try:
            base = tkfont.Font(family=self.font_ui, size=8, weight="bold")
        except tk.TclError:
            base = tkfont.Font(size=8, weight="bold")
        hover = tkfont.Font(font=base)
        hover.configure(underline=True)
        self._link_fonts = (base, hover)
        return self._link_fonts

    def _setup_link_hover(self, w):
        base, hover = self._ensure_link_fonts()
        w.config(font=base)

        def on_enter(_e):
            w.config(fg=self.colors["accent_hover"], font=hover)

        def on_leave(_e):
            w.config(fg=self.colors["accent"], font=base)

        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

    def _attach_hover_small(self, w):
        def on_enter(_e):
            w.config(bg=self.colors["card_hover"])

        def on_leave(_e):
            w.config(bg=self.colors["card"])

        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

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

        # اگر کاربر روی لینک‌ها hover بود، فونت را ریست کن
        if hasattr(self, "_link_fonts"):
            base, _ = self._link_fonts
            for w in (self.github_link, self.site_link):
                try:
                    w.config(font=base)
                except (AttributeError, tk.TclError):
                    pass

        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark")
        )
        if hasattr(self, "_status_key"):
            self._set_status(self._status_key, self._status_state)
        if self._toast_widget is not None:
            self._hide_toast()

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
            "card": dict(bg=c["card"], highlightbackground=c["border"]),
            "separator": dict(bg=c["border"]),
            "footer": dict(bg=c["surface"]),
            "title": dict(bg=c["header"], fg=c["text"]),
            "subtitle": dict(bg=c["header"], fg=c["text_sub"]),
            "card_title": dict(bg=c["card"], fg=c["text"]),
            "field_label": dict(bg=c["card"], fg=c["text_sub"]),
            "hint": dict(bg=c["card"], fg=c["muted"]),
            "hint_surface": dict(bg=c["surface"], fg=c["muted"]),
            "footer_text": dict(bg=c["surface"], fg=c["muted"]),
            "footer_link": dict(bg=c["surface"], fg=c["accent"]),
            "ghost_btn": dict(bg=c["header"], fg=c["text"]),
            "ghost_small": dict(bg=c["card"], fg=c["accent"]),
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
            padding=(10, 8),
            relief="flat",
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
            padding=(20, 10),
            font=self._font(10, "bold"),
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
            padding=(14, 8),
            font=self._font(9),
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
            font=self._font(9),
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
        )
        self.log_text.tag_configure("time", foreground=c["muted"])
        self.log_text.tag_configure("info", foreground=c["log_fg"])
        self.log_text.tag_configure("success", foreground=c["success"])
        self.log_text.tag_configure("warn", foreground=c["warning"])
        self.log_text.tag_configure("error", foreground=c["danger"])

    # ============================================================
    # Language
    # ============================================================
    def _apply_language(self):
        self._apply_texts_recursive(self.root)
        self._apply_alignment_recursive(self.root)
        self._relayout()
        self._rerender_log()
        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark")
        )
        self.lang_btn.config(text=self._t("lang_btn"))
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

    def _apply_alignment_recursive(self, w):
        rtl = self._rtl()
        anchor = "e" if rtl else "w"
        justify = "right" if rtl else "left"
        if isinstance(w, tk.Label):
            try:
                cur = str(w.cget("anchor"))
                if cur in ("w", "e"):
                    w.config(anchor=anchor)
            except tk.TclError:
                pass
        elif isinstance(w, (tk.Entry, ttk.Entry)):
            try:
                w.config(justify=justify)
            except tk.TclError:
                pass
        elif isinstance(w, tk.Text):
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
            self.status_box,
            self.hint_lbl,
        ):
            w.pack_forget()
        if rtl:
            self.start_btn.pack(side=tk.RIGHT)
            self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 6))
            self.open_btn.pack(side=tk.RIGHT, padx=(0, 6))
            self.status_box.pack(side=tk.RIGHT, padx=18)
            self.hint_lbl.pack(side=tk.LEFT)
        else:
            self.start_btn.pack(side=tk.LEFT)
            self.cancel_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
            self.status_box.pack(side=tk.LEFT, padx=18)
            self.hint_lbl.pack(side=tk.RIGHT)

        self.status_dot.pack_forget()
        self.status_label.pack_forget()
        if rtl:
            self.status_dot.pack(side=tk.RIGHT)
            self.status_label.pack(side=tk.RIGHT, padx=(0, 6))
        else:
            self.status_dot.pack(side=tk.LEFT)
            self.status_label.pack(side=tk.LEFT, padx=(6, 0))

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
        if self.running:
            self.cancel_btn.pack()
            self.open_btn.pack_forget()
        elif self.open_btn.winfo_manager() and not self._last_output_ok():
            self.open_btn.pack_forget()

    def _last_output_ok(self):
        return False

    def _rerender_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        for ts, key, kw, tag in self._log_entries:
            time_str = time.strftime("%H:%M:%S", time.localtime(ts))
            self.log_text.insert(tk.END, time_str + "  ", "time")
            self.log_text.insert(tk.END, self._t(key, **kw) + "\n", tag)
        self.log_text.see(tk.END)
        self._update_empty_state()

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
    # Browse / dialog
    # ============================================================
    def _browse_project(self):
        path = filedialog.askdirectory(title=self._t("dlg_project"))
        if path:
            self.project_var.set(path)
            self.output_var.set(os.path.join(path, DEFAULT_OUTPUT_NAME))
            self._reset_validation()
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
    # Log / status / toast
    # ============================================================
    def _log(self, key, kw=None, tag="info"):
        kw = kw or {}
        self.root.after(0, self._append_log, key, dict(kw), tag)

    def _append_log(self, key, kw, tag):
        ts = time.time()
        self._log_entries.append((ts, key, kw, tag))
        time_str = time.strftime("%H:%M:%S", time.localtime(ts))
        self.log_text.insert(tk.END, time_str + "  ", "time")
        self.log_text.insert(tk.END, self._t(key, **kw) + "\n", tag)
        self.log_text.see(tk.END)
        self._update_empty_state()

    def _clear_log(self):
        self._log_entries.clear()
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
        if self._toast_widget is not None:
            try:
                self._toast_widget.destroy()
            except tk.TclError:
                pass
        toast = tk.Label(
            self.root,
            text=text,
            font=self._font(9, "bold"),
            bg=color,
            fg="#ffffff",
            padx=18,
            pady=8,
        )
        toast.place(relx=0.5, y=88, anchor="n")
        self._toast_widget = toast
        self.root.after(2400, lambda: self._hide_toast())

    def _hide_toast(self):
        if self._toast_widget is not None:
            try:
                self._toast_widget.destroy()
            except tk.TclError:
                pass
            self._toast_widget = None

    # ============================================================
    # Validation
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

    # ============================================================
    # Run / cancel
    # ============================================================
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
        self.start_btn.config(state=tk.DISABLED)
        self._set_status("status_running", "running")
        self.progress.start(12)
        self._clear_log()

        self.open_btn.pack_forget()
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
            else:
                self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
        else:
            self._set_status("status_error", "error")
