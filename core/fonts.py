"""Font manager — loads custom fonts and picks per-language families."""

import os
import sys
import ctypes
import struct
import shutil
import tkinter as tk
import tkinter.font as tkfont
from typing import List, Optional, Tuple

from core.config import PROJECT_ROOT, FONTS_DIR


class FontManager:
    IRANSANS_NAMES = [
        "IRANSans",
        "IRANSansX",
        "IRANSansWeb",
        "IRAN Sans",
        "IRANSansXFaNum",
        "IRANSansXV",
        "IRANSans Light",
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

            if data[off : off + 4] == b"name":
                name_off = struct.unpack(">I", data[off + 8 : off + 12])[0]

                break

        if name_off is None or name_off + 6 > len(data):
            return None

        count = struct.unpack(">H", data[name_off + 2 : name_off + 4])[0]
        string_off = struct.unpack(">H", data[name_off + 4 : name_off + 6])[0]
        storage = name_off + string_off
        best = None
        for i in range(count):
            rec = name_off + 6 + i * 12
            if rec + 12 > len(data):
                break

            platform, _, _, name_id, length, offset = struct.unpack(
                ">HHHHHH", data[rec : rec + 12]
            )

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
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        ]

        gdi32.AddFontResourceExW.restype = ctypes.c_int
        if not gdi32.AddFontResourceExW(path, FR_PRIVATE, None):
            raise RuntimeError("AddFontResourceEx failed")

    def _load_unix(self, path: str):
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
        search_dirs = [
            FONTS_DIR,
            PROJECT_ROOT,
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

        try:
            self.root.update_idletasks()

        except Exception:
            pass

    def _available(self) -> set:
        try:
            return set(tkfont.families(self.root))

        except Exception:
            return set()

    def pick_ui_fonts(self) -> Tuple[str, str]:
        """Returns (en_family, fa_family)."""
        avail = self._available()

        fa = None

        for name in self.IRANSANS_NAMES + self.VAZIR_NAMES:
            if name in avail:
                fa = name

                break

        if not fa:
            for fam in self.loaded_families:
                low = fam.lower()

                if any(
                    k in low
                    for k in (
                        "iran",
                        "vazir",
                        "noto naskh",
                        "noto sans arabic",
                        "tahoma",
                    )
                ):
                    fa = fam

                    break

        en = None

        for fam in self.loaded_families:
            low = fam.lower()
            if any(k in low for k in ("iran", "vazir")):
                continue

            en = fam

            break

        if not en:
            sys_candidates = (
                ["Segoe UI", "Tahoma", "Arial"]
                if sys.platform.startswith("win")
                else (
                    ["SF Pro Text", "Helvetica Neue", "Tahoma"]
                    if sys.platform == "darwin"
                    else ["Ubuntu", "Cantarell", "DejaVu Sans", "Tahoma"]
                )
            )

            for name in sys_candidates:
                if name in avail:
                    en = name

                    break

        if not en:
            en = fa or "TkDefaultFont"

        if not fa:
            fa = en

        self._log(f"UI fonts: en='{en}', fa='{fa}'")

        return en, fa

    def pick_ui_font(self) -> str:
        en, _ = self.pick_ui_fonts()

        return en

    def pick_mono_font(self) -> str:
        avail = self._available()
        for name in [
            "JetBrains Mono",
            "Cascadia Code",
            "Consolas",
            "Menlo",
            "Monaco",
            "DejaVu Sans Mono",
            "Courier New",
        ]:
            if name in avail:
                return name

        return "TkFixedFont"
