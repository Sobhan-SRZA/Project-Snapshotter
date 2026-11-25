"""Theme palettes + system theme detection."""

import sys

PALETTES = {
    "light": {
        "surface": "#f5f5f7",
        "surface_hover": "#ebebee",
        "card": "#ffffff",
        "card_hover": "#f8f8fa",
        "header": "#ffffff",
        "header_hover": "#f2f2f5",
        "border": "#e2e2e7",
        "border_strong": "#cdcdd3",
        "text": "#1c1c1e",
        "text_sub": "#6e6e73",
        "muted": "#98989d",
        "accent": "#007aff",
        "accent_hover": "#0066d6",
        "accent_fg": "#ffffff",
        "input": "#fbfbfd",
        "input_border": "#d4d4d9",
        "log_bg": "#fbfbfd",
        "log_fg": "#1c1c1e",
        "success": "#28a745",
        "warning": "#cc8800",
        "danger": "#d70015",
        "scrollbar": "#c7c7cc",
    },
    "dark": {
        "surface": "#0f0f10",
        "surface_hover": "#1c1c1e",
        "card": "#1c1c1e",
        "card_hover": "#252528",
        "header": "#161618",
        "header_hover": "#232326",
        "border": "#2c2c2e",
        "border_strong": "#3d3d40",
        "text": "#f2f2f7",
        "text_sub": "#a1a1a6",
        "muted": "#6e6e73",
        "accent": "#0a84ff",
        "accent_hover": "#3d9dff",
        "accent_fg": "#ffffff",
        "input": "#161618",
        "input_border": "#3a3a3d",
        "log_bg": "#0a0a0b",
        "log_fg": "#e5e5ea",
        "success": "#30d158",
        "warning": "#ffd60a",
        "danger": "#ff453a",
        "scrollbar": "#48484a",
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
    return "light"


def resolve_theme(preference: str) -> str:
    """Turn a user preference ('system' / 'light' / 'dark') into a concrete theme."""
    if preference in ("light", "dark"):
        return preference
    return detect_system_theme()
