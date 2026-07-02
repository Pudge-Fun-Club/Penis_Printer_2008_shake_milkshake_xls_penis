"""JSON schemas of every MCP tool. Tool names and schemas are external API
consumed by MCP clients — never rename or restructure them casually."""

from __future__ import annotations

from typing import Any


def _schema(properties: dict[str, dict] | None = None, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_printer_status",
        "description": (
            "Return the active printer backend status, including connection and job progress."
        ),
        "inputSchema": _schema(),
    },
    {
        "name": "get_printer_position",
        "description": "Return the server-side tracked plotter head position.",
        "inputSchema": _schema(),
    },
    {
        "name": "get_mcp_overview",
        "description": (
            "Return a concise overview of what GCodeScribe is, what it can do, and how MCP "
            "agents should use it safely."
        ),
        "inputSchema": _schema(),
    },
    {
        "name": "get_mcp_tutorial",
        "description": (
            "Explain how to use the GCodeScribe MCP tools safely, including the expected "
            "workflow for drawing, plotting, previewing and cleanup."
        ),
        "inputSchema": _schema(),
    },
    {
        "name": "printer_home",
        "description": "Home the plotter through the configured printer backend.",
        "inputSchema": _schema(
            {"axes": {"type": "array", "description": "Optional axes, e.g. ['x', 'y', 'z']."}},
        ),
    },
    {
        "name": "printer_move_to",
        "description": (
            "Move the head to an absolute coordinate. Defaults to the active plot area limit."
        ),
        "inputSchema": _schema(
            {
                "x": {"type": "number", "description": "Target X in printer mm."},
                "y": {"type": "number", "description": "Target Y in printer mm."},
                "limit": {"type": "string", "default": "plot", "description": "plot or bed."},
            },
            ["x", "y"],
        ),
    },
    {
        "name": "printer_pen",
        "description": "Move the pen to the calibrated up or down height.",
        "inputSchema": _schema(
            {"down": {"type": "boolean", "description": "True for pen down, false for pen up."}},
            ["down"],
        ),
    },
    {
        "name": "printer_job_command",
        "description": "Send a safe job command: pause, resume or cancel.",
        "inputSchema": _schema(
            {"command": {"type": "string", "description": "pause, resume or cancel."}},
            ["command"],
        ),
    },
    {
        "name": "get_active_profile",
        "description": "Return the active plotter profile and safety-relevant calibration values.",
        "inputSchema": _schema(),
    },
    {
        "name": "list_profiles",
        "description": "List all plotter profiles, including archived profiles.",
        "inputSchema": _schema(),
    },
    {
        "name": "list_pages",
        "description": "List designer pages with their names, active page id and profile metadata.",
        "inputSchema": _schema(),
    },
    {
        "name": "list_mcp_pages",
        "description": "List only designer pages that were created by MCP tools.",
        "inputSchema": _schema(),
    },
    {
        "name": "get_page",
        "description": "Return a designer page by id, including its objects.",
        "inputSchema": _schema(
            {"page_id": {"type": "string", "description": "Designer page id."}},
            ["page_id"],
        ),
    },
    {
        "name": "delete_mcp_page",
        "description": "Delete a designer page only if it was created by MCP.",
        "inputSchema": _schema(
            {"page_id": {"type": "string", "description": "MCP-created designer page id."}},
            ["page_id"],
        ),
    },
    {
        "name": "get_page_svg",
        "description": "Return an SVG preview of the plottable paths on a designer page.",
        "inputSchema": _schema(
            {"page_id": {"type": "string", "description": "Designer page id."}},
            ["page_id"],
        ),
    },
    {
        "name": "list_fonts",
        "description": "List text fonts and handwriting stroke fonts available for MCP text tools.",
        "inputSchema": _schema(),
    },
    {
        "name": "list_gallery",
        "description": "List gallery items available for preview/insertion.",
        "inputSchema": _schema(
            {
                "include_archived": {"type": "boolean", "default": True},
                "uploader": {"type": "string", "description": "Optional uploader filter."},
            },
        ),
    },
    {
        "name": "get_gallery_item",
        "description": "Return a gallery item by id.",
        "inputSchema": _schema(
            {"item_id": {"type": "string", "description": "Gallery item id."}},
            ["item_id"],
        ),
    },
    {
        "name": "get_gallery_svg",
        "description": "Return an SVG preview for one gallery item page.",
        "inputSchema": _schema(
            {
                "item_id": {"type": "string", "description": "Gallery item id."},
                "page": {"type": "integer", "default": 1},
                "max_points": {"type": "integer", "default": 20000},
            },
            ["item_id"],
        ),
    },
    {
        "name": "list_jobs",
        "description": "List generated G-code jobs with profile and safety status.",
        "inputSchema": _schema(),
    },
    {
        "name": "get_job_preview",
        "description": (
            "Return parsed draw/travel polylines and an SVG preview for a generated job."
        ),
        "inputSchema": _schema(
            {"filename": {"type": "string", "description": "Job filename."}},
            ["filename"],
        ),
    },
    {
        "name": "plot_page",
        "description": (
            "Generate and immediately plot an existing designer page. The page must belong "
            "to the active profile."
        ),
        "inputSchema": _schema(
            {"page_id": {"type": "string", "description": "Designer page id."}},
            ["page_id"],
        ),
    },
    {
        "name": "create_page_and_plot_polylines",
        "description": (
            "Create a new designer page from plot-area polylines and immediately plot it. "
            "If anything is outside the active profile border, nothing is saved or plotted."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string", "description": "Name for the new designer page."},
                "polylines": {
                    "type": "array",
                    "description": "Polylines in mm relative to the active plot area.",
                },
            },
            ["polylines"],
        ),
    },
    {
        "name": "add_polylines_to_page_and_plot",
        "description": (
            "Add plot-area polylines to an existing designer page and immediately plot the "
            "updated page. If the resulting page exceeds the active border, nothing changes."
        ),
        "inputSchema": _schema(
            {
                "page_id": {"type": "string", "description": "Designer page id."},
                "polylines": {
                    "type": "array",
                    "description": "Polylines in mm relative to the active plot area.",
                },
            },
            ["page_id", "polylines"],
        ),
    },
    {
        "name": "create_page_and_plot_drawing",
        "description": (
            "Create a new page from drawing elements and immediately plot it. Elements may be "
            "polyline, line, rect, circle, ellipse, arc, polygon, star, spiral, wave, grid "
            "or hatch."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string", "description": "Name for the new designer page."},
                "elements": {"type": "array", "description": "Drawing elements in plot-area mm."},
            },
            ["elements"],
        ),
    },
    {
        "name": "add_drawing_to_page_and_plot",
        "description": (
            "Add drawing elements to an existing page and immediately plot the updated page. "
            "If the resulting page exceeds the active border, nothing changes."
        ),
        "inputSchema": _schema(
            {
                "page_id": {"type": "string", "description": "Designer page id."},
                "elements": {"type": "array", "description": "Drawing elements in plot-area mm."},
            },
            ["page_id", "elements"],
        ),
    },
    {
        "name": "create_page_and_plot_text",
        "description": (
            "Create a new designer page containing text and immediately plot it. "
            "Text is placed in plot-area mm and rejected if it exceeds the active border."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string", "description": "Name for the new designer page."},
                "text": {"type": "string", "description": "Text to render and plot."},
                "x": {"type": "number", "description": "Left position in plot-area mm."},
                "y": {"type": "number", "description": "Top position in plot-area mm."},
                "size": {"type": "number", "description": "Text size in mm."},
                "font": {"type": "string", "description": "Font id from list_fonts."},
                "connect_spaces": {"type": "boolean", "default": False},
                "seed": {"type": "integer", "default": 0},
            },
            ["text", "x", "y", "size", "font"],
        ),
    },
    {
        "name": "add_text_to_page_and_plot",
        "description": (
            "Add text to an existing designer page and immediately plot the updated page. "
            "If the resulting page exceeds the active border, nothing changes."
        ),
        "inputSchema": _schema(
            {
                "page_id": {"type": "string", "description": "Designer page id."},
                "text": {"type": "string", "description": "Text to render and plot."},
                "x": {"type": "number", "description": "Left position in plot-area mm."},
                "y": {"type": "number", "description": "Top position in plot-area mm."},
                "size": {"type": "number", "description": "Text size in mm."},
                "font": {"type": "string", "description": "Font id from list_fonts."},
                "connect_spaces": {"type": "boolean", "default": False},
                "seed": {"type": "integer", "default": 0},
            },
            ["page_id", "text", "x", "y", "size", "font"],
        ),
    },
    {
        "name": "create_page_and_plot_gallery_item",
        "description": (
            "Place a gallery item page on a new designer page and immediately plot it. "
            "Placement is rejected if it exceeds the active profile border."
        ),
        "inputSchema": _schema(
            {
                "item_id": {"type": "string", "description": "Gallery item id."},
                "page": {"type": "integer", "default": 1},
                "name": {"type": "string", "description": "Name for the new designer page."},
                "x": {"type": "number", "description": "Left position in plot-area mm."},
                "y": {"type": "number", "description": "Top position in plot-area mm."},
                "scale": {"type": "number", "default": 1},
            },
            ["item_id", "x", "y"],
        ),
    },
    {
        "name": "add_gallery_item_to_page_and_plot",
        "description": (
            "Place a gallery item page on an existing designer page and immediately plot the "
            "updated page. If the resulting page exceeds the active border, nothing changes."
        ),
        "inputSchema": _schema(
            {
                "page_id": {"type": "string", "description": "Designer page id."},
                "item_id": {"type": "string", "description": "Gallery item id."},
                "page": {"type": "integer", "default": 1},
                "x": {"type": "number", "description": "Left position in plot-area mm."},
                "y": {"type": "number", "description": "Top position in plot-area mm."},
                "scale": {"type": "number", "default": 1},
            },
            ["page_id", "item_id", "x", "y"],
        ),
    },
]
