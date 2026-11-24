"""
Project Snapshotter GUI
پیاده‌سازی کامل .gitignore سازگار با git + رابط گرافیکی

قابلیت‌های موتور gitignore:
  ✓ negation با !
  ✓ trailing slash برای الگوهای مخصوص پوشه
  ✓ leading slash برای anchored کردن
  ✓ ** globstar (شروع، وسط، پایان)
  ✓ کاراکتر کلاس []
  ✓ escape با backslash
  ✓ حذف فاصله‌های انتهایی (به‌جز escape شده)
  ✓ ترتیب اهمیت دارد (آخری برنده)
  ✓ پشتیبانی از .gitignore تو در تو در همه زیرپوشه‌ها
  ✓ رفتار «اگر پوشه ignore شد، محتوایش قابل بازگردانی نیست»
"""

import os
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from typing import List, Optional

# ============================================================
# بخش ۱: موتور تطبیق .gitignore
# ============================================================


class GitIgnorePattern:
    """یک قانون مستقل از .gitignore."""

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

        # --- ۱) خط خالی یا comment ---
        if not p or p.startswith("#"):
            self.valid = False
            return

        # --- ۲) negation ---
        if p.startswith("!"):
            self.negation = True
            p = p[1:]
        elif p.startswith("\\!") or p.startswith("\\#"):
            # escape شده: کاراکتر واقعی است
            p = p[1:]

        # --- ۳) حذف فاصله‌های انتهایی (escape نشده) ---
        p = self._rstrip_unescaped_spaces(p)
        if not p:
            self.valid = False
            return

        # --- ۴) الگوی مخصوص پوشه ---
        if p.endswith("/"):
            self.directory_only = True
            p = p[:-1]
            if not p:
                self.valid = False
                return

        # --- ۵) anchor ---
        if p.startswith("/"):
            self.anchored = True
            p = p[1:]
        elif "/" in p:
            self.anchored = True

        # --- ۶) glob → regex ---
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
            j = len(p) - 2
            bs = 0
            while j >= 0 and p[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 1:  # فاصله escape شده → نگه دار
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
                        out.append("(?:.*/)?")  # **/
                        i += 3
                    elif i + 2 == n:
                        out.append(".*")  # /**
                        i += 2
                    else:
                        out.append("[^/]*")  # ** وسط
                        i += 2
                else:
                    out.append("[^/]*")  # *
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
    """خواندن یک فایل .gitignore و بازگرداندن لیست قوانین."""
    patterns: List[GitIgnorePattern] = []
    if not os.path.isfile(path):
        return patterns
    try:
        with open(path, "r", encoding="utf-8-sig") as f:  # utf-8-sig: BOM-safe
            for line in f:
                line = line.rstrip("\r\n")
                r = GitIgnorePattern(line)
                if r.valid:
                    patterns.append(r)
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
    return patterns


class GitIgnoreMatcher:
    """مجموعه‌ای از قوانین که به ترتیب ارزیابی می‌شوند (آخری برنده)."""

    def __init__(self, rules: Optional[List[GitIgnorePattern]] = None):
        self.rules: List[GitIgnorePattern] = list(rules) if rules else []

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
    rules = [r for r in (GitIgnorePattern(line) for line in defaults) if r.valid]
    return GitIgnoreMatcher(rules)


# ============================================================
# بخش ۲: منطق ساخت اسنپ‌شات
# ============================================================


def create_snapshot(
    root_dir: str,
    include_gitignore: bool,
    extra_patterns: List[str],
    output_file_path: str,
    log_func=print,
) -> bool:
    output_abs = os.path.abspath(output_file_path)

    # matcher پایه: پیش‌فرض‌ها + الگوهای دستی
    base = build_default_matcher()
    manual_rules = [
        r for r in (GitIgnorePattern(line) for line in extra_patterns) if r.valid
    ]
    base.add(manual_rules)
    if manual_rules:
        log_func(f"➕ {len(manual_rules)} الگوی دستی اضافه شد.")

    all_contents: List[str] = []
    stats = {"processed": 0, "skipped": 0}

    log_func("🚀 شروع پیمایش...")

    # --- پیمایش بازگشتی با پشتیبانی از .gitignore تو در تو ---
    def walk(dir_path: str, rel_dir: str, matcher: GitIgnoreMatcher):
        # اضافه‌کردن .gitignore این پوشه (اگر مجاز باشد)
        current = matcher
        if include_gitignore:
            gi_path = os.path.join(dir_path, ".gitignore")
            if os.path.isfile(gi_path):
                rules = parse_gitignore_file(gi_path)
                if rules:
                    current = matcher.copy()
                    current.add(rules)
                    rel_gi = f"{rel_dir}/.gitignore" if rel_dir else ".gitignore"
                    log_func(f"📄 {len(rules)} الگو از {rel_gi}")

        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except (PermissionError, OSError) as e:
            log_func(f"⚠️ دسترسی به {dir_path} ممکن نیست: {e}")
            return

        for entry in entries:
            name = entry.name
            full = entry.path
            rel = f"{rel_dir}/{name}" if rel_dir else name

            try:
                is_dir = entry.is_dir()
            except OSError:
                stats["skipped"] += 1
                continue

            # فایل خروجی خودمان را نادیده بگیر
            if not is_dir and os.path.abspath(full) == output_abs:
                continue

            # --- اعمال قوانین gitignore ---
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
                        log_func(f"⏳ {stats['processed']} فایل پردازش شد...")
                except UnicodeDecodeError:
                    stats["skipped"] += 1
                except (IOError, OSError) as e:
                    log_func(f"❌ خطا در خواندن {rel}: {e}")
                    stats["skipped"] += 1

    try:
        walk(root_dir, "", base)
    except Exception as e:
        log_func(f"❌ خطای غیرمنتظره: {e}")
        return False

    # --- نوشتن خروجی ---
    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_contents))
        log_func(
            f"✅ تمام شد! {stats['processed']} فایل نوشته شد، "
            f"{stats['skipped']} مورد رد شد."
        )
        log_func(f"📁 خروجی: {output_file_path}")
        return True
    except Exception as e:
        log_func(f"❌ خطای بحرانی در نوشتن: {e}")
        return False


# ============================================================
# بخش ۳: رابط گرافیکی
# ============================================================


class SnapshotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Project Snapshotter — اسنپ‌شات پروژه")
        self.root.geometry("880x780")
        self.root.minsize(720, 640)
        self.running = False
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # --- مسیر پروژه ---
        row = ttk.Frame(main)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="مسیر پروژه:", width=14).pack(side=tk.LEFT)
        self.project_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.project_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row, text="انتخاب...", command=self._browse_project).pack(
            side=tk.LEFT
        )

        # --- مسیر خروجی ---
        row = ttk.Frame(main)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="مسیر خروجی:", width=14).pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row, text="ذخیره در...", command=self._browse_output).pack(
            side=tk.LEFT
        )

        # --- گزینه‌ها ---
        opts = ttk.LabelFrame(main, text="تنظیمات ignore", padding=8)
        opts.pack(fill=tk.X, pady=8)

        self.use_gitignore_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts,
            variable=self.use_gitignore_var,
            text="اعمال فایل‌های .gitignore (شامل زیرپوشه‌ها — سازگار با Git)",
        ).pack(anchor=tk.W)

        ttk.Label(opts, text="الگوهای دستی (هر خط یک الگو یا با کاما جدا کنید):").pack(
            anchor=tk.W, pady=(8, 2)
        )
        self.exclude_text = tk.Text(opts, height=4, wrap=tk.WORD)
        self.exclude_text.pack(fill=tk.X)

        hint = (
            "سینتکس پشتیبانی‌شده: !negation، dir/ (فقط پوشه)، /anchored، "
            "**  (بازگشتی)، ? و [] و \\escape"
        )
        ttk.Label(opts, text=hint, foreground="#666").pack(anchor=tk.W, pady=(2, 6))

        ttk.Label(opts, text="استثناهای پیش‌فرض (همیشه اعمال می‌شوند):").pack(
            anchor=tk.W, pady=(4, 2)
        )
        dflt = tk.Text(
            opts, height=3, wrap=tk.WORD, background="#f0f0f0", state=tk.DISABLED
        )
        dflt.pack(fill=tk.X)
        dflt.config(state=tk.NORMAL)
        dflt.insert(
            tk.END,
            ".git/  node_modules/  __pycache__/  *.pyc  *.tmp  "
            "venv/  .venv/  .vscode/  .idea/  dist/  build/  .DS_Store",
        )
        dflt.config(state=tk.DISABLED)

        # --- دکمه اجرا ---
        bar = ttk.Frame(main)
        bar.pack(fill=tk.X, pady=10)
        self.start_btn = ttk.Button(
            bar, text="🚀 شروع ساخت اسنپ‌شات", command=self._start
        )
        self.start_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 8))

        # --- لاگ ---
        log_frame = ttk.LabelFrame(main, text="گزارش", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=16, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

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
            filetypes=[("متنی", "*.txt"), ("همه", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _log(self, msg: str):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg: str):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _start(self):
        if self.running:
            return

        project = self.project_var.get().strip()
        output = self.output_var.get().strip()

        if not project or not os.path.isdir(project):
            self._log("❌ مسیر پروژه معتبر نیست.")
            return
        if not output:
            self._log("❌ مسیر خروجی مشخص نشده.")
            return

        # استخراج الگوهای دستی (کاما یا خط جدید)
        raw = self.exclude_text.get("1.0", tk.END)
        patterns = [p.strip() for p in raw.replace(",", "\n").split("\n") if p.strip()]

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.status_var.set("در حال اجرا...")
        self.progress.start(12)
        self.log_text.delete("1.0", tk.END)

        def worker():
            try:
                ok = create_snapshot(
                    project,
                    include_gitignore=self.use_gitignore_var.get(),
                    extra_patterns=patterns,
                    output_file_path=output,
                    log_func=self._log,
                )
                if ok:
                    self._log("─" * 50)
            finally:
                self.root.after(0, self._finish)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.status_var.set("آماده")
        self.progress.stop()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        s = ttk.Style()
        for theme in ("vista", "clam", "alt"):
            if theme in s.theme_names():
                s.theme_use(theme)
                break
    except Exception:
        pass
    SnapshotApp(root)
    root.mainloop()
