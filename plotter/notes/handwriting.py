"""Original Cyrillic centreline glyphs, with the bundled Latin stroke font.

Coordinates are y-down, with a 10-unit capital height. These are pen strokes,
not filled outlines. Style transformations stay deterministic for previews.
"""

from __future__ import annotations

import random
import zlib
from functools import lru_cache

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from plotter.services.errors import ServiceError
from plotter.text.flatten import recording_to_strokes
from plotter.text.fonts import load_font
from plotter.text.render import glyph_strokes

STYLES = [
    {"id": "notes-neat", "label": "Аккуратный"},
    {"id": "notes-slant", "label": "Наклонный"},
    {"id": "notes-human", "label": "Живой"},
]

# Original hand-printed letterforms. Curves are flattened before plotting.
_CYRILLIC = {
    "Б": "M7 0H1V10H4C9 10 9 5 4 5H1",
    "Г": "M1 10V0H7",
    "Д": "M0 12V10H9V12M1 10L3 0H7V10",
    "Ж": "M1 0L8 10M8 0L1 10M4.5 0V10",
    "З": "M1 1C8 -3 9 5 4 5C10 5 9 13 1 9",
    "И": "M1 0V10L7 0V10",
    "Й": "M1 0V10L7 0V10M2 -2Q4 -0.5 6 -2",
    "Л": "M0 10Q2 10 3 0H7V10",
    "П": "M1 10V0H7V10",
    "У": "M1 0L4 6M8 0L3 10H1",
    "Ф": "M4.5 0V10M4.5 1C-1 1 -1 9 4.5 9C10 9 10 1 4.5 1",
    "Ц": "M1 0V10H7V0M7 10H9V12",
    "Ч": "M1 0V4Q1 6 7 5M7 0V10",
    "Ш": "M1 0V10H9V0M5 0V10",
    "Щ": "M1 0V10H9V0M5 0V10M9 10H11V12",
    "Ъ": "M0 0H3V10H5C10 10 10 5 5 5H3",
    "Ы": "M1 0V10H4C8 10 8 5 4 5H1M9 0V10",
    "Ь": "M1 0V10H4C9 10 9 5 4 5H1",
    "Э": "M1 1C10 -3 10 13 1 9M4 5H8",
    "Ю": "M1 0V10M1 5H4M7 0C3 0 3 10 7 10C11 10 11 0 7 0",
    "Я": "M7 10V0H4C-1 0 -1 5 4 5H7M4 5L0 10",
    "а": "M6 4C0 0 -1 10 3 10Q6 10 6 4V10Q6 11 8 9",
    "б": "M6 0Q2 2 1 6C-1 12 8 12 7 6Q6 3 1 6",
    "в": "M1 10V4C8 1 8 7 1 7C9 5 9 11 1 10",
    "г": "M1 4Q7 1 5 6L2 9Q1 11 7 10",
    "д": "M6 4C0 0 -1 10 3 10Q6 10 6 4V12C6 16 0 15 2 12L8 9",
    "е": "M1 7H6C8 3 1 2 1 7C0 11 5 11 7 9",
    "ё": "M1 7H6C8 3 1 2 1 7C0 11 5 11 7 9M2 1H2.5M5 1H5.5",
    "ж": "M0 4L7 10M7 4L0 10M3.5 4V10",
    "з": "M1 4C7 2 8 7 3 7C10 7 7 16 1 13",
    "и": "M1 4V8Q1 12 6 8V4M6 8V10Q6 11 8 9",
    "й": "M1 4V8Q1 12 6 8V4M6 8V10Q6 11 8 9M2 1Q4 3 6 1",
    "к": "M1 4V10M6 4L1 7L7 10",
    "л": "M0 10Q2 10 3 4L6 10Q7 11 8 9",
    "м": "M0 10L2 4L5 10L7 4L9 10",
    "н": "M1 4V10M6 4V10M1 7H6",
    "о": "M4 4C0 3 0 11 4 10C8 11 8 3 4 4",
    "п": "M1 10V4Q6 2 6 6V10",
    "р": "M1 14V4M1 5C8 0 9 11 1 10",
    "с": "M6 5C1 1 -1 10 4 10Q6 10 7 9",
    "т": "M1 10V4Q4 2 4 6V10M4 6Q7 2 7 6V10",
    "у": "M1 4V8Q1 11 6 8M6 4V12C6 16 0 15 2 12L8 9",
    "ф": "M4.5 1V14M4.5 5C-1 1 -1 13 4.5 9C10 13 10 1 4.5 5",
    "х": "M1 4L7 10M7 4L1 10",
    "ц": "M1 4V8Q1 12 6 8V4M6 8V10H8V13",
    "ч": "M1 4V6Q1 9 6 7M6 4V10",
    "ш": "M1 4V8Q1 12 5 8V4M5 8Q5 12 9 8V4",
    "щ": "M1 4V8Q1 12 5 8V4M5 8Q5 12 9 8V4M9 8V10H11V13",
    "ъ": "M0 4H2V10H4C9 10 9 6 4 6H2",
    "ы": "M1 4V10H3C8 10 8 6 3 6H1M8 4V10",
    "ь": "M1 4V10H3C8 10 8 6 3 6H1",
    "э": "M1 5C8 1 9 13 1 9M3 7H7",
    "ю": "M1 4V10M1 7H4M7 4C3 3 3 11 7 10C11 11 11 3 7 4",
    "я": "M6 10V4H3C-1 4 -1 7 3 7H6M3 7L0 10",
}
_LATIN_ALIASES = dict(zip("АВЕКМНОРСТХ", "ABEKMHOPCTX", strict=True))
_SYMBOLS = {
    "−": "-",
    "–": "-",
    "—": "-",
    "«": '"',
    "»": '"',
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "×": "M1 3L7 9M7 3L1 9",
    "÷": "M1 6H7M3.8 3H4.2M3.8 9H4.2",
    "±": "M1 5H7M4 2V8M1 10H7",
    "→": "M0 6H9L6 3M9 6L6 9",
    "≤": "M7 2L1 5L7 8M1 10H7",
    "≥": "M1 2L7 5L1 8M1 10H7",
    "≠": "M1 4H7M1 8H7M6 2L2 10",
    "√": "M0 7L2 10L4 1H9",
    "²": "M1 1C5 -2 7 1 4 3L1 5H6",
    "³": "M1 0C7 -2 7 3 3 3C8 3 7 7 1 5",
    "°": "M3 0C0 0 0 3 3 3C6 3 6 0 3 0",
    "∞": "M4 6C-2 0 -2 12 4 6C10 0 10 12 4 6",
}


@lru_cache(maxsize=512)
def glyph(ch: str) -> tuple[list[list[tuple[float, float]]], float]:
    if ch.isspace():
        return [], 4.0
    path = _CYRILLIC.get(ch)
    if ch == "Ё":
        base, advance = glyph("Е")
        return [*base, [(2, -2), (2.5, -2)], [(5, -2), (5.5, -2)]], advance
    symbol = _SYMBOLS.get(ch)
    if symbol and symbol.startswith("M"):
        path = symbol
    elif symbol:
        lines, cursor = [], 0.0
        for part in symbol:
            strokes, advance = glyph(part)
            lines.extend([[(x + cursor, y) for x, y in line] for line in strokes])
            cursor += advance
        return lines, cursor
    if path:
        pen = RecordingPen()
        parse_path(path, TransformPen(pen, (100, 0, 0, 100, 0, 0)))
        lines = [[(x / 100, y / 100) for x, y in line] for line in recording_to_strokes(pen.value)]
        return lines, max(x for line in lines for x, _ in line) + 1.5
    tt = load_font("sans")
    cmap = tt.getBestCmap() or {}
    name = cmap.get(ord(_LATIN_ALIASES.get(ch, ch)))
    if not name:
        raise ServiceError(f"В почерке нет символа «{ch}». Замените его или выберите свой шрифт.")
    glyph_set = tt.getGlyphSet()
    scale = 10 / float(getattr(tt["OS/2"], "sCapHeight", 0) or tt["head"].unitsPerEm * 0.7)
    lines = [
        [(x * scale, 10 - y * scale) for x, y in line]
        for line in glyph_strokes(tt, glyph_set, name, True, "sans", False)
    ]
    if not lines:
        raise ServiceError(f"В почерке нет штрихов для символа «{ch}».")
    return lines, glyph_set[name].width * scale + 0.8


def render_line(text: str, font: str, size: float) -> list[list[list[float]]]:
    cursor = 0.0
    out: list[list[list[float]]] = []
    for i, ch in enumerate(text):
        strokes, advance = glyph(ch)
        rng = random.Random(zlib.crc32(f"{text}|{i}".encode()))
        slant = 0.24 if font == "notes-slant" else 0.10 if font == "notes-human" else 0.0
        dy = rng.uniform(-0.35, 0.35) if font == "notes-human" else 0.0
        stretch = rng.uniform(0.95, 1.05) if font == "notes-human" else 1.0
        for line in strokes:
            out.append(
                [
                    [(cursor + x * stretch + slant * (10 - y)) * size / 10, (y + dy) * size / 10]
                    for x, y in line
                ]
            )
        cursor += advance * stretch
    return out
