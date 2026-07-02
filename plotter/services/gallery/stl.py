"""Storage of client-rendered STL colour layers as gallery pages."""

from __future__ import annotations

from pathlib import Path

from plotter.artwork.drawing import load_svg_drawing
from plotter.artwork.pipeline import PlotterError
from plotter.services.upload_validation import sniff_kind


def write_stl_layers(dst_dir: Path, layers: list[dict]) -> list[dict]:
    """Write each colour layer as page-NNNN.svg; return page metadata."""
    pages: list[dict] = []
    order = 0
    for layer in sorted(layers, key=lambda d: d.get("order", 0)):
        svg_text = layer.get("svg") or ""
        svg_bytes = svg_text.encode("utf-8")
        sniff_kind("layer.svg", svg_bytes)  # defence-in-depth content check
        order += 1
        file = f"page-{order:04d}.svg"
        (dst_dir / file).write_bytes(svg_bytes)
        drawing = load_svg_drawing(dst_dir / file, quantization_mm=0.25)
        if drawing.is_empty():
            continue
        pages.append({
            "n": order,
            "file": file,
            "width": round(drawing.width, 3),
            "height": round(drawing.height, 3),
            "lines": len(drawing.polylines),
            "color": layer.get("color", "black"),
            "role": layer.get("role", "visible"),
            "order": order,
        })
    if not pages:
        raise PlotterError("Das STL-Rendering enthält keine plottbaren Linien.")
    return pages
