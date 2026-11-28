"""Modern theme palettes + system theme detection."""

import sys

PALETTES = {
    "light": {
        "surface": "#f4f6f9",
        "surface_hover": "#eaedf2",
        "card": "#ffffff",
        "card_hover": "#f9fafc",
        "header": "#ffffff",
        "header_hover": "#f1f4f8",
        "border": "#e2e6ee",
        "border_strong": "#cbd2df",
        "text": "#0f172a",
        "text_sub": "#475569",
        "muted": "#8290a6",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_fg": "#ffffff",
        "input": "#f8fafc",
        "input_border": "#cbd5e1",
        "log_bg": "#f8fafc",
        "log_fg": "#0f172a",
        "success": "#16a34a",
        "warning": "#d97706",
        "danger": "#dc2626",
        "scrollbar": "#cbd5e1",
    },
    "dark": {
        "surface": "#0b0f17",
        "surface_hover": "#151c2c",
        "card": "#111827",
        "card_hover": "#192236",
        "header": "#0f1522",
        "header_hover": "#1a2438",
        "border": "#1e293b",
        "border_strong": "#334155",
        "text": "#f1f5f9",
        "text_sub": "#94a3b8",
        "muted": "#64748b",
        "accent": "#3b82f6",
        "accent_hover": "#60a5fa",
        "accent_fg": "#ffffff",
        "input": "#0b111e",
        "input_border": "#273549",
        "log_bg": "#080c14",
        "log_fg": "#e2e8f0",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "scrollbar": "#334155",
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

            v, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")

            return "light" if v else "dark"

        if sys.platform == "darwin":
            import subprocess

            out = (
                subprocess.check_output(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )

            return "dark" if out.lower() == "dark" else "light"

    except Exception:
        pass

    return "dark"


def resolve_theme(preference: str) -> str:
    """Turn a user preference ('system' / 'light' / 'dark') into a concrete theme."""
    if preference in ("light", "dark"):
        return preference

    return detect_system_theme()
