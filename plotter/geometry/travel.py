"""Pen-up travel minimisation: order strokes (and pick their direction) so the
invisible pen-up moves between them stay short. Reordering never changes the
drawing itself.

Two public entry points preserve the historic behaviours of the two former
copies of this code:

- :func:`sort_for_travel_points` — ``(x, y)`` tuple polylines, greedy only
  (used by the scene renderer).
- :func:`sort_for_travel_complex` — complex-number ndarrays, greedy refined by
  a 2-opt pass (used by SVG drawings).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import TypeVar

import numpy as np

Point = tuple[float, float]
Polyline = list[Point]

L = TypeVar("L")

_LARGE_THRESHOLD = 4000
_TWO_OPT_MAX = 600  # 2-opt is O(passes·n²); cap n to keep it snappy
_TWO_OPT_PASSES = 6


def _greedy(
    polylines: Sequence[L],
    end_xy: Callable[[L, int], Point],
    reverse: Callable[[L], L],
) -> list[L]:
    """O(n²) greedy nearest-neighbour ordering starting at the origin."""
    remaining = list(polylines)
    ordered: list[L] = []
    cx, cy = 0.0, 0.0
    while remaining:
        best_i, best_rev, best_d = 0, False, float("inf")
        for i, line in enumerate(remaining):
            sx, sy = end_xy(line, 0)
            ex, ey = end_xy(line, -1)
            d_start = math.hypot(sx - cx, sy - cy)
            d_end = math.hypot(ex - cx, ey - cy)
            if d_start < best_d:
                best_i, best_rev, best_d = i, False, d_start
            if d_end < best_d:
                best_i, best_rev, best_d = i, True, d_end
        line = remaining.pop(best_i)
        if best_rev:
            line = reverse(line)
        ordered.append(line)
        cx, cy = end_xy(line, -1)
    return ordered


def _greedy_large(
    polylines: Sequence[L],
    end_xy: Callable[[L, int], Point],
    reverse: Callable[[L], L],
) -> list[L]:
    """KD-tree greedy nearest-neighbour ordering for large stroke counts, so
    even big non-continuous pages keep their pen-up travel short."""
    from scipy.spatial import cKDTree

    n = len(polylines)
    pts = np.empty((2 * n, 2))
    for i, line in enumerate(polylines):
        pts[2 * i] = end_xy(line, 0)
        pts[2 * i + 1] = end_xy(line, -1)
    tree = cKDTree(pts)
    used = bytearray(n)
    ordered: list[L] = []
    cursor = np.array([0.0, 0.0])
    for _ in range(n):
        found = -1
        kk = 8
        while found < 0:
            kk = min(2 * n, kk)
            _, idx = tree.query(cursor, k=kk)
            for ix in np.atleast_1d(idx):
                if not used[ix // 2]:
                    found = int(ix)
                    break
            if found < 0:
                if kk >= 2 * n:
                    break
                kk *= 2
        if found < 0:
            break
        pi = found // 2
        used[pi] = 1
        line = polylines[pi]
        if found % 2 == 1:
            line = reverse(line)
        ordered.append(line)
        cursor = np.array(end_xy(line, -1))
    return ordered


def _tuple_end(line: Polyline, i: int) -> Point:
    return (line[i][0], line[i][1])


def _complex_end(line: np.ndarray, i: int) -> Point:
    return (line[i].real, line[i].imag)


def sort_for_travel_points(polylines: list[Polyline]) -> list[Polyline]:
    """Order ``(x, y)`` tuple polylines for short pen-up travel (greedy only)."""
    if len(polylines) > _LARGE_THRESHOLD:
        return _greedy_large(polylines, _tuple_end, lambda ln: list(reversed(ln)))
    return _greedy(polylines, _tuple_end, lambda ln: list(reversed(ln)))


def sort_for_travel_complex(polylines: list[np.ndarray]) -> list[np.ndarray]:
    """Order complex-ndarray polylines for short pen-up travel; small inputs get
    an additional 2-opt refinement pass."""
    if len(polylines) <= 1:
        return list(polylines)
    if len(polylines) > _LARGE_THRESHOLD:
        return _greedy_large(polylines, _complex_end, lambda ln: ln[::-1])
    ordered = _greedy(polylines, _complex_end, lambda ln: ln[::-1])
    return _two_opt_travel(ordered, 0 + 0j)


def _two_opt_travel(ordered: list[np.ndarray], start: complex) -> list[np.ndarray]:
    """2-opt refinement of the stroke order: reverse a sub-sequence (flipping
    each stroke) whenever that shortens the total pen-up travel."""
    n = len(ordered)
    if n < 3 or n > _TWO_OPT_MAX:
        return ordered
    starts = [o[0] for o in ordered]
    ends = [o[-1] for o in ordered]
    for _ in range(_TWO_OPT_PASSES):
        improved = False
        for i in range(n):
            prev_end = start if i == 0 else ends[i - 1]
            for j in range(i + 1, n):
                tail = starts[j + 1] if j + 1 < n else None
                tail_before = abs(ends[j] - tail) if tail is not None else 0.0
                tail_after = abs(starts[i] - tail) if tail is not None else 0.0
                before = abs(prev_end - starts[i]) + tail_before
                after = abs(prev_end - ends[j]) + tail_after
                if after + 1e-9 < before:
                    ordered[i:j + 1] = [o[::-1] for o in reversed(ordered[i:j + 1])]
                    starts[i:j + 1] = [o[0] for o in ordered[i:j + 1]]
                    ends[i:j + 1] = [o[-1] for o in ordered[i:j + 1]]
                    improved = True
        if not improved:
            break
    return ordered
