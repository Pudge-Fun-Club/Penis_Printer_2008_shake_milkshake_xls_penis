from __future__ import annotations

from plotter.core.calibration import Calibration
from plotter.gcode.safety import _seg_intersects_obs
from plotter.services.errors import ServiceError


def paper_applied(cal: Calibration) -> bool:
    rect = cal.paper_rect_inner()
    if rect is None:
        return False
    x, y, w, h = rect
    tol = 0.05
    return (
        x - tol <= cal.origin_x
        and y - tol <= cal.origin_y
        and cal.origin_x + cal.plot_width <= x + w + tol
        and cal.origin_y + cal.plot_height <= y + h + tol
    )


def check_ink(lines: list, cal: Calibration) -> None:
    """Reject clamp intersections rather than silently masking the document."""

    def printer(p):
        x, y = p
        return (
            cal.origin_x + x,
            cal.origin_y + cal.plot_height - y if cal.flip_y else cal.origin_y + y,
        )

    for line in lines:
        for a, b in zip(line, line[1:], strict=False):
            for obstacle in cal.obstacles:
                if _seg_intersects_obs(printer(a), printer(b), obstacle):
                    raise ServiceError(
                        "Линии попадают в область зажима. Измените поля или калибровку."
                    )
