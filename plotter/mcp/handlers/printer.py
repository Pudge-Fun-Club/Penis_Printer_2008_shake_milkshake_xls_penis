"""MCP tools for direct printer control (status, motion, pen, job commands).

Service imports stay inside the functions: tests monkeypatch
``plotter.services.PrinterController``, which only works with late binding.
"""

from __future__ import annotations

from typing import Any

from plotter.mcp.args import float_arg, require_arg


def tool_get_printer_status(_: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    return PrinterController().status()


def tool_get_printer_position(_: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    return PrinterController().position()


def tool_printer_home(args: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    axes_raw = args.get("axes")
    axes = None
    if axes_raw is not None:
        if not isinstance(axes_raw, list) or not all(isinstance(axis, str) for axis in axes_raw):
            raise ValueError("axes must be an array of strings")
        axes = axes_raw
    return {"ok": True, "position": PrinterController().home(axes)}


def tool_printer_move_to(args: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    x = float_arg(args, "x")
    y = float_arg(args, "y")
    limit = args.get("limit") or "plot"
    if limit not in ("plot", "bed"):
        raise ValueError("limit must be 'plot' or 'bed'")
    return {
        "ok": True,
        "position": PrinterController().move_to(x, y, pen_up_first=True, limit=limit),
    }


def tool_printer_pen(args: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    down = args.get("down")
    if not isinstance(down, bool):
        raise ValueError("down must be a boolean")
    return {"ok": True, **PrinterController().pen(down)}


def tool_printer_job_command(args: dict[str, Any]) -> dict:
    from plotter.services import PrinterController

    command = require_arg(args, "command")
    if command not in ("pause", "resume", "cancel"):
        raise ValueError("command must be pause, resume or cancel")
    PrinterController().client.job_command(command)
    return {"ok": True, "command": command}
