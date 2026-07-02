"""Polyline smoothing helpers."""

from __future__ import annotations

import numpy as np


def chaikin(points: np.ndarray, iterations: int) -> np.ndarray:
    """Chaikin corner-cutting: round a polyline by replacing each segment with
    its 1/4 and 3/4 points. Endpoints stay fixed so open strokes keep their
    start/end. Curves stay within the original hull (no overshoot)."""
    pts = points
    for _ in range(iterations):
        if len(pts) < 3:
            break
        a, b = pts[:-1], pts[1:]
        cut = np.empty((2 * len(a), 2), dtype=pts.dtype)
        cut[0::2] = 0.75 * a + 0.25 * b
        cut[1::2] = 0.25 * a + 0.75 * b
        pts = np.vstack((pts[0], cut, pts[-1]))
    return pts
