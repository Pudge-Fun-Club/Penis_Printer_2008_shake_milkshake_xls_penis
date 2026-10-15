"""Plan short pen routes while preserving separate ink components."""

from __future__ import annotations

import math

import cv2
import numpy as np

from plotter.core.calibration import Calibration
from plotter.geometry.travel import sort_for_travel_complex
from plotter.notes.stroke_graph import stroke_components

# Only exactly shared vertices connect. Never bridge nearby letters or dots.
_SIMPLIFY_MM = 0.02


def _length(lines: list) -> float:
    return sum(math.dist(a, b) for line in lines for a, b in zip(line, line[1:], strict=False))


def _travel(lines: list) -> float:
    return sum(math.dist(a[-1], b[0]) for a, b in zip(lines, lines[1:], strict=False))


def _sort(lines: list) -> list:
    arrays = [np.asarray([complex(x, y) for x, y in line]) for line in lines]
    return [
        [[float(p.real), float(p.imag)] for p in line] for line in sort_for_travel_complex(arrays)
    ]


def _simplify(line: list) -> list:
    if len(line) <= 2:
        return line
    closed = line[0] == line[-1]
    points = (
        cv2.approxPolyDP(np.asarray(line, dtype=np.float32), _SIMPLIFY_MM, closed)
        .reshape(-1, 2)
        .tolist()
    )
    # A small closed mark must not become an empty or open stroke.
    if len(points) < (3 if closed else 2):
        return line
    if closed:
        points.append(points[0])
    return [[round(x, 3), round(y, 3)] for x, y in points]


def _reloop(lines: list) -> list:
    result = [list(line) for line in lines]
    cursor = (0.0, 0.0)
    for i, line in enumerate(result):
        following = result[i + 1][0] if i + 1 < len(result) else None
        if len(line) > 3 and line[0] == line[-1]:
            distances = [
                math.dist(cursor, p) + (math.dist(p, following) if following else 0)
                for p in line[:-1]
            ]
            seam = min(range(len(distances)), key=distances.__getitem__)
            ring = line[:-1]
            line = ring[seam:] + ring[:seam] + [ring[seam]]
            result[i] = line
        cursor = line[-1]
    return result


def optimize_strokes(lines: list, cal: Calibration) -> tuple[list, dict]:
    original = [[[float(x), float(y)] for x, y in line] for line in lines if len(line) >= 2]
    if not original:
        return [], {}

    def cost(route: list, *, include_start: bool = True) -> float:
        first_travel = math.dist((0, 0), route[0][0]) if include_start else 0
        return (
            _length(route) / min(cal.draw_feed, cal.travel_feed)
            + (_travel(route) + first_travel) / cal.travel_feed
            + len(route) * 2 * abs(cal.pen_up_z - cal.pen_down_z) / cal.z_feed
        )

    mixed = []
    for separate, connected in stroke_components(original):
        options = [separate, _sort(separate), connected]
        mixed.extend(min(options, key=lambda route: cost(route, include_start=False)))
    candidates = [original, _sort(original), _sort(mixed)]
    chosen = min(candidates, key=cost)
    simplified = [_simplify(line) for line in chosen]
    reseamed = _reloop(simplified)
    optimized = min([simplified, reseamed, _reloop(_sort(reseamed))], key=cost)
    return optimized, {
        "beforeStrokes": len(original),
        "afterStrokes": len(optimized),
        "beforeTravelMm": round(_travel(original), 1),
        "afterTravelMm": round(_travel(optimized), 1),
        "beforePoints": sum(len(line) for line in original),
        "afterPoints": sum(len(line) for line in optimized),
    }
