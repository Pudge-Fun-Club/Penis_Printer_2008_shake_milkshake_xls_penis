"""Generate a watertight, adjustable pen clip for mounting with cable ties.

This is a universal attachment prototype, not a measured Ender-3 Neo carriage
replacement. Check clearance on the actual head before mounting and moving.
Run: uv run python scripts/make-pen-holder.py --diameter 9
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

from shapely import constrained_delaunay_triangles
from shapely.geometry import Point, box
from shapely.geometry.polygon import orient


def holder(diameter: float, height: float = 18) -> list:
    if not 6 <= diameter <= 16 or not 10 <= height <= 30:
        raise ValueError("Pen diameter must be 6–16 mm; clip height 10–30 mm.")
    radius = diameter / 2 + 0.3
    center = radius + 1
    ring = Point(center, 0).buffer(radius + 3, quad_segs=48)
    plate = box(-28, -9, 0, 9)
    shape = ring.union(plate).difference(Point(center, 0).buffer(radius, quad_segs=48))
    shape = shape.difference(box(center, -0.7, center + radius + 4, 0.7))
    for y in (-6, 3):
        shape = shape.difference(box(-23, y, -19, y + 3))
    shape = orient(shape, sign=1)
    faces = []
    for triangle in constrained_delaunay_triangles(shape).geoms:
        xy = list(triangle.exterior.coords)[:3]
        a, b, c = xy
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            xy.reverse()
        faces.append([(x, y, height) for x, y in xy])
        faces.append([(x, y, 0) for x, y in reversed(xy)])
    for loop in [shape.exterior, *shape.interiors]:
        coords = list(loop.coords)
        for a, b in zip(coords, coords[1:], strict=False):
            bottom_a, bottom_b = (*a, 0), (*b, 0)
            top_a, top_b = (*a, height), (*b, height)
            faces.extend([[bottom_a, bottom_b, top_b], [bottom_a, top_b, top_a]])
    return faces


def save(faces: list, path: Path) -> None:
    # Shared edges must have exactly two incident faces, including the holes.
    edges = Counter()
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            edges[tuple(sorted((a, b)))] += 1
    if not all(count == 2 for count in edges.values()):
        raise ValueError("Holder mesh is not closed.")
    lines = ["solid cable_tie_pen_holder"]
    for a, b, c in faces:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        length = math.sqrt(sum(x * x for x in n))
        if length == 0:
            raise ValueError("Degenerate holder triangle.")
        lines.append("  facet normal " + " ".join(f"{x / length:.8f}" for x in n))
        lines.append("    outer loop")
        lines.extend("      vertex " + " ".join(f"{x:.8f}" for x in p) for p in (a, b, c))
        lines.extend(["    endloop", "  endfacet"])
    lines.append("endsolid cable_tie_pen_holder")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diameter", type=float, default=9)
    parser.add_argument("--height", type=float, default=18)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(f"media/models/pen-holder-{args.diameter:g}mm.stl")
    faces = holder(args.diameter, args.height)
    save(faces, output)
    print(f"{output}: {len(faces)} triangles, closed mesh, pen Ø{args.diameter:g} mm")
