"""Drawing-element parsing and SVG rendering for MCP tools.

The drawing-element dialect (polyline, rect, circle, star, spiral, …) is MCP's
own input format; it is parsed here rather than delegated to the artwork layer.
"""

from __future__ import annotations

import math
from typing import Any
from xml.sax.saxutils import escape

from plotter.mcp.args import num, segments


def coerce_polylines(raw: Any) -> list[list[list[float]]]:
    if not isinstance(raw, list):
        raise ValueError("polylines must be an array")
    out: list[list[list[float]]] = []
    total = 0
    for line in raw:
        if not isinstance(line, list):
            raise ValueError("each polyline must be an array")
        pts: list[list[float]] = []
        for point in line:
            if not isinstance(point, list | tuple) or len(point) < 2:
                raise ValueError("each point must be [x, y]")
            x = float(point[0])
            y = float(point[1])
            if not (x == x and y == y and abs(x) != float("inf") and abs(y) != float("inf")):
                raise ValueError("points must be finite")
            pts.append([round(x, 3), round(y, 3)])
        if len(pts) >= 2:
            out.append(pts)
            total += len(pts)
    if not out:
        raise ValueError("at least one polyline with two points is required")
    if total > 50000:
        raise ValueError("too many points; maximum is 50000")
    return out


def ellipse_points(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    start: float = 0.0,
    end: float = 360.0,
    segments: int = 96,
    close: bool = False,
) -> list[list[float]]:
    if rx <= 0 or ry <= 0:
        raise ValueError("radius values must be greater than 0")
    a0 = math.radians(start)
    a1 = math.radians(end)
    pts = []
    for i in range(segments + 1):
        angle = a0 + (a1 - a0) * i / segments
        pts.append(
            [
                round(cx + math.cos(angle) * rx, 3),
                round(cy + math.sin(angle) * ry, 3),
            ]
        )
    if close and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def drawing_element_polylines(element: dict[str, Any]) -> list[list[list[float]]]:
    kind = str(element.get("type") or "").lower()
    if kind == "polyline":
        return coerce_polylines([element.get("points")])
    if kind == "line":
        return [
            [
                [num(element, "x1"), num(element, "y1")],
                [num(element, "x2"), num(element, "y2")],
            ]
        ]
    if kind == "rect":
        x, y, w, h = (
            num(element, "x"),
            num(element, "y"),
            num(element, "w"),
            num(element, "h"),
        )
        return [[[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]]
    if kind == "circle":
        pts = ellipse_points(
            num(element, "cx"),
            num(element, "cy"),
            num(element, "r"),
            num(element, "r"),
            segments=segments(element),
            close=True,
        )
        return [pts]
    if kind == "ellipse":
        pts = ellipse_points(
            num(element, "cx"),
            num(element, "cy"),
            num(element, "rx"),
            num(element, "ry"),
            segments=segments(element),
            close=True,
        )
        return [pts]
    if kind == "arc":
        radius = num(element, "r", 0)
        pts = ellipse_points(
            num(element, "cx"),
            num(element, "cy"),
            num(element, "rx", radius),
            num(element, "ry", radius),
            start=num(element, "start", 0),
            end=num(element, "end", 180),
            segments=segments(element),
            close=False,
        )
        return [pts]
    if kind in ("polygon", "star"):
        cx, cy = num(element, "cx"), num(element, "cy")
        n = max(3, min(int(num(element, "points" if kind == "star" else "sides", 5)), 200))
        rot = math.radians(num(element, "rotation", -90))
        outer = num(element, "r")
        pts = []
        count = n * 2 if kind == "star" else n
        inner = num(element, "inner_r", outer * 0.5)
        for i in range(count):
            radius = outer if kind == "polygon" or i % 2 == 0 else inner
            a = rot + 2 * math.pi * i / count
            pts.append([round(cx + math.cos(a) * radius, 3), round(cy + math.sin(a) * radius, 3)])
        pts.append(pts[0])
        return [pts]
    if kind == "spiral":
        cx, cy = num(element, "cx"), num(element, "cy")
        turns = max(0.25, num(element, "turns", 3))
        steps = max(8, min(int(num(element, "segments", turns * 80)), 2000))
        r0, r1 = num(element, "r0", 0), num(element, "r", 50)
        pts = []
        for i in range(steps + 1):
            t = i / steps
            a = 2 * math.pi * turns * t + math.radians(num(element, "rotation", 0))
            r = r0 + (r1 - r0) * t
            pts.append([round(cx + math.cos(a) * r, 3), round(cy + math.sin(a) * r, 3)])
        return [pts]
    if kind == "wave":
        x, y, length = num(element, "x"), num(element, "y"), num(element, "length")
        amp, cycles = num(element, "amplitude"), num(element, "cycles", 3)
        steps = max(8, min(int(num(element, "segments", cycles * 48)), 2000))
        pts = []
        for i in range(steps + 1):
            pts.append(
                [
                    round(x + length * i / steps, 3),
                    round(y + math.sin(2 * math.pi * cycles * i / steps) * amp, 3),
                ]
            )
        return [pts]
    if kind in ("grid", "hatch"):
        x, y, w, h = num(element, "x"), num(element, "y"), num(element, "w"), num(element, "h")
        spacing = max(num(element, "spacing", 10), 0.1)
        lines = []
        if kind == "grid" or str(element.get("direction", "horizontal")) != "vertical":
            yy = y
            while yy <= y + h + 1e-6:
                lines.append([[x, round(yy, 3)], [x + w, round(yy, 3)]])
                yy += spacing
        if kind == "grid" or str(element.get("direction")) == "vertical":
            xx = x
            while xx <= x + w + 1e-6:
                lines.append([[round(xx, 3), y], [round(xx, 3), y + h]])
                xx += spacing
        return lines
    raise ValueError(f"unknown drawing element type: {kind}")


def drawing_polylines(raw: Any) -> list[list[list[float]]]:
    if not isinstance(raw, list):
        raise ValueError("elements must be an array")
    lines: list[list[list[float]]] = []
    for element in raw:
        if not isinstance(element, dict):
            raise ValueError("each drawing element must be an object")
        lines.extend(drawing_element_polylines(element))
    return coerce_polylines(lines)


def bounds(polylines: list[list[list[float]]]) -> list[float]:
    xs = [pt[0] for line in polylines for pt in line]
    ys = [pt[1] for line in polylines for pt in line]
    return [min(xs), min(ys), max(xs), max(ys)]


def svg_path(polylines: list[list[list[float]]]) -> str:
    parts: list[str] = []
    for line in polylines:
        if len(line) < 2:
            continue
        coords = []
        for point in line:
            if len(point) < 2:
                continue
            coords.append(f"{float(point[0]):.3f},{float(point[1]):.3f}")
        if len(coords) >= 2:
            parts.append("M" + " L".join(coords))
    return " ".join(parts)


def polylines_svg(
    polylines: list[list[list[float]]],
    *,
    width: float,
    height: float,
    title: str,
    travels: list[list[list[float]]] | None = None,
) -> str:
    width = max(float(width), 1.0)
    height = max(float(height), 1.0)
    draw_d = svg_path(polylines)
    travel_d = svg_path(travels or [])
    travel = (
        f'<path d="{escape(travel_d)}" fill="none" stroke="#9aa0a6" '
        'stroke-width="0.2" stroke-dasharray="2 2" vector-effect="non-scaling-stroke" />'
        if travel_d
        else ""
    )
    draw = (
        f'<path d="{escape(draw_d)}" fill="none" stroke="#111" stroke-width="0.35" '
        'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />'
        if draw_d
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.3f}mm" '
        f'height="{height:.3f}mm" viewBox="0 0 {width:.3f} {height:.3f}">'
        f"<title>{escape(title)}</title>"
        '<rect x="0" y="0" width="100%" height="100%" fill="white" />'
        f"{travel}{draw}</svg>"
    )
