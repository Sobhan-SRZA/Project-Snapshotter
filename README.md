# Project Snapshotter (v2.2.0)

A desktop Python utility with a `Tkinter` GUI that recursively scans a project directory, filters unwanted files using `.gitignore`-style rules, and consolidates all UTF-8 text files into a single formatted `.txt` file for feeding codebase context into AI models.

---

## Overview & Purpose

Pasting an entire project file by file into an LLM prompt is slow, loses folder context, and wastes time. **Project Snapshotter** automates this workflow:

1. Recursively traverses your target project directory using `os.scandir`.
2. Applies built-in defaults (`.git/`, `node_modules/`, `__pycache__/`, `venv/`, `.venv/`, build/IDE folders, etc.), subdirectory `.gitignore` files, and custom patterns.
3. Skips non-UTF-8 binary files safely and writes all text files into one clean output file.
4. Displays live progress, file counts, skipped counts, and output size in a bilingual (`fa` / `en`) interface with light/dark themes and font zooming.

---

## Features

- **Bilingual GUI (`fa` / `en`):** Automatic RTL/LTR layout switching and Persian/English font selection (`FontManager`).
- **Light & Dark Themes:** Includes `light` and `dark` palettes with OS theme detection (`Ctrl+T` to toggle, `Ctrl+L` to switch language).
- **Full `.gitignore` Rule Engine:** Supports negation (`!`), directory-only rules (`dir/`), anchored paths (`/path`), `**`, `*`, `?`, character classes (`[...]`), and escaped characters.
- **Quick Ignore Presets & Custom Rules:** Add common patterns (`*.log`, `*.lock`, `tests/`, `docs/`, `*.env*`) with one click or enter comma/newline-separated rules.
- **Live Stats & Quick Actions:** Tracks included files, skipped items, and output size, with one-click **Open Folder** and **Copy Path** actions.
- **Optional Vector Icons:** Renders crisp SVG icons via `cairosvg` + `Pillow` when installed, with automatic fallback to Unicode glyphs.

---

## Project Structure

```text
├── main.py                  # Application entry point
├── Snapshotter.spec         # PyInstaller build specification
├── core/
│   ├── __init__.py
│   ├── config.py            # Metadata, defaults, window & zoom settings, author info
│   ├── fonts.py             # Font discovery, OS font loading & family selection
│   ├── gitignore_engine.py  # .gitignore parser and pattern matcher
│   ├── icons.py             # SVG icon renderer (cairosvg + Pillow) with fallbacks
│   ├── snapshot_engine.py   # Directory walker, filter pipeline & output writer
│   ├── strings.py           # Localized UI strings (fa / en)
│   └── themes.py            # Color palettes & system theme detection
└── ui/
    ├── __init__.py
    ├── app.py               # Main Tkinter application & event/thread handling
    └── widgets.py           # Custom ScrollableFrame widget

```

---

## Requirements & Setup

Core functionality relies on Python's standard library (`tkinter`, `os`, `re`, `sys`, `threading`, etc.). For vector SVG icons and building standalone executables:

```bash
python -m venv build_env
build_env\Scripts\activate    # Windows

pip install cairosvg pillow

```

---

## How to Use

1. Run the application:
```bash
python main.py

```


2. Select the **Source project directory** (the **Output file path** defaults to `project_snapshot.txt` inside the selected project folder, or you can pick a custom path).
3. Enable or disable `.gitignore` rules and add any custom ignore patterns or presets.
4. Click **Run Snapshot** (or press `F5` / `Ctrl+Enter`). Use **Cancel** or `Esc` to stop a running scan.

### Keyboard Shortcuts

| Shortcut                       | Action                           |
| ------------------------------ | -------------------------------- |
| `F5` / `Ctrl+Enter`            | Start snapshot                   |
| `Esc`                          | Cancel running task or close app |
| `Ctrl+T`                       | Toggle light/dark theme          |
| `Ctrl+L`                       | Switch language (`fa` / `en`)    |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / zoom out / reset zoom  |

### Example Output (`project_snapshot.txt`)

```plaintext
main.py

```

import tkinter as tk
...

```

core/config.py

```

APP_NAME = "Project Snapshotter"
APP_VERSION = "2.2.0"
...

```

```

---

## Building an Executable (`.exe`)

### Using Nuitka

Install Nuitka:

```bash
pip install nuitka

```

Build without icon:

```bash
python -m nuitka --standalone --onefile --windows-disable-console --include-data-dir=fonts=fonts --include-package=cairosvg --include-package=PIL --enable-plugin=tk-inter --output-filename=ProjectSnapshotter.exe main.py

```

Build with a Windows `.ico` icon:

```bash
python -m nuitka --standalone --onefile --windows-disable-console --windows-icon-from-ico=icon.ico --include-data-dir=fonts=fonts --include-package=cairosvg --include-package=PIL --enable-plugin=tk-inter --output-filename=ProjectSnapshotter.exe main.py

```

### Using PyInstaller & `.spec` Generation

#### 1. Generating a `.spec` File Automatically (`pyi-makespec`)

You can generate a `.spec` file directly from CLI flags instead of writing one from scratch:

```bash
pyi-makespec --onefile --noconsole \
  --name ProjectSnapshotter \
  --add-data "fonts;fonts" \
  --collect-all tkinter \
  --collect-all cairosvg \
  --collect-all PIL \
  --hidden-import PIL._imaging \
  main.py

```

> **Note:** On non-Windows shells, replace `;` with `:` in `--add-data "fonts:fonts"`. Passing `--icon=icon.ico` to `pyi-makespec` sets the `icon` argument inside the generated `.spec` file.

#### 2. Why a Custom `Snapshotter.spec` Is Used Here

A plain `pyi-makespec` output often misses dynamic/native bindings in `Tkinter`, `cairosvg` (Cairo/CFFI/shared libs), and `Pillow` (`PIL._imaging`), or fails when `fonts/` is optional/empty. `Snapshotter.spec` guards `collect_all` calls with `try/except`, dynamically bundles `.ttf`/`.otf` files from `fonts/`, and configures `EXE(..., console=False)`:

```python
# Snapshotter.spec
# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

# Bundled font files
fonts_dir = os.path.join(os.getcwd(), "fonts")
datas = []
if os.path.isdir(fonts_dir):
    for f in os.listdir(fonts_dir):
        if f.lower().endswith((".ttf", ".otf")):
            datas.append((os.path.join(fonts_dir, f), "fonts"))

# Collect full tkinter runtime data & binaries
tk_datas, tk_binaries, tk_hiddenimports = collect_all("tkinter")

# Collect optional cairosvg package if installed
try:
    cairo_datas, cairo_binaries, cairo_hiddenimports = collect_all("cairosvg")
except Exception:
    cairo_datas, cairo_binaries, cairo_hiddenimports = [], [], []

# Collect Pillow package if installed
try:
    pil_datas, pil_binaries, pil_hiddenimports = collect_all("PIL")
except Exception:
    pil_datas, pil_binaries, pil_hiddenimports = [], [], []

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=tk_binaries + cairo_binaries + pil_binaries,
    datas=datas + tk_datas + cairo_datas + pil_datas,
    hiddenimports=(
        tk_hiddenimports
        + cairo_hiddenimports
        + pil_hiddenimports
        + ["PIL._imaging"]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ProjectSnapshotter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico" if os.path.isfile("icon.ico") else None,
)

```

#### 3. Building from the `.spec` File

```bash
pip install pyinstaller cairosvg pillow
pyinstaller Snapshotter.spec --clean

```

Once a `.spec` file exists, options like `--onefile` vs. one-dir (`COLLECT`), `--noconsole` (`console=False`), `--add-data` (`datas`), and `--icon` are controlled inside the `.spec` file rather than repeated on the `pyinstaller` command line.

---

## Author & License

* **Author:** Sobhan-SRZA (`mr.sinre`) · Persian Caesar Team
* **Links:** [GitHub](https://github.com/Sobhan-SRZA) · [srza.ir](https://srza.ir)
* **License:** Released under the **MIT License** (see [`LICENSE`](./LICENSE)).