"""Registry of MCP tool handlers, keyed by the external tool name."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from plotter.mcp.handlers import gallery, info, pages, printer
from plotter.mcp.schemas import TOOLS

ToolHandler = Callable[[dict[str, Any]], Any]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_printer_status": printer.tool_get_printer_status,
    "get_printer_position": printer.tool_get_printer_position,
    "get_mcp_overview": info.tool_get_mcp_overview,
    "get_mcp_tutorial": info.tool_get_mcp_tutorial,
    "printer_home": printer.tool_printer_home,
    "printer_move_to": printer.tool_printer_move_to,
    "printer_pen": printer.tool_printer_pen,
    "printer_job_command": printer.tool_printer_job_command,
    "get_active_profile": info.tool_get_active_profile,
    "list_profiles": info.tool_list_profiles,
    "list_pages": pages.tool_list_pages,
    "list_mcp_pages": pages.tool_list_mcp_pages,
    "get_page": pages.tool_get_page,
    "delete_mcp_page": pages.tool_delete_mcp_page,
    "get_page_svg": pages.tool_get_page_svg,
    "list_fonts": info.tool_list_fonts,
    "list_gallery": gallery.tool_list_gallery,
    "get_gallery_item": gallery.tool_get_gallery_item,
    "get_gallery_svg": gallery.tool_get_gallery_svg,
    "list_jobs": info.tool_list_jobs,
    "get_job_preview": info.tool_get_job_preview,
    "plot_page": pages.tool_plot_page,
    "create_page_and_plot_polylines": pages.tool_create_page_and_plot_polylines,
    "add_polylines_to_page_and_plot": pages.tool_add_polylines_to_page_and_plot,
    "create_page_and_plot_drawing": pages.tool_create_page_and_plot_drawing,
    "add_drawing_to_page_and_plot": pages.tool_add_drawing_to_page_and_plot,
    "create_page_and_plot_text": pages.tool_create_page_and_plot_text,
    "add_text_to_page_and_plot": pages.tool_add_text_to_page_and_plot,
    "create_page_and_plot_gallery_item": pages.tool_create_page_and_plot_gallery_item,
    "add_gallery_item_to_page_and_plot": pages.tool_add_gallery_item_to_page_and_plot,
}

# Tools that mutate designer pages; a successful call should refresh the open
# canvas live, not just the page list.
MUTATING_TOOLS = frozenset(
    {
        "delete_mcp_page",
        "create_page_and_plot_polylines",
        "add_polylines_to_page_and_plot",
        "create_page_and_plot_drawing",
        "add_drawing_to_page_and_plot",
        "create_page_and_plot_text",
        "add_text_to_page_and_plot",
        "create_page_and_plot_gallery_item",
        "add_gallery_item_to_page_and_plot",
    }
)

# The registry and the published schemas must always cover the same tools.
assert set(TOOL_HANDLERS) == {tool["name"] for tool in TOOLS}
