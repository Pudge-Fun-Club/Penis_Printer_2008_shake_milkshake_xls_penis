"""MCP tools for browsing the gallery."""

from __future__ import annotations

from typing import Any

from plotter.mcp.args import int_arg, require_arg
from plotter.mcp.shapes import polylines_svg


def tool_list_gallery(args: dict[str, Any]) -> list[dict]:
    from plotter.services.gallery import GalleryService

    include_archived = bool(args.get("include_archived", True))
    uploader = args.get("uploader")
    if uploader is not None and not isinstance(uploader, str):
        raise ValueError("uploader must be a string")
    return GalleryService().list(include_archived=include_archived, uploader=uploader)


def tool_get_gallery_item(args: dict[str, Any]) -> dict:
    from plotter.services.gallery import GalleryService

    return GalleryService().get(require_arg(args, "item_id"))


def tool_get_gallery_svg(args: dict[str, Any]) -> dict:
    from plotter.services.gallery import GalleryService

    item_id = require_arg(args, "item_id")
    page = int_arg(args, "page", 1, lo=1, hi=999)
    max_points = int_arg(args, "max_points", 20000, lo=100, hi=40000)
    preview = GalleryService().preview(item_id, page=page, max_points=max_points)
    polylines = preview.get("polylines") or []
    width = float(preview.get("width") or 1.0)
    height = float(preview.get("height") or 1.0)
    return {
        "item_id": item_id,
        "page": page,
        "width": width,
        "height": height,
        "polylines": polylines,
        "svg": polylines_svg(
            polylines,
            width=width,
            height=height,
            title=f"gallery {item_id} page {page}",
        ),
    }
