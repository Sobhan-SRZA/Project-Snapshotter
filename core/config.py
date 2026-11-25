"""
Project Snapshotter — Centralized configuration & metadata.
All defaults & author info live here.
"""

import os

# ---------- App metadata ----------
APP_NAME = "Project Snapshotter"
APP_VERSION = "2.0.0"

# ---------- Project paths ----------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(PROJECT_ROOT, "fonts")

# ---------- Default settings ----------
DEFAULT_LANG = "en"  # "fa" | "en"
DEFAULT_THEME = "system"  # "system" | "light" | "dark"
DEFAULT_USE_GITIGNORE = True
DEFAULT_OUTPUT_NAME = "project_snapshot.txt"

# ---------- Window ----------
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 920
WINDOW_MIN_WIDTH = 840
WINDOW_MIN_HEIGHT = 760

# ---------- Font zoom ----------
MIN_FONT_SCALE = 0.7
MAX_FONT_SCALE = 2.0
FONT_SCALE_STEP = 0.1

# ---------- Author / credits ----------
AUTHOR_NAME = "Sobhan-SRZA (mr.sinre)"
AUTHOR_TEAM = "Persian Caesar Team"
COPYRIGHT_YEAR = "2025-2026"
GITHUB_URL = "https://github.com/Sobhan-SRZA"
GITHUB_DISPLAY = "GitHub"
WEBSITE_URL = "https://srza.ir"
WEBSITE_DISPLAY = "srza.ir"
