"""Centerline extraction: rasterise a glyph outline, skeletonize it and trace
the skeleton back into smooth open strokes (for fonts without true single-line
geometry)."""

from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np
from fontTools.pens.recordingPen import DecomposingRecordingPen
from skimage.draw import polygon
from skimage.morphology import skeletonize

from plotter.geometry.smoothing import chaikin
from plotter.text.flatten import (
    MIN_STROKE_UNITS,
    Polyline,
    recording_to_contours,
    stroke_length,
)
from plotter.text.fonts import load_font

_SKELETON_EM_PX = 224
_SKELETON_MIN_PIXELS = 2
_CENTERLINE_SIMPLIFY_PX = 0.75
_CENTERLINE_SMOOTH_ITERS = 1
def skeleton_to_strokes(
    mask: np.ndarray, min_pixels: int = _SKELETON_MIN_PIXELS
) -> list[list[tuple[int, int]]]:
    padded = np.pad(mask.astype(np.uint8), 1)
    rows, cols = np.where(padded > 0)
    if len(rows) == 0:
        return []
    neighbours8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    degree = {
        (int(row), int(col)): int(
            padded[row - 1, col - 1] + padded[row - 1, col] + padded[row - 1, col + 1]
            + padded[row, col - 1] + padded[row, col + 1]
            + padded[row + 1, col - 1] + padded[row + 1, col] + padded[row + 1, col + 1]
        )
        for row, col in zip(rows, cols, strict=True)
    }
    pixels = set(degree)

    def neighbours(p: tuple[int, int]) -> list[tuple[int, int]]:
        r, c = p
        return [(r + dr, c + dc) for dr, dc in neighbours8 if (r + dr, c + dc) in pixels]

    visited_edges: set[frozenset[tuple[int, int]]] = set()
    strokes: list[list[tuple[int, int]]] = []

    def edge(a: tuple[int, int], b: tuple[int, int]) -> frozenset[tuple[int, int]]:
        return frozenset((a, b))

    def walk(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
        line = [a, b]
        visited_edges.add(edge(a, b))
        prev, cur = a, b
        while degree.get(cur, 0) == 2:
            options = [q for q in neighbours(cur) if q != prev]
            if not options:
                break
            nxt = options[0]
            e = edge(cur, nxt)
            if e in visited_edges:
                break
            visited_edges.add(e)
            line.append(nxt)
            prev, cur = cur, nxt
        return line

    for start in (p for p in pixels if degree[p] != 2):
        for nxt in neighbours(start):
            if edge(start, nxt) not in visited_edges:
                strokes.append(walk(start, nxt))

    for p in pixels:
        for nxt in neighbours(p):
            if edge(p, nxt) not in visited_edges:
                strokes.append(walk(p, nxt))

    # Coordinates were padded by one pixel; shift back to mask space.
    return [
        [(row - 1, col - 1) for row, col in line]
        for line in strokes
        if len(line) >= min_pixels
    ]


def smooth_skeleton_line(line: list[tuple[int, int]]) -> np.ndarray:
    arr = np.asarray([(col, row) for row, col in line], dtype=np.float32)
    if len(arr) < 3:
        return arr.astype(np.float64)
    approx = cv2.approxPolyDP(arr.reshape(-1, 1, 2), _CENTERLINE_SIMPLIFY_PX, False).reshape(-1, 2)
    if len(approx) < 2:
        approx = arr
    return chaikin(approx.astype(np.float64), _CENTERLINE_SMOOTH_ITERS)


@lru_cache(maxsize=2048)
def glyph_centerline(font: str, glyph_name: str) -> list[Polyline]:
    tt = load_font(font)
    glyph_set = tt.getGlyphSet()
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    contours = recording_to_contours(pen.value)
    if not contours:
        return []

    xs = [x for contour in contours for x, _ in contour]
    ys = [y for contour in contours for _, y in contour]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    units = float(tt["head"].unitsPerEm)
    px_per_unit = _SKELETON_EM_PX / units
    pad = 3
    width = max(4, int(math.ceil((max_x - min_x) * px_per_unit)) + pad * 2 + 1)
    height = max(4, int(math.ceil((max_y - min_y) * px_per_unit)) + pad * 2 + 1)
    mask = np.zeros((height, width), dtype=bool)

    for contour in contours:
        cols = np.array([(x - min_x) * px_per_unit + pad for x, _ in contour])
        rows = np.array([(max_y - y) * px_per_unit + pad for _, y in contour])
        rr, cc = polygon(rows, cols, shape=mask.shape)
        # Toggle contours so counters/holes in glyphs stay hollow.
        mask[rr, cc] = ~mask[rr, cc]

    skeleton = skeletonize(mask)
    strokes: list[Polyline] = []
    for line in skeleton_to_strokes(skeleton):
        pts: Polyline = []
        smoothed = smooth_skeleton_line(line)
        for col, row in smoothed:
            x = (col - pad) / px_per_unit + min_x
            y = max_y - (row - pad) / px_per_unit
            pts.append((x, y))
        # Keep short glyph branches (e.g. K/k diagonals) but drop pixel specks.
        if stroke_length(pts) >= max(MIN_STROKE_UNITS * 0.25, units * 0.006):
            strokes.append(pts)
    return strokes
