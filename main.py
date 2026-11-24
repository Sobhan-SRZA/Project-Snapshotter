"""
Project Snapshotter GUI
نسخه گرافیکی اسکریپت اسنپ‌شات پروژه

این برنامه پوشه پروژه را پیمایش کرده و محتوای تمام فایل‌های متنی را
در یک فایل خروجی ترکیب می‌کند. مسیر خروجی به طور پیش‌فرض داخل پوشه پروژه
انتخاب می‌شود و کاربر می‌تواند آن را تغییر دهد.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import Set
import fnmatch
import os
import threading

# استثناهای پیش‌فرض که همیشه اعمال می‌شوند
DEFAULT_EXCLUSIONS = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".vscode",
    ".idea",
    "dist",
    "build",
    "*.pyc",
    "*.tmp",
    ".DS_Store",
}


# ---------------- منطق اصلی (بدون تغییر) ----------------


def parse_gitignore(gitignore_path: str) -> Set[str]:
    """خواندن الگوها از فایل .gitignore"""
    patterns = set()
    if not os.path.isfile(gitignore_path):
        return patterns
    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    patterns.add(stripped_line)
    except Exception as e:
        print(
            f"Warning: Could not read .gitignore file at {gitignore_path}. Error: {e}"
        )
    return patterns


def create_project_snapshot(
    root_dir: str, exclude_patterns: Set[str], output_file_path: str, log_func=print
) -> bool:
    """
    ساخت فایل اسنپ‌شات پروژه.
    log_func برای دریافت پیام‌ها استفاده می‌شود (برای GUI).
    """
    output_filename = os.path.basename(output_file_path)
    all_file_contents = []
    processed_count = 0
    skipped_count = 0

    log_func("در حال پیمایش پوشه پروژه...")

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # هرس پوشه‌های مستثنی (in-place)
        dirs_to_keep = [
            d
            for d in dirnames
            if not any(fnmatch.fnmatch(d, p) for p in exclude_patterns)
        ]
        dirnames[:] = dirs_to_keep

        for filename in filenames:
            if filename == output_filename:
                continue

            file_path = os.path.join(dirpath, filename)

            try:
                relative_path = os.path.relpath(file_path, root_dir).replace(
                    os.sep, "/"
                )
            except ValueError:
                log_func(f"⚠️ رد شد (درایو متفاوت): {file_path}")
                skipped_count += 1
                continue

            if any(
                fnmatch.fnmatch(filename, p) or fnmatch.fnmatch(relative_path, p)
                for p in exclude_patterns
            ):
                skipped_count += 1
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                formatted_block = f"{relative_path}\n```\n{content}\n```\n\n"
                all_file_contents.append(formatted_block)
                processed_count += 1
            except UnicodeDecodeError:
                log_func(f"⚠️ فایل باینری/غیر UTF-8: {relative_path}")
                skipped_count += 1
            except IOError as e:
                log_func(f"❌ خطا در خواندن {relative_path}: {e}")
                skipped_count += 1
            except Exception as e:
                log_func(f"❌ خطای غیرمنتظره {relative_path}: {e}")
                skipped_count += 1

    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_file_contents))
        log_func(
            f"✅ موفق! {processed_count} فایل پردازش شد، {skipped_count} فایل رد شد."
        )
        log_func(f"📁 فایل خروجی: {output_file_path}")
        return True
    except Exception as e:
        log_func(f"❌ خطای بحرانی در نوشتن فایل خروجی: {e}")
        return False


# ---------------- رابط گرافیکی ----------------


class SnapshotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Project Snapshotter - اسنپ‌شات پروژه")
        self.root.geometry("820x720")
        self.root.minsize(700, 600)

        self.running = False
        self.build_ui()

    # ----- ساخت رابط -----
    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # --- ردیف مسیر پروژه ---
        row1 = ttk.Frame(main)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="مسیر پروژه:", width=15).pack(side=tk.LEFT)
        self.project_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.project_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row1, text="انتخاب پوشه...", command=self.browse_project).pack(
            side=tk.LEFT
        )

        # --- ردیف مسیر خروجی ---
        row2 = ttk.Frame(main)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="مسیر خروجی:", width=15).pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row2, text="ذخیره در...", command=self.browse_output).pack(
            side=tk.LEFT
        )

        # --- گزینه‌های استثنا ---
        options = ttk.LabelFrame(main, text="تنظیمات استثنا", padding=8)
        options.pack(fill=tk.X, pady=8)

        self.use_gitignore_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options,
            text="استفاده از قوانین .gitignore (در صورت وجود)",
            variable=self.use_gitignore_var,
        ).pack(anchor=tk.W)

        ttk.Label(options, text="الگوهای دستی (با کاما یا خط جدید جدا کنید):").pack(
            anchor=tk.W, pady=(8, 2)
        )
        self.exclude_text = tk.Text(options, height=3, wrap=tk.WORD)
        self.exclude_text.pack(fill=tk.X)

        ttk.Label(options, text="استثناهای پیش‌فرض (همیشه اعمال می‌شوند):").pack(
            anchor=tk.W, pady=(8, 2)
        )
        default_display = tk.Text(
            options, height=3, wrap=tk.WORD, background="#f0f0f0", state=tk.DISABLED
        )
        default_display.pack(fill=tk.X)
        default_display.config(state=tk.NORMAL)
        default_display.insert(tk.END, ", ".join(sorted(DEFAULT_EXCLUSIONS)))
        default_display.config(state=tk.DISABLED)

        # --- دکمه شروع و Progress ---
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=10)
        self.start_btn = ttk.Button(
            btn_frame, text="🚀 شروع ساخت اسنپ‌شات", command=self.start_snapshot
        )
        self.start_btn.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="آماده")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 8))

        # --- ناحیه لاگ ---
        log_frame = ttk.LabelFrame(main, text="گزارش عملیات", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=14, wrap=tk.WORD, state=tk.NORMAL
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ----- انتخاب مسیرها -----
    def browse_project(self):
        path = filedialog.askdirectory(title="انتخاب پوشه اصلی پروژه")
        if path:
            self.project_var.set(path)
            # پیش‌فرض: خروجی داخل همان پوشه پروژه
            self.output_var.set(os.path.join(path, "project_snapshot.txt"))

    def browse_output(self):
        initial_dir = self.project_var.get().strip() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="محل ذخیره فایل خروجی",
            initialdir=initial_dir,
            initialfile="project_snapshot.txt",
            defaultextension=".txt",
            filetypes=[("فایل متنی", "*.txt"), ("همه فایل‌ها", "*.*")],
        )
        if path:
            self.output_var.set(path)

    # ----- لاگ thread-safe -----
    def log(self, msg: str):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg: str):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    # ----- اجرا -----
    def start_snapshot(self):
        if self.running:
            return

        project = self.project_var.get().strip()
        output = self.output_var.get().strip()

        if not project or not os.path.isdir(project):
            messagebox.showerror("خطا", "مسیر پروژه معتبر نیست.")
            return
        if not output:
            messagebox.showerror("خطا", "مسیر خروجی مشخص نشده است.")
            return

        # ساخت مجموعه استثناها
        exclude = set(DEFAULT_EXCLUSIONS)

        # ۱) از gitignore
        if self.use_gitignore_var.get():
            gi = os.path.join(project, ".gitignore")
            if os.path.isfile(gi):
                patterns = parse_gitignore(gi)
                exclude.update(patterns)
                self.log(f"📄 {len(patterns)} الگو از .gitignore بارگذاری شد.")
            else:
                self.log("ℹ️ فایل .gitignore یافت نشد.")

        # ۲) الگوهای دستی
        manual = self.exclude_text.get("1.0", tk.END).strip()
        if manual:
            # هم کاما و هم خط جدید را جداکننده در نظر می‌گیریم
            for p in manual.replace("\n", ",").split(","):
                p = p.strip()
                if p:
                    exclude.add(p)
            self.log(f"➕ الگوهای دستی اضافه شد (مجموع: {len(exclude)} الگو).")

        # قفل کردن UI
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.status_var.set("در حال اجرا...")
        self.progress.start(12)
        self.log_text.delete("1.0", tk.END)

        # اجرا در Thread جداگانه
        def worker():
            try:
                create_project_snapshot(project, exclude, output, self.log)
            finally:
                self.root.after(0, self.finish)

        threading.Thread(target=worker, daemon=True).start()

    def finish(self):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.status_var.set("آماده")
        self.progress.stop()


# ----- اجرای برنامه -----
if __name__ == "__main__":
    root = tk.Tk()
    try:
        # استفاده از تم به‌روزتر در ویندوز/لینوکس
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = SnapshotApp(root)
    root.mainloop()
