"""Render text to single-line polylines (the public entry point)."""

from __future__ import annotations

import random
import re
import zlib

from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont

from plotter.artwork.pipeline import PlotterError
from plotter.text.flatten import (
    Point,
    Polyline,
    merge_strokes,
    recording_to_strokes,
    stroke_length,
)
from plotter.text.fonts import (
    FONT_CONNECT,
    FONT_HUMANIZE,
    FONT_SVG,
    FONT_WARP,
    FONT_WORD_JITTER,
    load_font,
    use_centerline,
)
from plotter.text.humanize import USER_PLOTTER_HUMANIZE, humanize_glyph, jitter_word, warp
from plotter.text.skeleton import glyph_centerline

_PATH_D_RE = re.compile(r'<path[^>]*\bd="([^"]+)"')


def svg_glyph_map(tt: TTFont) -> dict[int, str]:
    """gid -> SVG document, built once per font."""
    cached = getattr(tt, "_singleline_svg_map", None)
    if cached is None:
        cached = {}
        if "SVG " in tt:
            for doc in tt["SVG "].docList:
                for gid in range(doc.startGlyphID, doc.endGlyphID + 1):
                    cached[gid] = doc.data
        tt._singleline_svg_map = cached  # type: ignore[attr-defined]
    return cached


def glyph_strokes(
    tt: TTFont, glyph_set, glyph_name: str, svg_src: bool, font: str, centerline: bool
) -> list[Polyline]:
    """Open strokes for a glyph in font units (y-up). For SVG fonts we parse the
    single-line <path> from the SVG table and merge its subpaths; otherwise we
    read the (decomposed) CFF/glyf outline."""
    if svg_src:
        gid = tt.getGlyphID(glyph_name)
        data = svg_glyph_map(tt).get(gid)
        if data:
            raw: list[Polyline] = []
            for d in _PATH_D_RE.findall(data):
                pen = RecordingPen()
                parse_path(d, pen)
                raw += recording_to_strokes(pen.value)
            return merge_strokes(raw, tol=4.0)
        # Rare glyphs (e.g. », Ω, arrows) have no SVG art: fall back to the
        # outline so they still appear, rather than rendering nothing.
    if centerline:
        return glyph_centerline(font, glyph_name)
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return recording_to_strokes(pen.value)


def text_polylines(
    text: str, *, font: str = "sans", size: float = 12.0, connect_spaces: bool = False
) -> list[list[list[float]]]:
    """Render text to single-line polylines in mm, y-down (editor space).

    ``connect_spaces`` (cursive fonts only) adds a baseline sweep across each
    space so a whole line reads as one continuous flourish.
    """
    if size <= 0:
        raise PlotterError("Schriftgröße muss größer als 0 sein.")
    if not text:
        return []

    tt = load_font(font)
    cmap = tt.getBestCmap() or {}
    glyph_set = tt.getGlyphSet()
    units = float(tt["head"].unitsPerEm)
    scale = size / units
    hhea = tt["hhea"]
    ascent = float(hhea.ascent)
    descent = float(hhea.descent)
    line_height = (ascent - descent) * scale * 1.25
    baseline = ascent * scale
    cursor = 0.0
    connect = font in FONT_CONNECT
    svg_src = font in FONT_SVG
    centerline = use_centerline(font)
    human = FONT_HUMANIZE.get(font) or (USER_PLOTTER_HUMANIZE if centerline else None)
    jitter = FONT_WORD_JITTER.get(font)
    sweep_spaces = connect_spaces and connect
    prev_word_end: Point | None = None  # (x, baseline) right edge of the last word

    # Cursive fonts build one stroke per word: each letter's main stroke joins
    # `word_bodies`; its dots/accents/crossbars go to `word_marks`. On a word
    # break the bodies are linemerged (and optionally jittered as a unit) into
    # the page mains; marks are emitted after all mains so they don't break flow.
    mains: list[Polyline] = []
    marks: list[Polyline] = []
    word_bodies: list[Polyline] = []
    word_marks: list[Polyline] = []
    word_no = 0

    def flush_word() -> None:
        nonlocal word_bodies, word_marks, word_no
        if word_bodies or word_marks:
            merged = merge_strokes(word_bodies, tol=0.3)
            group_marks = word_marks
            if jitter:
                rng = random.Random(zlib.crc32(f"{font}|{word_no}".encode()))
                combined = jitter_word(merged + group_marks, jitter, size, rng)
                merged, group_marks = combined[: len(merged)], combined[len(merged):]
            mains.extend(merged)
            marks.extend(group_marks)
        word_bodies, word_marks = [], []
        word_no += 1

    for gi, ch in enumerate(text):
        if ch == "\n":
            cursor = 0.0
            baseline += line_height
            flush_word()
            prev_word_end = None  # never sweep across a line break
            continue
        glyph_name = cmap.get(ord(ch))
        if glyph_name is None or ch == " ":
            if sweep_spaces and (word_bodies or word_marks):
                prev_word_end = (cursor, baseline)  # right edge of the word
            cursor += glyph_set[glyph_name].width * scale if glyph_name else size * 0.4
            flush_word()
            continue

        # First glyph of a word: bridge from the previous word along the baseline.
        if sweep_spaces and not word_bodies and not word_marks and prev_word_end is not None:
            if prev_word_end[1] == baseline and cursor > prev_word_end[0]:
                mains.append([prev_word_end, (cursor, baseline)])
            prev_word_end = None

        strokes = [
            [(cursor + x * scale, baseline - y * scale) for x, y in raw]
            for raw in glyph_strokes(tt, glyph_set, glyph_name, svg_src, font, centerline)
        ]
        if human:
            # Seed per (font, position, char): stable across re-renders, while
            # repeated letters still vary by where they sit.
            rng = random.Random(zlib.crc32(f"{font}|{gi}|{ch}".encode()))
            strokes, advance = humanize_glyph(strokes, human, size, rng)
            cursor += advance

        if connect and strokes:
            body = max(strokes, key=stroke_length)  # the letter's main stroke
            word_bodies.append(body)
            word_marks.extend(s for s in strokes if s is not body)
        else:
            mains.extend(strokes)
        cursor += glyph_set[glyph_name].width * scale

    flush_word()
    out = mains + marks
    if font in FONT_WARP:
        out = warp(out, size, zlib.crc32(text.encode()), FONT_WARP[font])
    return [[[round(x, 3), round(y, 3)] for x, y in line] for line in out]
