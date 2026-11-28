"""
Clean vector SVG icon set rendered via cairosvg + Pillow with clean fallbacks.
Optional dependency for crisp vector icons:
    pip install cairosvg pillow
"""

from typing import Tuple

try:
    import io
    import cairosvg
    from PIL import Image, ImageTk

    _SVG_AVAILABLE = True
except Exception:
    _SVG_AVAILABLE = False

_STROKE = (
    'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.9" '
    'stroke-linecap="round" stroke-linejoin="round"'
)

SVG_ICONS = {
    "layers": f'<svg {_STROKE}><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    "sun": f'<svg {_STROKE}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>',
    "moon": f'<svg {_STROKE}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    "globe": f'<svg {_STROKE}><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    "zoom-in": f'<svg {_STROKE}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M11 8v6M8 11h6"/></svg>',
    "zoom-out": f'<svg {_STROKE}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M8 11h6"/></svg>',
    "folder": f'<svg {_STROKE}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "folder-open": f'<svg {_STROKE}><path d="M6 14l1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h5"/></svg>',
    "filter": f'<svg {_STROKE}><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>',
    "terminal": f'<svg {_STROKE}><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
    "trash": f'<svg {_STROKE}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    "copy": f'<svg {_STROKE}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    "play": f'<svg {_STROKE}><polygon points="5 3 19 12 5 21 5 3"/></svg>',
    "stop": f'<svg {_STROKE}><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
    "github": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2c-3.2.69-3.87-1.36-3.87-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.04 1.78 2.72 1.27 3.38.97.1-.75.4-1.27.73-1.56-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.06 11.06 0 0 1 5.8 0c2.21-1.49 3.18-1.18 3.18-1.18.63 1.58.23 2.75.11 3.04.74.81 1.19 1.84 1.19 3.1 0 4.43-2.7 5.41-5.26 5.69.41.35.78 1.05.78 2.12v3.14c0 .31.21.68.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5z"/></svg>',
    "external": f'<svg {_STROKE}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
}

FALLBACK_CHARS = {
    "layers": "❖",
    "sun": "☀",
    "moon": "☾",
    "globe": "🌐",
    "zoom-in": "＋",
    "zoom-out": "－",
    "folder": "📁",
    "folder-open": "📂",
    "filter": "▽",
    "terminal": ">_",
    "trash": "✕",
    "copy": "❐",
    "play": "▶",
    "stop": "■",
    "github": "◆",
    "external": "↗",
}

_CACHE: dict = {}


def has_svg_support() -> bool:
    return _SVG_AVAILABLE


def get_icon(name: str, size: int = 16, fg: str = "#000000") -> Tuple[str, object]:
    """
    Returns ("image", PhotoImage) if cairosvg+Pillow are available,
    otherwise ("text", unicode_glyph).
    Cached by (name, size, fg).
    """
    if name not in SVG_ICONS:
        return ("text", FALLBACK_CHARS.get(name, "•"))

    if _SVG_AVAILABLE:
        key = (name, size, fg)
        if key not in _CACHE:
            try:
                svg = SVG_ICONS[name].replace("currentColor", fg)
                png = cairosvg.svg2png(
                    bytestring=svg.encode("utf-8"),
                    output_width=size,
                    output_height=size,
                )
                img = Image.open(io.BytesIO(png)).convert("RGBA")
                _CACHE[key] = ImageTk.PhotoImage(img)
            except Exception:
                _CACHE[key] = None

        img = _CACHE.get(key)
        if img is not None:
            return ("image", img)

    return ("text", FALLBACK_CHARS.get(name, "•"))
