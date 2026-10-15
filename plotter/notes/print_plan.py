"""Use one reviewed route for preview metrics and compact printer commands."""

from __future__ import annotations

from plotter.core.calibration import Calibration
from plotter.gcode.metrics import analyze_gcode
from plotter.gcode.scene import scene_gcode


def ordered_page(lines: list, *, id: str = "preview", name: str = "SVG") -> dict:
    return {
        "id": id,
        "name": name,
        "continuous": False,
        "objects": [
            {
                "cachedPolylines": lines,
                "cachedFeeds": [[1.0] * len(line) for line in lines],
            }
        ],
    }


def compact_gcode(text: str) -> str:
    # Feed is modal in absolute Marlin G-code. Keep every coordinate/motion and
    # feed change, but avoid sending the same F word for every curve vertex.
    feed = None
    result = []
    for raw in text.splitlines():
        words = raw.split()
        if words and words[0] in ("G0", "G1"):
            kept = []
            for word in words:
                if word.startswith("F"):
                    current = float(word[1:])
                    if current == feed:
                        continue
                    feed = current
                kept.append(word)
            raw = " ".join(kept)
        result.append(raw)
    return "\n".join(result) + "\n"


def plot_stats(lines: list, cal: Calibration) -> dict:
    metrics = analyze_gcode(compact_gcode(scene_gcode(ordered_page(lines), cal)))
    return {
        "estimatedSeconds": metrics.duration_s,
        "penLifts": metrics.pen_lifts,
        "drawMm": metrics.draw_mm,
        "travelMm": metrics.travel_mm,
        "penLiftMm": round(abs(cal.pen_up_z - cal.pen_down_z), 3),
    }
