"""
Project Snapshotter — Production Build
دوزبانه + تم روز/شب + فونت اختصاصی از پوشه پروژه
موتور .gitignore سازگار با Git.
"""

import os
import re
import sys
import json
import time
import ctypes
import struct
import shutil
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
from typing import List, Optional, Tuple


APP_VERSION = "2.0.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# Font Manager — load .ttf/.otf from project path
# ============================================================

class FontManager:
    """
    فونت‌های اختصاصی را از script_dir/fonts/ و script_dir/ بارگذاری می‌کند
    و نام خانوادگی واقعی فونت را از فایل TTF/OTF می‌خواند.
    """

    IRANSANS_NAMES = [
        "IRANSans", "IRANSansX", "IRANSansWeb", "IRAN Sans",
        "IRANSansXFaNum", "IRANSansXV", "IRANSans Light",
    ]
    VAZIR_NAMES = ["Vazir", "Vazirmatn", "Vazir Medium"]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.loaded_families: List[str] = []
        self.log: List[str] = []

    def _log(self, msg: str):
        self.log.append(msg)
        print(f"[font] {msg}")

    # ---- TTF/OTF name table parser ----

    @staticmethod
    def _read_family_from_font(path: str) -> Optional[str]:
        """استخراج نام خانواده فونت از name table (id=1 یا 16)."""
        try:
            with open(path, "rb") as f:
                data = f.read(128 * 1024)
        except Exception:
            return None
        if len(data) < 12:
            return None
        if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
            return None
        num_tables = struct.unpack(">H", data[4:6])[0]
        name_off = None
        for i in range(num_tables):
            off = 12 + i * 16
            if off + 16 > len(data):
                break
            if data[off:off + 4] == b"name":
                name_off = struct.unpack(">I", data[off + 8:off + 12])[0]
                break
        if name_off is None or name_off + 6 > len(data):
            return None
        count = struct.unpack(">H", data[name_off + 2:name_off + 4])[0]
        string_off = struct.unpack(">H", data[name_off + 4:name_off + 6])[0]
        storage = name_off + string_off
        best = None
        for i in range(count):
            rec = name_off + 6 + i * 12
            if rec + 12 > len(data):
                break
            platform, _, _, name_id, length, offset = struct.unpack(
                ">HHHHHH", data[rec:rec + 12])
            if name_id not in (1, 16):
                continue
            s, e = storage + offset, storage + offset + length
            if e > len(data):
                continue
            try:
                if platform == 3:
                    name = data[s:e].decode("utf-16-be", errors="ignore")
                else:
                    name = data[s:e].decode("mac-roman", errors="ignore")
                name = name.strip()
                if not name:
                    continue
                if name_id == 16 or best is None:
                    best = name
            except Exception:
                continue
        return best

    # ---- OS-level loading ----

    def _load_windows(self, path: str):
        FR_PRIVATE = 0x10
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi32.AddFontResourceExW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        gdi32.AddFontResourceExW.restype = ctypes.c_int
        if not gdi32.AddFontResourceExW(path, FR_PRIVATE, None):
            raise RuntimeError("AddFontResourceEx failed")

    def _load_unix(self, path: str):
        # copy to user fonts dir + refresh cache
        if sys.platform == "darwin":
            dst_dir = os.path.expanduser("~/Library/Fonts")
        else:
            dst_dir = os.path.expanduser("~/.local/share/fonts")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(path))
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
        if sys.platform != "darwin":
            os.system("fc-cache -f >/dev/null 2>&1")

    def _load_file(self, path: str) -> Optional[str]:
        try:
            if sys.platform.startswith("win"):
                self._load_windows(path)
            else:
                self._load_unix(path)
        except Exception as e:
            self._log(f"failed to load {os.path.basename(path)}: {e}")
            return None
        family = self._read_family_from_font(path)
        if family:
            self.loaded_families.append(family)
            self._log(f"loaded '{family}' from {os.path.basename(path)}")
        return family

    def scan_and_load(self):
        """جستجو در script_dir/fonts و script_dir و cwd."""
        search_dirs = [
            os.path.join(SCRIPT_DIR, "fonts"),
            SCRIPT_DIR,
            os.path.join(os.getcwd(), "fonts"),
            os.getcwd(),
        ]
        seen = set()
        for d in search_dirs:
            if not d or not os.path.isdir(d) or d in seen:
                continue
            seen.add(d)
            for entry in sorted(os.listdir(d)):
                if entry.lower().endswith((".ttf", ".otf")):
                    self._load_file(os.path.join(d, entry))
        # refresh Tk font cache
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def _available(self) -> set:
        try:
            return set(tkfont.families(self.root))
        except Exception:
            return set()

    def pick_ui_font(self) -> str:
        avail = self._available()
        # priority: loaded families first (they're our own)
        for name in self.loaded_families + self.IRANSANS_NAMES:
            if name in avail:
                self._log(f"UI font = '{name}' (custom)")
                return name
        for name in self.VAZIR_NAMES:
            if name in avail:
                self._log(f"UI font = '{name}' (vazir fallback)")
                return name
        # system fallbacks
        sys_candidates = (
            ["Segoe UI", "Tahoma", "Arial"] if sys.platform.startswith("win")
            else ["SF Pro Text", "Helvetica Neue", "Tahoma"]
            if sys.platform == "darwin"
            else ["Ubuntu", "Cantarell", "DejaVu Sans", "Tahoma"]
        )
        for name in sys_candidates:
            if name in avail:
                self._log(f"UI font = '{name}' (system)")
                return name
        self._log("UI font = TkDefaultFont")
        return "TkDefaultFont"

    def pick_mono_font(self) -> str:
        avail = self._available()
        for name in ["JetBrains Mono", "Cascadia Code", "Consolas",
                     "Menlo", "Monaco", "DejaVu Sans Mono", "Courier New"]:
            if name in avail:
                return name
        return "TkFixedFont"


# ============================================================
# Palettes — macOS-inspired, WCAG AA contrast
# ============================================================

PALETTES = {
    "light": {
        "surface":       "#f5f5f7",
        "surface_hover": "#ebebee",
        "card":          "#ffffff",
        "card_hover":    "#f8f8fa",
        "header":        "#ffffff",
        "header_hover":  "#f2f2f5",
        "border":        "#e2e2e7",
        "border_strong": "#cdcdd3",
        "text":          "#1c1c1e",
        "text_sub":      "#6e6e73",
        "muted":         "#98989d",
        "accent":        "#007aff",
        "accent_hover":  "#0066d6",
        "accent_fg":     "#ffffff",
        "input":         "#fbfbfd",
        "input_border":  "#d4d4d9",
        "log_bg":        "#fbfbfd",
        "log_fg":        "#1c1c1e",
        "success":       "#28a745",
        "warning":       "#cc8800",
        "danger":        "#d70015",
        "scrollbar":     "#c7c7cc",
    },
    "dark": {
        "surface":       "#0f0f10",
        "surface_hover": "#1c1c1e",
        "card":          "#1c1c1e",
        "card_hover":    "#252528",
        "header":        "#161618",
        "header_hover":  "#232326",
        "border":        "#2c2c2e",
        "border_strong": "#3d3d40",
        "text":          "#f2f2f7",
        "text_sub":      "#a1a1a6",
        "muted":         "#6e6e73",
        "accent":        "#0a84ff",
        "accent_hover":  "#3d9dff",
        "accent_fg":     "#ffffff",
        "input":         "#161618",
        "input_border":  "#3a3a3d",
        "log_bg":        "#0a0a0b",
        "log_fg":        "#e5e5ea",
        "success":       "#30d158",
        "warning":       "#ffd60a",
        "danger":        "#ff453a",
        "scrollbar":     "#48484a",
    },
}


def detect_system_theme() -> str:
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            v, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if v else "dark"
        if sys.platform == "darwin":
            import subprocess
            out = subprocess.check_output(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stderr=subprocess.DEVNULL).decode().strip()
            return "dark" if out.lower() == "dark" else "light"
    except Exception:
        pass
    return "light"


# ============================================================
# Strings
# ============================================================

STRINGS = {
    "fa": {
        "app_title":     "Project Snapshotter",
        "app_subtitle":  "اسنپ‌شات از فایل‌های متنی پروژه",
        "lang_btn":      "EN",
        "theme_dark":    "🌙",
        "theme_light":   "☀️",
        "theme_tip":     "تغییر تم (Ctrl+T)",
        "lang_tip":      "Switch to English (Ctrl+L)",

        "section_paths":  "مسیرها",
        "project_path":   "پوشه پروژه",
        "project_ph":     "پوشه‌ای که می‌خواهید اسنپ‌شات بگیرید...",
        "browse":         "انتخاب",
        "output_path":    "فایل خروجی",
        "output_ph":      "مسیر فایل متنی خروجی...",
        "save_as":        "ذخیره در",

        "section_ignore":  "قواعد ignore",
        "use_gitignore":   "اعمال فایل‌های .gitignore (شامل زیرپوشه‌ها)",
        "manual_patterns": "الگوهای اضافی (هر خط یک الگو یا با کاما):",
        "pattern_ph":      "dist/, *.log, !important.log",
        "pattern_hint":    "پشتیبانی:  !negation  ·  dir/  ·  /anchored  ·  **  ·  ?  ·  []  ·  \\escape",

        "start_btn":      "🚀  شروع اسنپ‌شات",
        "cancel_btn":     "✕  لغو",
        "open_folder":    "📂  باز کردن پوشه",
        "btn_hint":       "F5 برای اجرا",

        "status_ready":    "آماده",
        "status_running":  "در حال اجرا...",
        "status_success":  "تکمیل شد",
        "status_error":    "خطا",
        "status_cancelled":"لغو شد",

        "log_title":   "گزارش عملیات",
        "log_clear":   "پاک کردن",
        "log_empty":   "هنوز گزارشی وجود ندارد.",
        "log_empty_sub":"مسیر پروژه را انتخاب و دکمه شروع را بزنید.",

        "footer_hint": "Ctrl+T تم  ·  Ctrl+L زبان  ·  F5 اجرا",

        "dlg_project":  "انتخاب پوشه پروژه",
        "dlg_output":   "ذخیره خروجی",
        "dlg_ft_text":  "فایل متنی",
        "dlg_ft_all":   "همه فایل‌ها",

        "toast_saved":   "مسیر خروجی به‌روز شد",
        "toast_copied":  "در کلیپ‌بورد کپی شد",

        "log_manual_added": "➕ {n} الگوی دستی اضافه شد",
        "log_start":        "🚀 شروع پیمایش پروژه",
        "log_gitignore":    "📄 {n} الگو از {path}",
        "log_access_error": "⚠️ دسترسی به {path} ممکن نیست",
        "log_progress":     "⏳ {n} فایل پردازش شد",
        "log_read_error":   "❌ خطا در خواندن {path}: {err}",
        "log_unexpected":   "❌ خطای غیرمنتظره: {err}",
        "log_done":         "✅ انجام شد — {n} فایل نوشته شد، {skipped} مورد رد شد",
        "log_output":       "📁 فایل خروجی: {path}",
        "log_write_error":  "❌ خطا در نوشتن فایل: {err}",
        "log_cancelled":    "⊘ عملیات توسط کاربر لغو شد",
        "log_invalid_proj": "❌ مسیر پروژه معتبر نیست",
        "log_invalid_out":  "❌ مسیر خروجی مشخص نشده",
        "log_internal":     "❌ خطای داخلی: {err}",
        "log_font_loaded":  "🔤 فونت بارگذاری شد: {name}",
    },
    "en": {
        "app_title":     "Project Snapshotter",
        "app_subtitle":  "Snapshot of project text files",
        "lang_btn":      "فا",
        "theme_dark":    "🌙",
        "theme_light":   "☀️",
        "theme_tip":     "Toggle theme (Ctrl+T)",
        "lang_tip":      "تغییر به فارسی (Ctrl+L)",

        "section_paths":  "Paths",
        "project_path":   "Project folder",
        "project_ph":     "Folder to snapshot...",
        "browse":         "Browse",
        "output_path":    "Output file",
        "output_ph":      "Output text file path...",
        "save_as":        "Save as",

        "section_ignore":  "Ignore rules",
        "use_gitignore":   "Apply .gitignore files (including subfolders)",
        "manual_patterns": "Additional patterns (one per line, or comma-separated):",
        "pattern_ph":      "dist/, *.log, !important.log",
        "pattern_hint":    "Supports:  !negation  ·  dir/  ·  /anchored  ·  **  ·  ?  ·  []  ·  \\escape",

        "start_btn":      "🚀  Start snapshot",
        "cancel_btn":     "✕  Cancel",
        "open_folder":    "📂  Open folder",
        "btn_hint":       "Press F5 to run",

        "status_ready":    "Ready",
        "status_running":  "Running...",
        "status_success":  "Completed",
        "status_error":    "Error",
        "status_cancelled":"Cancelled",

        "log_title":   "Activity log",
        "log_clear":   "Clear",
        "log_empty":   "No activity yet.",
        "log_empty_sub":"Pick a project folder, then click Start.",

        "footer_hint": "Ctrl+T theme  ·  Ctrl+L language  ·  F5 run",

        "dlg_project":  "Select project folder",
        "dlg_output":   "Save output as",
        "dlg_ft_text":  "Text file",
        "dlg_ft_all":   "All files",

        "toast_saved":   "Output path updated",
        "toast_copied":  "Copied to clipboard",

        "log_manual_added": "➕ {n} manual patterns added",
        "log_start":        "🚀 Starting traversal",
        "log_gitignore":    "📄 {n} patterns from {path}",
        "log_access_error": "⚠️ Cannot access {path}",
        "log_progress":     "⏳ {n} files processed",
        "log_read_error":   "❌ Error reading {path}: {err}",
        "log_unexpected":   "❌ Unexpected error: {err}",
        "log_done":         "✅ Done — {n} files written, {skipped} skipped",
        "log_output":       "📁 Output: {path}",
        "log_write_error":  "❌ Failed to write output: {err}",
        "log_cancelled":    "⊘ Cancelled by user",
        "log_invalid_proj": "❌ Invalid project path",
        "log_invalid_out":  "❌ Output path not specified",
        "log_internal":     "❌ Internal error: {err}",
        "log_font_loaded":  "🔤 Font loaded: {name}",
    },
}


# ============================================================
# .gitignore engine (unchanged, production-grade)
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
            self.valid = False; return
        if p.startswith("!"):
            self.negation = True; p = p[1:]
        elif p.startswith("\\!") or p.startswith("\\#"):
            p = p[1:]
        p = self._rstrip_unescaped_spaces(p)
        if not p:
            self.valid = False; return
        if p.endswith("/"):
            self.directory_only = True; p = p[:-1]
            if not p:
                self.valid = False; return
        if p.startswith("/"):
            self.anchored = True; p = p[1:]
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
                bs += 1; j -= 1
            if bs % 2 == 1: break
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
                        out.append("(?:.*/)?"); i += 3
                    elif i + 2 == n:
                        out.append(".*"); i += 2
                    else:
                        out.append("[^/]*"); i += 2
                else:
                    out.append("[^/]*"); i += 1
            elif c == "?":
                out.append("[^/]"); i += 1
            elif c == "[":
                j = i + 1
                if j < n and p[j] in ("!", "^"): j += 1
                if j < n and p[j] == "]": j += 1
                while j < n and p[j] != "]": j += 1
                if j >= n:
                    out.append(re.escape(c)); i += 1
                else:
                    inner = p[i + 1:j]
                    if inner.startswith("!"): inner = "^" + inner[1:]
                    out.append("[" + inner + "]"); i = j + 1
            elif c == "\\":
                if i + 1 < n:
                    out.append(re.escape(p[i + 1])); i += 2
                else:
                    out.append(re.escape(c)); i += 1
            else:
                out.append(re.escape(c)); i += 1
        return "".join(out)

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if not self.valid or self.regex is None: return False
        if self.directory_only and not is_dir: return False
        return self.regex.match(rel_path) is not None


def parse_gitignore_file(path: str) -> List[GitIgnorePattern]:
    out = []
    if not os.path.isfile(path): return out
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.rstrip("\r\n")
                r = GitIgnorePattern(line)
                if r.valid: out.append(r)
    except Exception:
        pass
    return out


class GitIgnoreMatcher:
    def __init__(self, rules: Optional[List[GitIgnorePattern]] = None):
        self.rules = list(rules) if rules else []
    def copy(self): return GitIgnoreMatcher(self.rules)
    def add(self, rules): self.rules.extend(rules)
    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        ignored = False
        for rule in self.rules:
            if rule.matches(rel_path, is_dir):
                ignored = not rule.negation
        return ignored


def build_default_matcher() -> GitIgnoreMatcher:
    defaults = [".git/", "node_modules/", "__pycache__/", "*.pyc", "*.tmp",
                "venv/", ".venv/", ".vscode/", ".idea/", "dist/", "build/",
                ".DS_Store"]
    return GitIgnoreMatcher(
        [r for r in (GitIgnorePattern(l) for l in defaults) if r.valid])


# ============================================================
# Snapshot engine
# ============================================================

def create_snapshot(root_dir, include_gitignore, extra_patterns,
                    output_file_path, log_func, cancel_event=None) -> bool:
    output_abs = os.path.abspath(output_file_path)
    base = build_default_matcher()
    manual = [r for r in (GitIgnorePattern(l) for l in extra_patterns) if r.valid]
    base.add(manual)
    if manual:
        log_func("log_manual_added", {"n": len(manual)}, "info")

    all_contents = []
    stats = {"processed": 0, "skipped": 0}
    log_func("log_start", {}, "info")

    def walk(dir_path, rel_dir, matcher):
        if cancel_event and cancel_event.is_set():
            return
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
        except (PermissionError, OSError):
            log_func("log_access_error", {"path": dir_path}, "warn")
            return

        for entry in entries:
            if cancel_event and cancel_event.is_set():
                return
            name, full = entry.name, entry.path
            rel = f"{rel_dir}/{name}" if rel_dir else name
            try:
                is_dir = entry.is_dir()
            except OSError:
                stats["skipped"] += 1; continue

            if not is_dir and os.path.abspath(full) == output_abs:
                continue
            if current.is_ignored(rel, is_dir):
                stats["skipped"] += 1; continue

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

    if cancel_event and cancel_event.is_set():
        log_func("log_cancelled", {}, "warn")
        return False

    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_contents))
        log_func("log_done",
                 {"n": stats["processed"], "skipped": stats["skipped"]}, "success")
        log_func("log_output", {"path": output_file_path}, "success")
        return True
    except Exception as e:
        log_func("log_write_error", {"err": str(e)}, "error")
        return False


# ============================================================
# SnapshotApp — redesigned UI
# ============================================================

class SnapshotApp:
    def __init__(self, root: tk.Tk, font_mgr: FontManager):
        self.root = root
        self.font_mgr = font_mgr
        self.theme = detect_system_theme()
        self.lang = "fa"
        self.colors = PALETTES[self.theme]
        self.running = False
        self.cancel_event: Optional[threading.Event] = None
        self._log_entries: List[Tuple[float, str, dict, str]] = []
        self._status_key = "status_ready"
        self._status_state = "idle"
        self._toast_widget = None

        self.font_ui = font_mgr.pick_ui_font()
        self.font_mono = font_mgr.pick_mono_font()

        self.root.title("Project Snapshotter")
        self.root.geometry("1000x920")
        self.root.minsize(840, 760)

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

    # ============================
    # Build UI
    # ============================

    def _build_ui(self):
        # --- Header ---
        self.header = tk.Frame(self.root, height=72)
        self.header._role = "header"
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        # title block
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

        # header actions (theme + lang)
        self.actions = tk.Frame(self.header)
        self.actions._role = "header"
        self.actions.pack(side=tk.RIGHT, padx=20)

        self.theme_btn = self._make_ghost_icon(self.actions, self._toggle_theme,
                                                role="ghost_btn")
        self.theme_btn.pack(side=tk.RIGHT, padx=(0, 6))

        self.lang_btn = tk.Label(self.actions, font=self._font(10, "bold"),
                                  padx=14, pady=8, cursor="hand2")
        self.lang_btn._role = "ghost_btn"
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 6))
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_lang())
        self._attach_hover(self.lang_btn, "ghost_btn")

        # separator
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
            w.config(bg=c["header_hover"] if role == "ghost_btn"
                     else c["card_hover"])
        def on_leave(_e):
            c = self.colors
            w.config(bg=c["header"] if role == "ghost_btn" else c["card"])
        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

    # --- Cards ---

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
        inner = tk.Frame(card); inner._role = "card"
        inner.pack(fill=tk.X, padx=20, pady=18)

        self._section_title(inner, "section_paths")

        # Project row
        self.lbl_project = tk.Label(inner, font=self._font(9), anchor=tk.W)
        self.lbl_project._text_key = "project_path"
        self.lbl_project._role = "field_label"
        self.lbl_project.pack(fill=tk.X, pady=(0, 6))

        self.row_project = tk.Frame(inner); self.row_project._role = "card"
        self.row_project.pack(fill=tk.X)

        self.project_var = tk.StringVar()
        self.project_entry = ttk.Entry(self.row_project, textvariable=self.project_var,
                                        font=self._font(10), style="TEntry")
        self.browse_btn1 = ttk.Button(self.row_project, style="Secondary.TButton",
                                       command=self._browse_project)
        self.browse_btn1._text_key = "browse"

        # Output row
        self.lbl_output = tk.Label(inner, font=self._font(9), anchor=tk.W)
        self.lbl_output._text_key = "output_path"
        self.lbl_output._role = "field_label"
        self.lbl_output.pack(fill=tk.X, pady=(14, 6))

        self.row_output = tk.Frame(inner); self.row_output._role = "card"
        self.row_output.pack(fill=tk.X)

        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(self.row_output, textvariable=self.output_var,
                                       font=self._font(10), style="TEntry")
        self.browse_btn2 = ttk.Button(self.row_output, style="Secondary.TButton",
                                       command=self._browse_output)
        self.browse_btn2._text_key = "save_as"

        self._path_rows = [(self.project_entry, self.browse_btn1),
                            (self.output_entry, self.browse_btn2)]

    def _build_ignore_card(self, parent):
        card = self._card(parent)
        inner = tk.Frame(card); inner._role = "card"
        inner.pack(fill=tk.X, padx=20, pady=18)

        self._section_title(inner, "section_ignore")

        self.use_gitignore_var = tk.BooleanVar(value=True)
        self.gitignore_cb = ttk.Checkbutton(
            inner, variable=self.use_gitignore_var, style="TCheckbutton")
        self.gitignore_cb._text_key = "use_gitignore"
        self.gitignore_cb.pack(anchor=tk.W, pady=(0, 12))

        lbl = tk.Label(inner, font=self._font(9), anchor=tk.W)
        lbl._text_key = "manual_patterns"
        lbl._role = "field_label"
        lbl.pack(fill=tk.X, pady=(0, 6))

        self.exclude_text = tk.Text(
            inner, height=3, wrap=tk.WORD, font=(self.font_mono, 10),
            relief=tk.FLAT, borderwidth=0, padx=10, pady=8, highlightthickness=1)
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

        self.start_btn = ttk.Button(self.action_row, style="Primary.TButton",
                                     command=self._start)
        self.start_btn._text_key = "start_btn"

        self.cancel_btn = ttk.Button(self.action_row, style="Secondary.TButton",
                                      command=self._cancel)
        self.cancel_btn._text_key = "cancel_btn"

        self.open_btn = ttk.Button(self.action_row, style="Secondary.TButton",
                                    command=self._open_output_folder)
        self.open_btn._text_key = "open_folder"

        self.status_box = tk.Frame(self.action_row); self.status_box._role = "surface"
        self.status_dot = tk.Label(self.status_box, text="●", font=self._font(11))
        self.status_dot._role = "status_dot"
        self.status_label = tk.Label(self.status_box, font=self._font(9))
        self.status_label._role = "status_text"

        self.hint_lbl = tk.Label(self.action_row, font=self._font(8))
        self.hint_lbl._text_key = "btn_hint"
        self.hint_lbl._role = "hint_surface"

        # progress bar (thin, under action row)
        self.progress = ttk.Progressbar(parent, mode="indeterminate",
                                         style="Accent.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 12))

    def _build_log_card(self, parent):
        card = tk.Frame(parent, highlightthickness=1)
        card._role = "card"
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card); inner._role = "card"
        inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

        head = tk.Frame(inner); head._role = "card"
        head.pack(fill=tk.X, pady=(0, 10))

        self.log_title = tk.Label(head, font=self._font(11, "bold"), anchor=tk.W)
        self.log_title._text_key = "log_title"
        self.log_title._role = "card_title"

        self.clear_btn = tk.Label(head, font=self._font(9), cursor="hand2")
        self.clear_btn._text_key = "log_clear"
        self.clear_btn._role = "ghost_small"
        self.clear_btn.bind("<Button-1>", lambda e: self._clear_log())
        self._attach_hover_small(self.clear_btn)

        text_container = tk.Frame(inner); text_container._role = "card"
        text_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            text_container, wrap=tk.WORD, font=(self.font_mono, 9),
            relief=tk.FLAT, borderwidth=0, padx=12, pady=10,
            highlightthickness=1, height=14)
        self.log_text._role = "log"

        self.log_scroll = ttk.Scrollbar(text_container, orient=tk.VERTICAL,
                                         command=self.log_text.yview,
                                         style="Vertical.TScrollbar")
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # empty-state overlay
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

    def _build_footer(self):
        self.footer = tk.Frame(self.root, height=28)
        self.footer._role = "footer"
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        self.footer_hint = tk.Label(self.footer, font=self._font(8))
        self.footer_hint._text_key = "footer_hint"
        self.footer_hint._role = "footer_text"
        self.footer_hint.pack(side=tk.LEFT, padx=20)

        self.version_lbl = tk.Label(self.footer, text=f"v{APP_VERSION}",
                                     font=self._font(8))
        self.version_lbl._role = "footer_text"
        self.version_lbl.pack(side=tk.RIGHT, padx=20)

    def _attach_hover_small(self, w):
        def on_enter(_e): w.config(bg=self.colors["card_hover"])
        def on_leave(_e): w.config(bg=self.colors["card"])
        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")

    # ============================
    # Theme
    # ============================

    def _apply_theme(self):
        self.colors = PALETTES[self.theme]
        c = self.colors
        self.root.config(bg=c["surface"])
        self._apply_ttk_styles()
        self._apply_roles_recursive(self.root)
        self._update_log_tags()
        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark"))
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
            "surface":       dict(bg=c["surface"]),
            "header":        dict(bg=c["header"]),
            "card":          dict(bg=c["card"], highlightbackground=c["border"]),
            "separator":     dict(bg=c["border"]),
            "footer":        dict(bg=c["surface"]),
            "title":         dict(bg=c["header"], fg=c["text"]),
            "subtitle":      dict(bg=c["header"], fg=c["text_sub"]),
            "card_title":    dict(bg=c["card"], fg=c["text"]),
            "field_label":   dict(bg=c["card"], fg=c["text_sub"]),
            "hint":          dict(bg=c["card"], fg=c["muted"]),
            "hint_surface":  dict(bg=c["surface"], fg=c["muted"]),
            "footer_text":   dict(bg=c["surface"], fg=c["muted"]),
            "ghost_btn":     dict(bg=c["header"], fg=c["text"]),
            "ghost_small":   dict(bg=c["card"], fg=c["accent"]),
            "status_dot":    dict(bg=c["surface"]),
            "status_text":   dict(bg=c["surface"], fg=c["text_sub"]),
            "empty_title":   dict(bg=c["log_bg"], fg=c["text_sub"]),
            "empty_sub":     dict(bg=c["log_bg"], fg=c["muted"]),
            "text_input":    dict(
                bg=c["input"], fg=c["text"], insertbackground=c["text"],
                highlightbackground=c["input_border"], highlightcolor=c["accent"],
                selectbackground=c["accent"], selectforeground=c["accent_fg"]),
            "log":           dict(
                bg=c["log_bg"], fg=c["log_fg"], insertbackground=c["log_fg"],
                highlightbackground=c["border"],
                selectbackground=c["accent"], selectforeground=c["accent_fg"]),
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

        # Entry
        s.configure("TEntry",
                    fieldbackground=c["input"], foreground=c["text"],
                    insertcolor=c["text"], bordercolor=c["input_border"],
                    lightcolor=c["input"], darkcolor=c["input"],
                    padding=(10, 8), relief="flat")
        s.map("TEntry",
              bordercolor=[("focus", c["accent"])],
              lightcolor=[("focus", c["accent"])],
              darkcolor=[("focus", c["accent"])])

        # Error entry (for validation)
        s.configure("Error.TEntry",
                    fieldbackground=c["input"], foreground=c["text"],
                    bordercolor=c["danger"], lightcolor=c["danger"],
                    darkcolor=c["danger"])

        # Primary
        s.configure("Primary.TButton",
                    background=c["accent"], foreground=c["accent_fg"],
                    bordercolor=c["accent"], lightcolor=c["accent"],
                    darkcolor=c["accent"], focuscolor=c["accent"],
                    padding=(20, 10), font=self._font(10, "bold"),
                    relief="flat")
        s.map("Primary.TButton",
              background=[("active", c["accent_hover"]),
                          ("pressed", c["accent_hover"]),
                          ("disabled", c["muted"])],
              bordercolor=[("active", c["accent_hover"])],
              lightcolor=[("active", c["accent_hover"])],
              darkcolor=[("active", c["accent_hover"])])

        # Secondary
        s.configure("Secondary.TButton",
                    background=c["card"], foreground=c["text"],
                    bordercolor=c["border_strong"], lightcolor=c["card"],
                    darkcolor=c["card"], focuscolor=c["card"],
                    padding=(14, 8), font=self._font(9), relief="flat")
        s.map("Secondary.TButton",
              background=[("active", c["card_hover"])],
              bordercolor=[("active", c["accent"])])

        # Checkbutton
        s.configure("TCheckbutton",
                    background=c["card"], foreground=c["text"],
                    focuscolor=c["card"], font=self._font(9))
        s.map("TCheckbutton", background=[("active", c["card"])])

        # Progress
        s.configure("Accent.Horizontal.TProgressbar",
                    troughcolor=c["surface"], background=c["accent"],
                    bordercolor=c["surface"], lightcolor=c["accent"],
                    darkcolor=c["accent"], thickness=4)

        # Scrollbar
        s.configure("Vertical.TScrollbar",
                    background=c["scrollbar"], troughcolor=c["log_bg"],
                    bordercolor=c["log_bg"], arrowcolor=c["text_sub"],
                    lightcolor=c["scrollbar"], darkcolor=c["scrollbar"])

    def _update_log_tags(self):
        c = self.colors
        self.log_text.config(bg=c["log_bg"], fg=c["log_fg"],
                              insertbackground=c["log_fg"],
                              highlightbackground=c["border"])
        self.log_text.tag_configure("time", foreground=c["muted"])
        self.log_text.tag_configure("info", foreground=c["log_fg"])
        self.log_text.tag_configure("success", foreground=c["success"])
        self.log_text.tag_configure("warn", foreground=c["warning"])
        self.log_text.tag_configure("error", foreground=c["danger"])

    # ============================
    # Language
    # ============================

    def _apply_language(self):
        self._apply_texts_recursive(self.root)
        self._apply_alignment_recursive(self.root)
        self._relayout()
        self._rerender_log()
        self.theme_btn.config(
            text=self._t("theme_light" if self.theme == "dark" else "theme_dark"),
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
        # Path rows
        for entry, btn in self._path_rows:
            entry.pack_forget(); btn.pack_forget()
            if rtl:
                btn.pack(side=tk.LEFT, padx=(0, 8))
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                btn.pack(side=tk.LEFT, padx=(8, 0))

        # Action row
        for w in (self.start_btn, self.cancel_btn, self.open_btn,
                  self.status_box, self.hint_lbl):
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

        # Status inner
        self.status_dot.pack_forget(); self.status_label.pack_forget()
        if rtl:
            self.status_dot.pack(side=tk.RIGHT)
            self.status_label.pack(side=tk.RIGHT, padx=(0, 6))
        else:
            self.status_dot.pack(side=tk.LEFT)
            self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        # Log header
        self.log_title.pack_forget(); self.clear_btn.pack_forget()
        if rtl:
            self.clear_btn.pack(side=tk.LEFT)
            self.log_title.pack(side=tk.RIGHT)
        else:
            self.log_title.pack(side=tk.LEFT)
            self.clear_btn.pack(side=tk.RIGHT)

        # Only show cancel while running, only show open after success
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

    # ============================
    # Browse / dialog
    # ============================

    def _browse_project(self):
        path = filedialog.askdirectory(title=self._t("dlg_project"))
        if path:
            self.project_var.set(path)
            self.output_var.set(os.path.join(path, "project_snapshot.txt"))
            self._reset_validation()
            self._show_toast(self._t("toast_saved"), "success")

    def _browse_output(self):
        initial = self.project_var.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title=self._t("dlg_output"),
            initialdir=initial,
            initialfile="project_snapshot.txt",
            defaultextension=".txt",
            filetypes=[(self._t("dlg_ft_text"), "*.txt"),
                       (self._t("dlg_ft_all"), "*.*")])
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

    # ============================
    # Log / status / toast
    # ============================

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
        color = {"idle": c["muted"], "running": c["accent"],
                 "success": c["success"], "error": c["danger"]}.get(state, c["muted"])
        try:
            self.status_dot.config(fg=color)
            self.status_label.config(text=self._t(key))
        except tk.TclError:
            pass

    def _show_toast(self, text, kind="info"):
        c = self.colors
        color = {"info": c["accent"], "success": c["success"],
                 "error": c["danger"]}.get(kind, c["accent"])
        if self._toast_widget is not None:
            try:
                self._toast_widget.destroy()
            except tk.TclError:
                pass
        toast = tk.Label(self.root, text=text, font=self._font(9, "bold"),
                          bg=color, fg="#ffffff", padx=18, pady=8)
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

    # ============================
    # Validation
    # ============================

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

    # ============================
    # Run / cancel
    # ============================

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
                    cancel_event=self.cancel_event)
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
            # show "open folder" button
            if self._rtl():
                self.open_btn.pack(side=tk.RIGHT, padx=(0, 6))
            else:
                self.open_btn.pack(side=tk.LEFT, padx=(6, 0))
        else:
            self._set_status("status_error", "error")


# ============================================================
# Entry point
# ============================================================

def main():
    root = tk.Tk()

    # load fonts BEFORE building UI (Tk needs them registered)
    font_mgr = FontManager(root)
    font_mgr.scan_and_load()

    app = SnapshotApp(root, font_mgr)
    root.mainloop()


if __name__ == "__main__":
    main()