"""Downsampled polyline previews and their on-disk caches."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from plotter.artwork.drawing import load_svg_drawing
from plotter.services.errors import ServiceError
from plotter.services.gallery.common import (
    FULL_PREVIEW_POINTS,
    SVG_FILE,
    SVG_PREVIEW_FILE,
    SVG_THUMB_FILE,
    THUMB_PREVIEW_POINTS,
)


def preview_from_drawing(drawing, *, max_points: int) -> dict:
    total = sum(len(line) for line in drawing.polylines)
    step = max(total // max_points, 1)
    polylines = []
    for line in drawing.polylines:
        pts = line[::step] if step > 1 else line
        if step > 1 and not np.isclose(pts[-1], line[-1]):
            pts = np.append(pts, line[-1])
        polylines.append([[round(p.real, 2), round(p.imag, 2)] for p in pts])
    return {
        "polylines": polylines,
        "width": round(drawing.width, 3),
        "height": round(drawing.height, 3),
    }


def write_preview_cache(item_dir: Path, drawing) -> None:
    (item_dir / SVG_PREVIEW_FILE).write_text(
        json.dumps(preview_from_drawing(drawing, max_points=FULL_PREVIEW_POINTS))
    )
    (item_dir / SVG_THUMB_FILE).write_text(
        json.dumps(preview_from_drawing(drawing, max_points=THUMB_PREVIEW_POINTS))
    )


def svg_preview(item_dir: Path, item_id: str, *, max_points: int = FULL_PREVIEW_POINTS) -> dict:
    """Polylines of the derived SVG (mm, y down) for safe 2D rendering."""
    cache = item_dir / (
        SVG_THUMB_FILE if max_points <= THUMB_PREVIEW_POINTS else SVG_PREVIEW_FILE
    )
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except (OSError, json.JSONDecodeError):
            cache.unlink(missing_ok=True)

    svg = item_dir / SVG_FILE
    if not svg.exists():
        raise ServiceError(f"Einreichung nicht gefunden: {item_id}")
    drawing = load_svg_drawing(svg, quantization_mm=0.5)
    preview = preview_from_drawing(drawing, max_points=max_points)
    cache.write_text(json.dumps(preview))
    return preview
