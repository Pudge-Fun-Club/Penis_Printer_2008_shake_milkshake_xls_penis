"""Single-line font registry and loading.

Fonts are vendored under ``plotter/fonts/`` and loaded by path (no system font
lookup) so rendering is deterministic across machines.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

from plotter.artwork.pipeline import PlotterError
from plotter.text.humanize import Humanize, Warp, WordJitter

_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"


# Registry: font key -> file under plotter/fonts/. All are OTF-SVG single-line
# fonts: the true one-stroke geometry lives in their SVG table.
FONT_FILES = {
    "sans": "ReliefSingleLineOTF-SVG-Regular.otf",
    "hand": "ReliefSingleLineOTF-SVG-Regular.otf",
    "script": "MistralSingleLine-Regular.otf",
}

# Fonts that apply hand-printed humanization on top of their base file.
FONT_HUMANIZE = {
    "hand": Humanize(),
}

# Cursive fonts: join consecutive letters of a word into one continuous path so
# each word plots as a single pen-down (huge pen-lift reduction). We chain each
# letter's main stroke through a curved Bézier connector; dots/accents/crossbars
# are collected as separate "marks" plotted after the main paths.
FONT_CONNECT = {"script"}

# Fonts whose true single-line geometry lives in the OpenType SVG table (one open
# <path> per glyph) rather than the CFF/glyf outline. The CFF in these fonts is a
# *doubled* thin outline; the SVG table is the genuine single centreline.
FONT_SVG = {"sans", "hand", "script"}


# Cursive fonts get per-word humanization keyed here.
FONT_WORD_JITTER = {"script": WordJitter()}


FONT_WARP = {"script": Warp()}

def font_path(font: str) -> Path:
    name = FONT_FILES.get(font)
    if name is None:
        # Lazy import: plotter.services.fonts imports back into plotter.text.
        from plotter.services.fonts import user_font_path

        path = user_font_path(font)
        if path is None:
            raise PlotterError(f"Unbekannte Schrift: {font}")
        return path
    path = _FONT_DIR / name
    if not path.exists():
        raise PlotterError(f"Schriftdatei fehlt: {name}")
    return path


@lru_cache(maxsize=8)
def load_font(font: str) -> TTFont:
    return TTFont(str(font_path(font)))


def use_centerline(font: str) -> bool:
    if font in FONT_FILES:
        return False
    try:
        from plotter.services.fonts import PLOTTER_MODE, user_font_mode
    except ImportError:
        return False
    return user_font_mode(font) == PLOTTER_MODE
