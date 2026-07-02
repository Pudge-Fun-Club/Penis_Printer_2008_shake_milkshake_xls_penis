"""Read-only MCP tools: overview/tutorial texts, profiles, fonts and jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plotter.mcp.args import require_arg
from plotter.mcp.shapes import polylines_svg


def tool_get_mcp_overview(_: dict[str, Any]) -> dict:
    return {
        "name": "GCodeScribe",
        "summary": (
            "GCodeScribe is a browser-based pen-plotter studio. It converts, generates, "
            "places, previews and plots line artwork through calibrated printer profiles."
        ),
        "what_you_can_do": [
            "Inspect the active plotter profile, plot area, printer status and position.",
            "List, inspect and preview designer pages as SVG or plottable polylines.",
            "Create new pages from polylines, drawing primitives, text or gallery items.",
            "Add safe MCP-generated content to existing pages and immediately plot them.",
            "Preview existing generated jobs and list available fonts or gallery assets.",
            "Home the plotter, move within configured limits, lift/lower the pen, and pause, "
            "resume or cancel jobs.",
            "Clean up pages that were created by MCP tools, while leaving manual pages protected.",
        ],
        "important_limits": [
            "MCP does not expose raw G-code or raw serial commands.",
            "All drawing coordinates are millimeters relative to the active plot area.",
            "Anything outside the active profile plot area is rejected before saving or plotting.",
            "Existing pages must match the active profile id and fingerprint before plotting.",
            "Only MCP-created pages can be deleted through MCP.",
            "Every create/add drawing operation immediately plots after validation succeeds.",
        ],
        "recommended_start": [
            "Call get_active_profile to learn the available plot width and height.",
            "Call get_mcp_tutorial for the detailed safe workflow and drawing element examples.",
            "Use get_page_svg, get_gallery_svg or get_job_preview when you need visual context.",
            "Use create_page_and_plot_drawing for new free-form drawings or patterns.",
            "Use add_drawing_to_page_and_plot only after inspecting the target page.",
        ],
    }


def tool_get_mcp_tutorial(_: dict[str, Any]) -> dict:
    return {
        "purpose": (
            "Use MCP to inspect GCodeScribe state, create or update designer pages, and "
            "immediately plot through the configured printer backend. The MCP surface is "
            "intentionally safe: it does not expose raw G-code or raw serial commands."
        ),
        "workflow": [
            "Call get_active_profile first and design only within plot_width x plot_height.",
            "Use preview/read tools such as list_pages, get_page, get_page_svg, list_gallery, "
            "get_gallery_svg and get_job_preview when you need context.",
            "For free drawing, prefer create_page_and_plot_drawing or "
            "add_drawing_to_page_and_plot.",
            "For exact existing paths, use create_page_and_plot_polylines or "
            "add_polylines_to_page_and_plot.",
            "For text or gallery insertion, use the dedicated text/gallery tools.",
            "Every create/add tool validates bounds and immediately plots if validation succeeds.",
        ],
        "safety_rules": [
            "Coordinates are millimeters relative to the active plot area origin.",
            "Anything outside the active profile plot area fails with "
            "outside_active_profile_plot_area.",
            "Out-of-bounds failures do not save page changes and do not plot.",
            "Existing pages must match the active profile id and fingerprint before plotting.",
            "MCP can delete only pages created by MCP; manual pages are protected.",
            "printer_job_command supports only pause, resume and cancel.",
        ],
        "drawing_elements": {
            "polyline": {"type": "polyline", "points": [[10, 10], [30, 10], [30, 30]]},
            "line": {"type": "line", "x1": 10, "y1": 10, "x2": 50, "y2": 10},
            "rect": {"type": "rect", "x": 10, "y": 10, "w": 40, "h": 20},
            "circle": {"type": "circle", "cx": 50, "cy": 50, "r": 20},
            "ellipse": {"type": "ellipse", "cx": 50, "cy": 50, "rx": 30, "ry": 15},
            "arc": {"type": "arc", "cx": 50, "cy": 50, "r": 25, "start": 0, "end": 180},
            "polygon": {"type": "polygon", "cx": 50, "cy": 50, "sides": 6, "r": 25},
            "star": {"type": "star", "cx": 50, "cy": 50, "points": 5, "r": 25, "inner_r": 12},
            "spiral": {"type": "spiral", "cx": 50, "cy": 50, "turns": 4, "r": 35},
            "wave": {"type": "wave", "x": 10, "y": 40, "length": 120, "amplitude": 10},
            "grid": {"type": "grid", "x": 10, "y": 10, "w": 80, "h": 50, "spacing": 10},
            "hatch": {"type": "hatch", "x": 10, "y": 10, "w": 80, "h": 50, "spacing": 5},
        },
        "examples": {
            "create_page_and_plot_drawing": {
                "name": "MCP pattern",
                "elements": [
                    {"type": "rect", "x": 10, "y": 10, "w": 80, "h": 50},
                    {"type": "circle", "cx": 50, "cy": 35, "r": 20},
                    {"type": "hatch", "x": 10, "y": 10, "w": 80, "h": 50, "spacing": 5},
                ],
            },
            "add_drawing_to_page_and_plot": {
                "page_id": "existing-page-id",
                "elements": [{"type": "wave", "x": 10, "y": 80, "length": 120, "amplitude": 8}],
            },
        },
    }


def tool_get_active_profile(_: dict[str, Any]) -> dict:
    from plotter.services.profiles import ProfileService

    return ProfileService().active()


def tool_list_profiles(_: dict[str, Any]) -> list[dict]:
    from plotter.services.profiles import ProfileService

    return ProfileService().list(include_archived=True)


def tool_list_fonts(_: dict[str, Any]) -> dict:
    from plotter.services.fonts import list_fonts
    from plotter.services.stroke_fonts import StrokeFontService

    return {
        "fonts": [font.__dict__ for font in list_fonts()],
        "strokeFonts": StrokeFontService().list(),
    }


def tool_list_jobs(_: dict[str, Any]) -> list[dict]:
    from plotter.web.routes.jobs import list_jobs

    return [job.model_dump() for job in list_jobs()]


def tool_get_job_preview(args: dict[str, Any]) -> dict:
    from plotter.core.storage import jobs_dir
    from plotter.gcode.preview import parse_gcode

    filename = Path(require_arg(args, "filename")).name
    path = jobs_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Job nicht gefunden: {filename}")
    preview = parse_gcode(path)
    bounds = preview.get("bounds") or [0, 0, 1, 1]
    width = max(float(bounds[2]) - min(float(bounds[0]), 0.0), 1.0)
    height = max(float(bounds[3]) - min(float(bounds[1]), 0.0), 1.0)
    return {
        "filename": filename,
        **preview,
        "svg": polylines_svg(
            preview.get("polylines") or [],
            travels=preview.get("travels") or [],
            width=width,
            height=height,
            title=filename,
        ),
    }
