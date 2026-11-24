"""
Project Snapshotter GUI
دوزبانه (فارسی/انگلیسی) + تم روز/شب
موتور .gitignore سازگار با Git (negation, anchoring, **, [], escape,
nested .gitignore, first-prune semantics).
"""

import os
import re
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
from typing import List, Optional

# ============================================================
# فونت‌ها
# ============================================================


def pick_ui_font(root) -> str:
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    if sys.platform.startswith("win"):
        candidates = ["Segoe UI", "Vazirmatn", "Tahoma", "Arial"]
    elif sys.platform == "darwin":
        candidates = ["SF Pro Text", "Vazirmatn", "Helvetica Neue", "Tahoma", "Arial"]
    else:
        candidates = [
            "Vazirmatn",
            "Ubuntu",
            "Cantarell",
            "DejaVu Sans",
            "Tahoma",
            "Arial",
        ]
    for f in candidates:
        if f in families:
            return f
    return "TkDefaultFont"


def pick_mono_font(root) -> str:
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for f in [
        "Cascadia Code",
        "Consolas",
        "Menlo",
        "Monaco",
        "DejaVu Sans Mono",
        "Courier New",
    ]:
        if f in families:
            return f
    return "TkFixedFont"


# ============================================================
# پالت رنگ
# ============================================================

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
# ترجمه‌ها
# ============================================================

STRINGS = {
    "fa": {
        "title": "📸  Project Snapshotter",
        "subtitle": "اسنپ‌شات از فایل‌های متنی پروژه",
        "theme_light": "☀️  حالت روز",
        "theme_dark": "🌙  حالت شب",
        "lang_btn": "🌐  English",
        "project_path": "مسیر پروژه",
        "output_path": "مسیر فایل خروجی",
        "browse_folder": "انتخاب پوشه",
        "save_in": "ذخیره در...",
        "output_hint": "به‌طور پیش‌فرض کنار پروژه ذخیره می‌شود. مسیر را می‌توانید تغییر دهید.",
        "ignore_settings": "تنظیمات ignore",
        "use_gitignore": "اعمال .gitignore ها (شامل زیرپوشه‌ها، سازگار با Git)",
        "manual_patterns": "الگوهای دستی (هر خط یک الگو، یا با کاما):",
        "pattern_hint": "پشتیبانی: !negation   dir/   /anchored   **   ?   []   \\escape",
        "start_btn": "🚀  شروع اسنپ‌شات",
        "status_ready": "آماده",
        "status_running": "در حال اجرا...",
        "status_success": "با موفقیت انجام شد",
        "status_error_project": "خطا در مسیر پروژه",
        "status_error_output": "خطا در مسیر خروجی",
        "status_finished_error": "پایان با خطا",
        "shortcuts": "F5 اجرا  •  Ctrl+T تم  •  Ctrl+L زبان  •  Esc خروج",
        "log_title": "گزارش عملیات",
        "clear_btn": "پاک کردن",
        "dlg_project": "انتخاب پوشه پروژه",
        "dlg_output": "محل ذخیره خروجی",
        "dlg_ft_text": "متنی",
        "dlg_ft_all": "همه فایل‌ها",
        "log_manual_added": "➕ {n} الگوی دستی اضافه شد.",
        "log_start": "🚀 شروع پیمایش...",
        "log_gitignore": "📄 {n} الگو از {path}",
        "log_access_error": "⚠️ دسترسی به {path} ممکن نیست: {err}",
        "log_progress": "⏳ {n} فایل پردازش شد...",
        "log_read_error": "❌ خطا در {path}: {err}",
        "log_unexpected": "❌ خطای غیرمنتظره: {err}",
        "log_done": "✅ تمام شد! {n} فایل نوشته شد، {skipped} مورد رد شد.",
        "log_output": "📁 خروجی: {path}",
        "log_write_error": "❌ خطای بحرانی در نوشتن: {err}",
        "log_invalid_project": "❌ مسیر پروژه معتبر نیست.",
        "log_invalid_output": "❌ مسیر خروجی مشخص نشده.",
        "log_internal_error": "❌ خطای داخلی: {err}",
    },
    "en": {
        "title": "📸  Project Snapshotter",
        "subtitle": "Snapshot of project text files",
        "theme_light": "☀️  Light mode",
        "theme_dark": "🌙  Dark mode",
        "lang_btn": "🌐  فارسی",
        "project_path": "Project path",
        "output_path": "Output file path",
        "browse_folder": "Browse folder",
        "save_in": "Save as...",
        "output_hint": "Saved next to the project by default. You can change the path.",
        "ignore_settings": "Ignore settings",
        "use_gitignore": "Apply .gitignore files (including subfolders, Git-compatible)",
        "manual_patterns": "Manual patterns (one per line, or comma-separated):",
        "pattern_hint": "Supported: !negation   dir/   /anchored   **   ?   []   \\escape",
        "start_btn": "🚀  Start snapshot",
        "status_ready": "Ready",
        "status_running": "Running...",
        "status_success": "Completed successfully",
        "status_error_project": "Invalid project path",
        "status_error_output": "Invalid output path",
        "status_finished_error": "Finished with error",
        "shortcuts": "F5 run  •  Ctrl+T theme  •  Ctrl+L language  •  Esc exit",
        "log_title": "Activity log",
        "clear_btn": "Clear",
        "dlg_project": "Select project folder",
        "dlg_output": "Save output as",
        "dlg_ft_text": "Text",
        "dlg_ft_all": "All files",
        "log_manual_added": "➕ {n} manual patterns added.",
        "log_start": "🚀 Starting traversal...",
        "log_gitignore": "📄 {n} patterns from {path}",
        "log_access_error": "⚠️ Cannot access {path}: {err}",
        "log_progress": "⏳ {n} files processed...",
        "log_read_error": "❌ Error in {path}: {err}",
        "log_unexpected": "❌ Unexpected error: {err}",
        "log_done": "✅ Done! {n} files written, {skipped} skipped.",
        "log_output": "📁 Output: {path}",
        "log_write_error": "❌ Critical write error: {err}",
        "log_invalid_project": "❌ Invalid project path.",
        "log_invalid_output": "❌ Output path not specified.",
        "log_internal_error": "❌ Internal error: {err}",
    },
}


# ============================================================
# موتور gitignore
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

    def copy(self):
        return GitIgnoreMatcher(self.rules)

    def add(self, rules):
        self.rules.extend(rules)

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        ignored = False
        for rule in self.rules:
            if rule.matches(rel_path, is_dir):
                ignored = not rule.negation
        return ignored


def build_default_matcher():
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
# ساخت اسنپ‌شات
# ============================================================


def create_snapshot(
    root_dir: str,
    include_gitignore: bool,
    extra_patterns: List[str],
    output_file_path: str,
    log_func,
) -> bool:
    """
    log_func(key, kwargs_dict, tag)
    """
    output_abs = os.path.abspath(output_file_path)
    base = build_default_matcher()
    manual = [r for r in (GitIgnorePattern(l) for l in extra_patterns) if r.valid]
    base.add(manual)
    if manual:
        log_func("log_manual_added", {"n": len(manual)}, "info")

    all_contents: List[str] = []
    stats = {"processed": 0, "skipped": 0}

    log_func("log_start", {}, "info")

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
                    log_func("log_gitignore", {"n": len(rules), "path": rel_gi}, "info")

        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except (PermissionError, OSError) as e:
            log_func("log_access_error", {"path": dir_path, "err": str(e)}, "warn")
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
                        log_func("log_progress", {"n": stats["processed"]}, "info")
                except UnicodeDecodeError:
                    stats["skipped"] += 1
                except (IOError, OSError) as e:
                    log_func("log_read_error", {"path": rel, "err": str(e)}, "error")
                    stats["skipped"] += 1

    try:
        walk(root_dir, "", base)
    except Exception as e:
        log_func("log_unexpected", {"err": str(e)}, "error")
        return False

    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_contents))
        log_func(
            "log_done",
            {"n": stats["processed"], "skipped": stats["skipped"]},
            "success",
        )
        log_func("log_output", {"path": output_file_path}, "success")
        return True
    except Exception as e:
        log_func("log_write_error", {"err": str(e)}, "error")
        return False


# ============================================================
# اپلیکیشن
# ============================================================


class SnapshotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = detect_system_theme()
        self.lang = "fa"  # پیش‌فرض فارسی
        self.colors = PALETTES[self.theme]
        self.running = False
        self._log_entries: List[tuple] = []
        self._status_key = "status_ready"
        self._status_state = "idle"

        self.font_ui = pick_ui_font(root)
        self.font_mono = pick_mono_font(root)

        self.root.title("Project Snapshotter")
        self.root.geometry("980x900")
        self.root.minsize(820, 740)

        self._build_ui()
        self._apply_theme()
        self._apply_language()

        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<Control-l>", lambda e: self._toggle_lang())
        self.root.bind("<F5>", lambda e: self._start())
        self.root.bind("<Control-Return>", lambda e: self._start())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    # --- helpers ---

    def _t(self, key: str, **kwargs) -> str:
        template = STRINGS[self.lang].get(key, key)
        try:
            return template.format(**kwargs) if kwargs else template
        except (KeyError, IndexError):
            return template

    def _is_rtl(self) -> bool:
        return self.lang == "fa"

    def _font(self, size: int, weight: str = "normal"):
        return (self.font_ui, size, weight)

    # --- UI ---

    def _build_ui(self):
        # Header
        self.header = tk.Frame(self.root, height=64)
        self.header.pack(fill=tk.X)
        self.header._role = "header"
        self.header.pack_propagate(False)

        self.title_box = tk.Frame(self.header)
        self.title_box._role = "header"
        self.title_box.pack(side=tk.LEFT, padx=20, pady=10)

        self.title_lbl = tk.Label(self.title_box, font=self._font(15, "bold"))
        self.title_lbl._text_key = "title"
        self.title_lbl._role = "title"
        self.title_lbl.pack(anchor=tk.W)

        self.subtitle_lbl = tk.Label(self.title_box, font=self._font(9))
        self.subtitle_lbl._text_key = "subtitle"
        self.subtitle_lbl._role = "subtitle"
        self.subtitle_lbl.pack(anchor=tk.W)

        self.theme_btn = tk.Label(
            self.header, font=self._font(10), padx=14, pady=6, cursor="hand2"
        )
        self.theme_btn._role = "ghost_btn"
        self.theme_btn.pack(side=tk.RIGHT, padx=(0, 20))
        self.theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())

        self.lang_btn = tk.Label(
            self.header, font=self._font(10), padx=14, pady=6, cursor="hand2"
        )
        self.lang_btn._role = "ghost_btn"
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 6))
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_lang())

        self.header_line = tk.Frame(self.root, height=1)
        self.header_line._role = "separator"
        self.header_line.pack(fill=tk.X)

        # Body
        self.body = tk.Frame(self.root)
        self.body._role = "bg"
        self.body.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        self._build_paths_card(self.body)
        self._build_options_card(self.body)
        self._build_action_bar(self.body)
        self._build_log_card(self.body)

    def _make_card(self, parent) -> tk.Frame:
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        return card

    def _make_label(
        self,
        parent,
        key: str,
        size: int,
        weight: str = "normal",
        role: str = "card_title",
    ) -> tk.Label:
        lbl = tk.Label(parent, font=self._font(size, weight), anchor=tk.W)
        lbl._text_key = key
        lbl._role = role
        return lbl

    def _build_paths_card(self, parent):
        card = self._make_card(parent)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=16, pady=14)

        lbl1 = self._make_label(inner, "project_path", 9, "bold")
        lbl1.pack(fill=tk.X, pady=(0, 4))

        row1 = tk.Frame(inner)
        row1._role = "card"
        row1.pack(fill=tk.X)
        self.project_var = tk.StringVar()
        self.project_entry = ttk.Entry(
            row1, textvariable=self.project_var, font=self._font(10)
        )
        self.browse_btn1 = ttk.Button(
            row1, style="Secondary.TButton", command=self._browse_project
        )
        self.browse_btn1._text_key = "browse_folder"

        lbl2 = self._make_label(inner, "output_path", 9, "bold")
        lbl2.pack(fill=tk.X, pady=(12, 4))

        row2 = tk.Frame(inner)
        row2._role = "card"
        row2.pack(fill=tk.X)
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(
            row2, textvariable=self.output_var, font=self._font(10)
        )
        self.browse_btn2 = ttk.Button(
            row2, style="Secondary.TButton", command=self._browse_output
        )
        self.browse_btn2._text_key = "save_in"

        hint = self._make_label(inner, "output_hint", 8, role="hint")
        hint.pack(fill=tk.X, pady=(8, 0))

        self._path_widgets = [
            (self.project_entry, self.browse_btn1),
            (self.output_entry, self.browse_btn2),
        ]

    def _build_options_card(self, parent):
        card = self._make_card(parent)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card)
        inner._role = "card"
        inner.pack(fill=tk.X, padx=16, pady=14)

        title = self._make_label(inner, "ignore_settings", 9, "bold")
        title.pack(fill=tk.X, pady=(0, 8))

        self.use_gitignore_var = tk.BooleanVar(value=True)
        self.gitignore_cb = ttk.Checkbutton(
            inner, variable=self.use_gitignore_var, style="TCheckbutton"
        )
        self.gitignore_cb._text_key = "use_gitignore"
        self.gitignore_cb.pack(anchor=tk.W)

        lbl = self._make_label(inner, "manual_patterns", 9)
        lbl.pack(fill=tk.X, pady=(12, 4))

        self.exclude_text = tk.Text(
            inner,
            height=3,
            wrap=tk.WORD,
            font=self._font(10),
            relief=tk.FLAT,
            borderwidth=0,
            padx=8,
            pady=6,
            highlightthickness=1,
        )
        self.exclude_text._role = "text_input"
        self.exclude_text.pack(fill=tk.X)

        hint = self._make_label(inner, "pattern_hint", 8, role="hint")
        hint.pack(fill=tk.X, pady=(6, 0))

    def _build_action_bar(self, parent):
        self.action_bar = tk.Frame(parent)
        self.action_bar._role = "bg"
        self.action_bar.pack(fill=tk.X, pady=(0, 12))

        self.start_btn = ttk.Button(
            self.action_bar, style="Primary.TButton", command=self._start
        )
        self.start_btn._text_key = "start_btn"

        self.status_box = tk.Frame(self.action_bar)
        self.status_box._role = "bg"

        self.status_dot = tk.Label(self.status_box, text="●", font=self._font(12))
        self.status_dot._role = "status_dot"

        self.status_label = tk.Label(self.status_box, font=self._font(9))
        self.status_label._role = "status_text"

        self.shortcuts_lbl = tk.Label(self.action_bar, font=self._font(8))
        self.shortcuts_lbl._text_key = "shortcuts"
        self.shortcuts_lbl._role = "hint_bg"

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

        self.log_header = tk.Frame(inner)
        self.log_header._role = "card"
        self.log_header.pack(fill=tk.X, pady=(0, 6))

        self.log_title_lbl = self._make_label(self.log_header, "log_title", 9, "bold")

        self.clear_btn = tk.Label(self.log_header, font=self._font(8), cursor="hand2")
        self.clear_btn._text_key = "clear_btn"
        self.clear_btn._role = "ghost_btn_small"
        self.clear_btn.bind("<Button-1>", lambda e: self._clear_log())

        text_frame = tk.Frame(inner)
        text_frame._role = "card"
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=(self.font_mono, 9),
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

    # --- theme ---

    def _apply_theme(self):
        self.colors = PALETTES[self.theme]
        c = self.colors
        self.root.config(bg=c["bg"])
        self._apply_ttk_styles()
        self._apply_roles_recursive(self.root)
        self._update_log_tags()
        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark")
        )
        if hasattr(self, "_status_key"):
            self._set_status_from_key(self._status_key, self._status_state)

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
                w.config(bg=c["bg"])
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
            font=self._font(10, "bold"),
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
            font=self._font(9),
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
            font=self._font(9),
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

    # --- language ---

    def _apply_language(self):
        self._apply_texts_recursive(self.root)
        self._apply_alignment_recursive(self.root)
        self._relayout()
        self._rerender_log()
        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark")
        )
        self.lang_btn.config(text=self._t("lang_btn"))
        self._set_status_from_key(self._status_key, self._status_state)

    def _apply_texts_recursive(self, widget):
        key = getattr(widget, "_text_key", None)
        if key:
            try:
                widget.config(text=self._t(key))
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._apply_texts_recursive(child)

    def _apply_alignment_recursive(self, widget):
        rtl = self._is_rtl()
        anchor = "e" if rtl else "w"
        justify = "right" if rtl else "left"
        if isinstance(widget, tk.Label):
            try:
                cur = str(widget.cget("anchor"))
                if cur in ("w", "e"):
                    widget.config(anchor=anchor)
            except tk.TclError:
                pass
        elif isinstance(widget, (tk.Entry, ttk.Entry)):
            try:
                widget.config(justify=justify)
            except tk.TclError:
                pass
        elif isinstance(widget, tk.Text):
            try:
                widget.config(justify=justify)
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._apply_alignment_recursive(child)

    def _relayout(self):
        rtl = self._is_rtl()

        # ردیف‌های مسیر
        for entry, btn in self._path_widgets:
            entry.pack_forget()
            btn.pack_forget()
            if rtl:
                btn.pack(side=tk.LEFT, padx=(0, 8))
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                btn.pack(side=tk.LEFT, padx=(8, 0))

        # نوار اجرا
        self.start_btn.pack_forget()
        self.status_box.pack_forget()
        self.shortcuts_lbl.pack_forget()
        if rtl:
            self.start_btn.pack(side=tk.RIGHT)
            self.status_box.pack(side=tk.RIGHT, padx=16)
            self.shortcuts_lbl.pack(side=tk.LEFT)
        else:
            self.start_btn.pack(side=tk.LEFT)
            self.status_box.pack(side=tk.LEFT, padx=16)
            self.shortcuts_lbl.pack(side=tk.RIGHT)

        # هدر لاگ
        self.log_title_lbl.pack_forget()
        self.clear_btn.pack_forget()
        if rtl:
            self.clear_btn.pack(side=tk.LEFT)
            self.log_title_lbl.pack(side=tk.RIGHT)
        else:
            self.log_title_lbl.pack(side=tk.LEFT)
            self.clear_btn.pack(side=tk.RIGHT)

        # وضعیت
        self.status_dot.pack_forget()
        self.status_label.pack_forget()
        if rtl:
            self.status_dot.pack(side=tk.RIGHT)
            self.status_label.pack(side=tk.RIGHT, padx=(0, 6))
        else:
            self.status_dot.pack(side=tk.LEFT)
            self.status_label.pack(side=tk.LEFT, padx=(6, 0))

    def _rerender_log(self):
        self.log_text.delete("1.0", tk.END)
        for key, kwargs, tag in self._log_entries:
            text = self._t(key, **kwargs)
            self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)

    def _toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self._apply_theme()

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "fa" else "fa"
        self._apply_language()

    # --- browse ---

    def _browse_project(self):
        path = filedialog.askdirectory(title=self._t("dlg_project"))
        if path:
            self.project_var.set(path)
            self.output_var.set(os.path.join(path, "project_snapshot.txt"))

    def _browse_output(self):
        initial = self.project_var.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title=self._t("dlg_output"),
            initialdir=initial,
            initialfile="project_snapshot.txt",
            defaultextension=".txt",
            filetypes=[
                (self._t("dlg_ft_text"), "*.txt"),
                (self._t("dlg_ft_all"), "*.*"),
            ],
        )
        if path:
            self.output_var.set(path)

    # --- log / status ---

    def _log(self, key, kwargs=None, tag="info"):
        kwargs = kwargs or {}
        self.root.after(0, self._append_log, key, dict(kwargs), tag)

    def _append_log(self, key, kwargs, tag):
        self._log_entries.append((key, kwargs, tag))
        text = self._t(key, **kwargs)
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)

    def _clear_log(self):
        self._log_entries.clear()
        self.log_text.delete("1.0", tk.END)

    def _set_status_from_key(self, key: str, state: str = "idle"):
        self._status_key = key
        self._status_state = state
        c = self.colors
        color = {
            "idle": c["muted"],
            "running": c["accent"],
            "success": c["success"],
            "error": c["error"],
        }.get(state, c["muted"])
        try:
            self.status_dot.config(fg=color)
            self.status_label.config(text=self._t(key))
        except tk.TclError:
            pass

    # --- run ---

    def _start(self):
        if self.running:
            return

        project = self.project_var.get().strip()
        output = self.output_var.get().strip()

        if not project or not os.path.isdir(project):
            self._log("log_invalid_project", {}, "error")
            self._set_status_from_key("status_error_project", "error")
            return
        if not output:
            self._log("log_invalid_output", {}, "error")
            self._set_status_from_key("status_error_output", "error")
            return

        raw = self.exclude_text.get("1.0", tk.END)
        patterns = [p.strip() for p in raw.replace(",", "\n").split("\n") if p.strip()]

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self._set_status_from_key("status_running", "running")
        self.progress.start(12)
        self._clear_log()

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
                self._log("log_internal_error", {"err": str(e)}, "error")
            finally:
                self.root.after(0, self._finish, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, ok: bool):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.progress.stop()
        if ok:
            self._set_status_from_key("status_success", "success")
        else:
            self._set_status_from_key("status_finished_error", "error")


# ============================================================
# اجرا
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    SnapshotApp(root)
    root.mainloop()
