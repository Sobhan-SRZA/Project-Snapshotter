"""
Project Snapshotter GUI — با تم روز و شب

موتور .gitignore سازگار با Git (negation, anchoring, **, [], escape,
nested .gitignore, first-prune semantics) + رابط گرافیکی مدرن.
"""

import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from typing import List, Optional

# ============================================================
# فونت‌ها و پالت رنگ
# ============================================================

if sys.platform.startswith("win"):
    FONT_UI = "Segoe UI"
    FONT_MONO = "Consolas"
elif sys.platform == "darwin":
    FONT_UI = "SF Pro Text"
    FONT_MONO = "Menlo"
else:
    FONT_UI = "Ubuntu"
    FONT_MONO = "Monospace"

PALETTES = {
    "light": {
        "bg": "#f2f3f5",
        "header": "#ffffff",
        "card": "#ffffff",
        "border": "#dcdfe4",
        "text": "#1d1d1f",
        "muted": "#6b7280",
        "accent": "#0071e3",
        "accent_hover": "#0077ed",
        "accent_fg": "#ffffff",
        "input_bg": "#fafbfc",
        "log_bg": "#fafbfc",
        "log_fg": "#24292f",
        "success": "#16a34a",
        "warn": "#d97706",
        "error": "#dc2626",
        "scrollbar": "#c1c5cc",
    },
    "dark": {
        "bg": "#1b1c1f",
        "header": "#232428",
        "card": "#2a2b30",
        "border": "#3a3b40",
        "text": "#e6e7ea",
        "muted": "#9a9ba0",
        "accent": "#0a84ff",
        "accent_hover": "#3d9dff",
        "accent_fg": "#ffffff",
        "input_bg": "#202126",
        "log_bg": "#16171a",
        "log_fg": "#d4d6db",
        "success": "#30d158",
        "warn": "#ffb020",
        "error": "#ff453a",
        "scrollbar": "#4a4b50",
    },
}


def detect_system_theme() -> str:
    """تشخیص تم سیستم در ویندوز (پیش‌فرض: light)."""
    try:
        if sys.platform.startswith("win"):
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
    except Exception:
        pass
    return "light"


# ============================================================
# موتور .gitignore سازگار با Git
# ============================================================


class GitIgnorePattern:
    __slots__ = ("original", "negation", "directory_only", "anchored", "regex", "valid")

    def __init__(self, line: str):
        self.original = line
        self.negation = False
        self.directory_only = False
        self.anchored = False
        self.regex: Optional[re.Pattern] = None
        self.valid = True
        self._compile(line)

    def _compile(self, line: str):
        p = line
        if not p or p.startswith("#"):
            self.valid = False
            return
        if p.startswith("!"):
            self.negation = True
            p = p[1:]
        elif p.startswith("\\!") or p.startswith("\\#"):
            p = p[1:]

        p = self._rstrip_unescaped_spaces(p)
        if not p:
            self.valid = False
            return

        if p.endswith("/"):
            self.directory_only = True
            p = p[:-1]
            if not p:
                self.valid = False
                return

        if p.startswith("/"):
            self.anchored = True
            p = p[1:]
        elif "/" in p:
            self.anchored = True

        body = self._translate(p)
        if not self.anchored:
            body = "(?:.*/)?" + body

        try:
            self.regex = re.compile("^" + body + "$")
        except re.error:
            self.valid = False

    @staticmethod
    def _rstrip_unescaped_spaces(p: str) -> str:
        while p.endswith(" "):
            j, bs = len(p) - 2, 0
            while j >= 0 and p[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 1:
                break
            p = p[:-1]
        return p

    @staticmethod
    def _translate(p: str) -> str:
        i, n, out = 0, len(p), []
        while i < n:
            c = p[i]
            if c == "*":
                if i + 1 < n and p[i + 1] == "*":
                    if i + 2 < n and p[i + 2] == "/":
                        out.append("(?:.*/)?")
                        i += 3
                    elif i + 2 == n:
                        out.append(".*")
                        i += 2
                    else:
                        out.append("[^/]*")
                        i += 2
                else:
                    out.append("[^/]*")
                    i += 1
            elif c == "?":
                out.append("[^/]")
                i += 1
            elif c == "[":
                j = i + 1
                if j < n and p[j] in ("!", "^"):
                    j += 1
                if j < n and p[j] == "]":
                    j += 1
                while j < n and p[j] != "]":
                    j += 1
                if j >= n:
                    out.append(re.escape(c))
                    i += 1
                else:
                    inner = p[i + 1 : j]
                    if inner.startswith("!"):
                        inner = "^" + inner[1:]
                    out.append("[" + inner + "]")
                    i = j + 1
            elif c == "\\":
                if i + 1 < n:
                    out.append(re.escape(p[i + 1]))
                    i += 2
                else:
                    out.append(re.escape(c))
                    i += 1
            else:
                out.append(re.escape(c))
                i += 1
        return "".join(out)

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if not self.valid or self.regex is None:
            return False
        if self.directory_only and not is_dir:
            return False
        return self.regex.match(rel_path) is not None


def parse_gitignore_file(path: str) -> List[GitIgnorePattern]:
    patterns = []
    if not os.path.isfile(path):
        return patterns
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.rstrip("\r\n")
                r = GitIgnorePattern(line)
                if r.valid:
                    patterns.append(r)
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
    return patterns


class GitIgnoreMatcher:
    def __init__(self, rules: Optional[List[GitIgnorePattern]] = None):
        self.rules = list(rules) if rules else []

    def copy(self) -> "GitIgnoreMatcher":
        return GitIgnoreMatcher(self.rules)

    def add(self, rules: List[GitIgnorePattern]):
        self.rules.extend(rules)

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        ignored = False
        for rule in self.rules:
            if rule.matches(rel_path, is_dir):
                ignored = not rule.negation
        return ignored


def build_default_matcher() -> GitIgnoreMatcher:
    defaults = [
        ".git/",
        "node_modules/",
        "__pycache__/",
        "*.pyc",
        "*.tmp",
        "venv/",
        ".venv/",
        ".vscode/",
        ".idea/",
        "dist/",
        "build/",
        ".DS_Store",
    ]
    return GitIgnoreMatcher(
        [r for r in (GitIgnorePattern(l) for l in defaults) if r.valid]
    )


# ============================================================
# منطق ساخت اسنپ‌شات
# ============================================================


def create_snapshot(
    root_dir: str,
    include_gitignore: bool,
    extra_patterns: List[str],
    output_file_path: str,
    log_func=print,
) -> bool:
    output_abs = os.path.abspath(output_file_path)
    base = build_default_matcher()
    manual = [r for r in (GitIgnorePattern(l) for l in extra_patterns) if r.valid]
    base.add(manual)
    if manual:
        log_func(f"➕ {len(manual)} الگوی دستی اضافه شد.", "info")

    all_contents: List[str] = []
    stats = {"processed": 0, "skipped": 0}

    log_func("🚀 شروع پیمایش...", "info")

    def walk(dir_path: str, rel_dir: str, matcher: GitIgnoreMatcher):
        current = matcher
        if include_gitignore:
            gi = os.path.join(dir_path, ".gitignore")
            if os.path.isfile(gi):
                rules = parse_gitignore_file(gi)
                if rules:
                    current = matcher.copy()
                    current.add(rules)
                    rel_gi = f"{rel_dir}/.gitignore" if rel_dir else ".gitignore"
                    log_func(f"📄 {len(rules)} الگو از {rel_gi}", "info")

        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except (PermissionError, OSError) as e:
            log_func(f"⚠️ دسترسی به {dir_path} ممکن نیست: {e}", "warn")
            return

        for entry in entries:
            name, full = entry.name, entry.path
            rel = f"{rel_dir}/{name}" if rel_dir else name

            try:
                is_dir = entry.is_dir()
            except OSError:
                stats["skipped"] += 1
                continue

            if not is_dir and os.path.abspath(full) == output_abs:
                continue

            if current.is_ignored(rel, is_dir):
                stats["skipped"] += 1
                continue

            if is_dir:
                walk(full, rel, current)
            else:
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read()
                    all_contents.append(f"{rel}\n```\n{content}\n```\n\n")
                    stats["processed"] += 1
                    if stats["processed"] % 50 == 0:
                        log_func(f"⏳ {stats['processed']} فایل پردازش شد...", "info")
                except UnicodeDecodeError:
                    stats["skipped"] += 1
                except (IOError, OSError) as e:
                    log_func(f"❌ خطا در {rel}: {e}", "error")
                    stats["skipped"] += 1

    try:
        walk(root_dir, "", base)
    except Exception as e:
        log_func(f"❌ خطای غیرمنتظره: {e}", "error")
        return False

    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_contents))
        log_func(
            f"✅ تمام شد! {stats['processed']} فایل نوشته شد، "
            f"{stats['skipped']} مورد رد شد.",
            "success",
        )
        log_func(f"📁 خروجی: {output_file_path}", "success")
        return True
    except Exception as e:
        log_func(f"❌ خطای بحرانی در نوشتن: {e}", "error")
        return False


# ============================================================
# رابط گرافیکی
# ============================================================


class SnapshotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = detect_system_theme()
        self.colors = PALETTES[self.theme]
        self.running = False

        self.root.title("Project Snapshotter")
        self.root.geometry("960x880")
        self.root.minsize(800, 720)

        self._build_ui()
        self._apply_theme()

        # میانبرهای کیبورد
        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<F5>", lambda e: self._start())
        self.root.bind("<Control-Return>", lambda e: self._start())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    # ---------- ساخت UI ----------

    def _build_ui(self):
        # هدر
        self.header = tk.Frame(self.root, height=64)
        self.header.pack(fill=tk.X)
        self.header._role = "header"
        self.header.pack_propagate(False)

        title_box = tk.Frame(self.header)
        title_box._role = "header"
        title_box.pack(side=tk.LEFT, padx=20, pady=10)

        self.title_lbl = tk.Label(
            title_box, text="📸  Project Snapshotter", font=(FONT_UI, 15, "bold")
        )
        self.title_lbl._role = "title"
        self.title_lbl.pack(anchor=tk.W)

        self.subtitle_lbl = tk.Label(
            title_box, text="اسنپ‌شات از فایل‌های متنی پروژه", font=(FONT_UI, 9)
        )
        self.subtitle_lbl._role = "subtitle"
        self.subtitle_lbl.pack(anchor=tk.W)

        # دکمه تم
        self.theme_btn = tk.Label(
            self.header,
            text=self._theme_btn_text(),
            font=(FONT_UI, 10),
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.theme_btn._role = "ghost_btn"
        self.theme_btn.pack(side=tk.RIGHT, padx=20)
        self.theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())

        # خط جداکننده زیر هدر
        self.header_line = tk.Frame(self.root, height=1)
        self.header_line._role = "separator"
        self.header_line.pack(fill=tk.X)

        # بدنه
        body = tk.Frame(self.root)
        body._role = "bg"
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        # کارت مسیرها
        self._build_paths_card(body)

        # کارت تنظیمات
        self._build_options_card(body)

        # نوار اجرا
        self._build_action_bar(body)

        # کارت لاگ
        self._build_log_card(body)

    def _make_card(self, parent) -> tk.Frame:
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        return card

    def _build_paths_card(self, parent):
        card = self._make_card(parent)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=16, pady=14)

        # --- مسیر پروژه ---
        lbl = tk.Label(inner, text="مسیر پروژه", font=(FONT_UI, 9, "bold"), anchor=tk.W)
        lbl._role = "card_title"
        lbl.pack(fill=tk.X, pady=(0, 4))

        row = tk.Frame(inner)
        row._role = "card"
        row.pack(fill=tk.X)
        self.project_var = tk.StringVar()
        self.project_entry = ttk.Entry(
            row, textvariable=self.project_var, font=(FONT_UI, 10)
        )
        self.project_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_btn1 = ttk.Button(
            row,
            text="انتخاب پوشه",
            style="Secondary.TButton",
            command=self._browse_project,
        )
        self.browse_btn1.pack(side=tk.LEFT, padx=(8, 0))

        # --- مسیر خروجی ---
        lbl2 = tk.Label(
            inner, text="مسیر فایل خروجی", font=(FONT_UI, 9, "bold"), anchor=tk.W
        )
        lbl2._role = "card_title"
        lbl2.pack(fill=tk.X, pady=(12, 4))

        row2 = tk.Frame(inner)
        row2._role = "card"
        row2.pack(fill=tk.X)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(
            row2, textvariable=self.output_var, font=(FONT_UI, 10)
        )
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_btn2 = ttk.Button(
            row2,
            text="ذخیره در...",
            style="Secondary.TButton",
            command=self._browse_output,
        )
        self.browse_btn2.pack(side=tk.LEFT, padx=(8, 0))

        hint = tk.Label(
            inner,
            text="به‌طور پیش‌فرض کنار پروژه ذخیره می‌شود. مسیر را می‌توانید تغییر دهید.",
            font=(FONT_UI, 8),
            anchor=tk.W,
        )
        hint._role = "hint"
        hint.pack(fill=tk.X, pady=(8, 0))

    def _build_options_card(self, parent):
        card = self._make_card(parent)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=16, pady=14)

        title = tk.Label(
            inner, text="تنظیمات ignore", font=(FONT_UI, 9, "bold"), anchor=tk.W
        )
        title._role = "card_title"
        title.pack(fill=tk.X, pady=(0, 8))

        self.use_gitignore_var = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(
            inner,
            variable=self.use_gitignore_var,
            text="اعمال .gitignore ها (شامل زیرپوشه‌ها، سازگار با Git)",
        )
        cb.pack(anchor=tk.W)

        lbl = tk.Label(
            inner,
            text="الگوهای دستی (هر خط یک الگو، یا با کاما):",
            font=(FONT_UI, 9),
            anchor=tk.W,
        )
        lbl._role = "card_title"
        lbl.pack(fill=tk.X, pady=(12, 4))

        self.exclude_text = tk.Text(
            inner,
            height=3,
            wrap=tk.WORD,
            font=(FONT_MONO, 10),
            relief=tk.FLAT,
            borderwidth=0,
            padx=8,
            pady=6,
            highlightthickness=1,
        )
        self.exclude_text._role = "text_input"
        self.exclude_text.pack(fill=tk.X)

        hint = tk.Label(
            inner,
            text="پشتیبانی: !negation   dir/   /anchored   **   ?   []   \\escape",
            font=(FONT_UI, 8),
            anchor=tk.W,
        )
        hint._role = "hint"
        hint.pack(fill=tk.X, pady=(6, 0))

    def _build_action_bar(self, parent):
        bar = tk.Frame(parent)
        bar._role = "bg"
        bar.pack(fill=tk.X, pady=(0, 12))

        self.start_btn = ttk.Button(
            bar, text="🚀  شروع اسنپ‌شات", style="Primary.TButton", command=self._start
        )
        self.start_btn.pack(side=tk.LEFT)

        status_box = tk.Frame(bar)
        status_box._role = "bg"
        status_box.pack(side=tk.LEFT, padx=16)

        self.status_dot = tk.Label(status_box, text="●", font=(FONT_UI, 12))
        self.status_dot._role = "status_dot"
        self.status_dot.pack(side=tk.LEFT)

        self.status_label = tk.Label(status_box, text="آماده", font=(FONT_UI, 9))
        self.status_label._role = "status_text"
        self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        hint = tk.Label(
            bar, text="F5 برای اجرا  •  Ctrl+T تم  •  Esc خروج", font=(FONT_UI, 8)
        )
        hint._role = "hint_bg"
        hint.pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(
            parent, mode="indeterminate", style="Accent.Horizontal.TProgressbar"
        )
        self.progress.pack(fill=tk.X, pady=(0, 12))

    def _build_log_card(self, parent):
        card = self._make_card(parent)
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        head = tk.Frame(inner)
        head._role = "card"
        head.pack(fill=tk.X, pady=(0, 6))

        lbl = tk.Label(
            head, text="گزارش عملیات", font=(FONT_UI, 9, "bold"), anchor=tk.W
        )
        lbl._role = "card_title"
        lbl.pack(side=tk.LEFT)

        clear_btn = tk.Label(head, text="پاک کردن", font=(FONT_UI, 8), cursor="hand2")
        clear_btn._role = "ghost_btn_small"
        clear_btn.pack(side=tk.RIGHT)
        clear_btn.bind("<Button-1>", lambda e: self.log_text.delete("1.0", tk.END))

        text_frame = tk.Frame(inner)
        text_frame._role = "card"
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=(FONT_MONO, 9),
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=8,
            highlightthickness=1,
            height=14,
        )
        self.log_text._role = "log"

        self.log_scroll = ttk.Scrollbar(
            text_frame,
            orient=tk.VERTICAL,
            command=self.log_text.yview,
            style="Vertical.TScrollbar",
        )
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ---------- اعمال تم ----------

    def _apply_theme(self):
        self.colors = PALETTES[self.theme]
        c = self.colors
        self.root.config(bg=c["bg"])
        self._apply_ttk_styles()
        self._apply_roles_recursive(self.root)
        self._update_log_tags()
        self.theme_btn.config(text=self._theme_btn_text())

    def _apply_roles_recursive(self, widget):
        role = getattr(widget, "_role", None)
        if role:
            self._apply_role(widget, role)
        for child in widget.winfo_children():
            self._apply_roles_recursive(child)

    def _apply_role(self, w, role: str):
        c = self.colors
        try:
            if role == "bg":
                w.config(bg=c["bg"])
            elif role == "header":
                w.config(bg=c["header"])
            elif role == "card":
                w.config(bg=c["card"], highlightbackground=c["border"])
            elif role == "separator":
                w.config(bg=c["border"])
            elif role == "title":
                w.config(bg=c["header"], fg=c["text"])
            elif role == "subtitle":
                w.config(bg=c["header"], fg=c["muted"])
            elif role == "card_title":
                w.config(bg=c["card"], fg=c["text"])
            elif role == "hint":
                w.config(bg=c["card"], fg=c["muted"])
            elif role == "hint_bg":
                w.config(bg=c["bg"], fg=c["muted"])
            elif role == "ghost_btn":
                w.config(bg=c["header"], fg=c["accent"])
            elif role == "ghost_btn_small":
                w.config(bg=c["card"], fg=c["accent"])
            elif role == "status_dot":
                w.config(bg=c["bg"], fg=c["muted"])
            elif role == "status_text":
                w.config(bg=c["bg"], fg=c["text"])
            elif role == "text_input":
                w.config(
                    bg=c["input_bg"],
                    fg=c["text"],
                    insertbackground=c["text"],
                    highlightbackground=c["border"],
                    highlightcolor=c["accent"],
                    selectbackground=c["accent"],
                    selectforeground=c["accent_fg"],
                )
            elif role == "log":
                w.config(
                    bg=c["log_bg"],
                    fg=c["log_fg"],
                    insertbackground=c["log_fg"],
                    highlightbackground=c["border"],
                    selectbackground=c["accent"],
                    selectforeground=c["accent_fg"],
                )
        except tk.TclError:
            pass

    def _apply_ttk_styles(self):
        c = self.colors
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "TEntry",
            fieldbackground=c["input_bg"],
            foreground=c["text"],
            insertcolor=c["text"],
            bordercolor=c["border"],
            lightcolor=c["input_bg"],
            darkcolor=c["input_bg"],
            padding=6,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
            darkcolor=[("focus", c["accent"])],
        )

        style.configure(
            "Primary.TButton",
            background=c["accent"],
            foreground=c["accent_fg"],
            bordercolor=c["accent"],
            lightcolor=c["accent"],
            darkcolor=c["accent"],
            focuscolor=c["accent"],
            padding=(18, 9),
            font=(FONT_UI, 10, "bold"),
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[("active", c["accent_hover"]), ("pressed", c["accent_hover"])],
            bordercolor=[("active", c["accent_hover"])],
            lightcolor=[("active", c["accent_hover"])],
            darkcolor=[("active", c["accent_hover"])],
        )

        style.configure(
            "Secondary.TButton",
            background=c["card"],
            foreground=c["text"],
            bordercolor=c["border"],
            lightcolor=c["card"],
            darkcolor=c["card"],
            focuscolor=c["card"],
            padding=(12, 6),
            font=(FONT_UI, 9),
            relief="flat",
        )
        style.map(
            "Secondary.TButton",
            background=[("active", c["input_bg"])],
            bordercolor=[("active", c["accent"])],
        )

        style.configure(
            "TCheckbutton",
            background=c["card"],
            foreground=c["text"],
            focuscolor=c["card"],
            font=(FONT_UI, 9),
        )
        style.map("TCheckbutton", background=[("active", c["card"])])

        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=c["card"],
            background=c["accent"],
            bordercolor=c["border"],
            lightcolor=c["accent"],
            darkcolor=c["accent"],
            thickness=6,
        )

        style.configure(
            "Vertical.TScrollbar",
            background=c["scrollbar"],
            troughcolor=c["log_bg"],
            bordercolor=c["log_bg"],
            arrowcolor=c["muted"],
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
        self.log_text.tag_configure("info", foreground=c["log_fg"])
        self.log_text.tag_configure("success", foreground=c["success"])
        self.log_text.tag_configure("warn", foreground=c["warn"])
        self.log_text.tag_configure("error", foreground=c["error"])

    def _theme_btn_text(self) -> str:
        return "☀️  حالت روز" if self.theme == "dark" else "🌙  حالت شب"

    def _toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self._apply_theme()

    # ---------- انتخاب مسیرها ----------

    def _browse_project(self):
        path = filedialog.askdirectory(title="انتخاب پوشه پروژه")
        if path:
            self.project_var.set(path)
            self.output_var.set(os.path.join(path, "project_snapshot.txt"))

    def _browse_output(self):
        initial = self.project_var.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="محل ذخیره خروجی",
            initialdir=initial,
            initialfile="project_snapshot.txt",
            defaultextension=".txt",
            filetypes=[("متنی", "*.txt"), ("همه فایل‌ها", "*.*")],
        )
        if path:
            self.output_var.set(path)

    # ---------- لاگ و وضعیت ----------

    def _log(self, msg: str, tag: str = "info"):
        self.root.after(0, self._append_log, msg, tag)

    def _append_log(self, msg: str, tag: str):
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)

    def _set_status(self, text: str, state: str = "idle"):
        c = self.colors
        color = {
            "idle": c["muted"],
            "running": c["accent"],
            "success": c["success"],
            "error": c["error"],
        }.get(state, c["muted"])
        self.status_dot.config(fg=color)
        self.status_label.config(text=text)

    # ---------- اجرا ----------

    def _start(self):
        if self.running:
            return

        project = self.project_var.get().strip()
        output = self.output_var.get().strip()

        if not project or not os.path.isdir(project):
            self._log("❌ مسیر پروژه معتبر نیست.", "error")
            self._set_status("خطا در مسیر پروژه", "error")
            return
        if not output:
            self._log("❌ مسیر خروجی مشخص نشده.", "error")
            self._set_status("خطا در مسیر خروجی", "error")
            return

        raw = self.exclude_text.get("1.0", tk.END)
        patterns = [p.strip() for p in raw.replace(",", "\n").split("\n") if p.strip()]

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self._set_status("در حال اجرا...", "running")
        self.progress.start(12)
        self.log_text.delete("1.0", tk.END)

        def worker():
            ok = False
            try:
                ok = create_snapshot(
                    project,
                    include_gitignore=self.use_gitignore_var.get(),
                    extra_patterns=patterns,
                    output_file_path=output,
                    log_func=self._log,
                )
            except Exception as e:
                self._log(f"❌ خطای غیرمنتظره: {e}", "error")
            finally:
                self.root.after(0, self._finish, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, ok: bool):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.progress.stop()
        if ok:
            self._set_status("با موفقیت انجام شد", "success")
        else:
            self._set_status("پایان با خطا", "error")


# ============================================================
# اجرا
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = SnapshotApp(root)
    root.mainloop()
