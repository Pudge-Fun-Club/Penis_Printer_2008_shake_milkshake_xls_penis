"""Bézier flattening and stroke assembly from fontTools glyph recordings."""

from __future__ import annotations

Point = tuple[float, float]
Polyline = list[Point]

# Strokes shorter than this (in em units) are dropped — single-line fonts carry
# tiny degenerate nubs (e.g. a 2-unit cap on "I") that would waste pen dabs.
MIN_STROKE_UNITS = 6.0

def quad(a: Point, b: Point, c: Point, steps: int = 8) -> Polyline:
    pts: Polyline = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        pts.append((
            mt * mt * a[0] + 2 * mt * t * b[0] + t * t * c[0],
            mt * mt * a[1] + 2 * mt * t * b[1] + t * t * c[1],
        ))
    return pts


def cubic(a: Point, b: Point, c: Point, d: Point, steps: int = 12) -> Polyline:
    pts: Polyline = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        pts.append((
            mt ** 3 * a[0] + 3 * mt * mt * t * b[0] + 3 * mt * t * t * c[0] + t ** 3 * d[0],
            mt ** 3 * a[1] + 3 * mt * mt * t * b[1] + 3 * mt * t * t * c[1] + t ** 3 * d[1],
        ))
    return pts


def stroke_length(line: Polyline) -> float:
    return sum(
        ((line[i][0] - line[i - 1][0]) ** 2 + (line[i][1] - line[i - 1][1]) ** 2) ** 0.5
        for i in range(1, len(line))
    )


def recording_to_strokes(recording: list[tuple[str, tuple]]) -> list[Polyline]:
    """Convert a glyph recording to open polylines. closePath is treated as a
    plain end-of-stroke — we never add the closing segment, since these fonts
    are single-line and closing would double the path."""
    strokes: list[Polyline] = []
    current: Point = (0.0, 0.0)
    line: Polyline = []

    def finish() -> None:
        nonlocal line
        if len(line) > 1 and stroke_length(line) >= MIN_STROKE_UNITS:
            strokes.append(line)
        line = []

    for op, args in recording:
        if op == "moveTo":
            finish()
            current = tuple(args[0])
            line = [current]
        elif op == "lineTo":
            current = tuple(args[0])
            line.append(current)
        elif op == "qCurveTo":
            points = [tuple(p) for p in args]
            for i in range(len(points) - 1):
                line.extend(quad(current, points[i], points[i + 1]))
                current = points[i + 1]
        elif op == "curveTo":
            p1, p2, p3 = (tuple(p) for p in args)
            line.extend(cubic(current, p1, p2, p3))
            current = p3
        elif op in ("closePath", "endPath"):
            finish()
    finish()
    return strokes


def recording_to_contours(recording: list[tuple[str, tuple]]) -> list[Polyline]:
    """Flatten a glyph recording into closed contours for raster skeletonizing."""
    contours: list[Polyline] = []
    current: Point = (0.0, 0.0)
    start: Point | None = None
    line: Polyline = []

    def finish(close: bool) -> None:
        nonlocal line, start
        if close and start is not None and line and line[-1] != start:
            line.append(start)
        if len(line) >= 3:
            contours.append(line)
        line = []
        start = None

    for op, args in recording:
        if op == "moveTo":
            finish(close=False)
            current = tuple(args[0])
            start = current
            line = [current]
        elif op == "lineTo":
            current = tuple(args[0])
            line.append(current)
        elif op == "qCurveTo":
            points = [tuple(p) for p in args]
            for i in range(len(points) - 1):
                line.extend(quad(current, points[i], points[i + 1]))
                current = points[i + 1]
        elif op == "curveTo":
            p1, p2, p3 = (tuple(p) for p in args)
            line.extend(cubic(current, p1, p2, p3))
            current = p3
        elif op == "closePath":
            finish(close=True)
        elif op == "endPath":
            finish(close=False)
    finish(close=False)
    return contours


def _close(a: Point, b: Point, tol: float) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def merge_strokes(strokes: list[Polyline], tol: float) -> list[Polyline]:
    """Greedily chain strokes whose endpoints coincide (linemerge). The SVG glyph
    paths split a single pen stroke into several subpaths at shared points; this
    stitches them back into continuous strokes."""
    pool = [list(s) for s in strokes if len(s) >= 2]
    out: list[Polyline] = []
    while pool:
        cur = pool.pop(0)
        extended = True
        while extended:
            extended = False
            for i, s in enumerate(pool):
                if _close(cur[-1], s[0], tol):
                    cur += s[1:]
                elif _close(cur[-1], s[-1], tol):
                    cur += list(reversed(s))[1:]
                elif _close(cur[0], s[-1], tol):
                    cur = s + cur[1:]
                elif _close(cur[0], s[0], tol):
                    cur = list(reversed(s)) + cur[1:]
                else:
                    continue
                pool.pop(i)
                extended = True
                break
        out.append(cur)
    return out
