"""Follow the top of an unknown stack by confirmed single-sheet removals."""

from __future__ import annotations

import math

from plotter.core.calibration import Calibration
from plotter.services.profiles import ProfileConflict, ProfileService


def stack_status(profile: dict) -> dict:
    cal = Calibration().merged(profile["calibration"])
    return {
        "profileId": profile["id"],
        "fingerprint": profile["fingerprint"],
        "thicknessMm": cal.paper_thickness_mm,
        "penDownZ": cal.pen_down_z,
        "penUpZ": cal.pen_up_z,
    }


def remove_sheet(thickness_mm: float, profile_id: str, fingerprint: str, status: dict) -> None:
    state = str((status.get("job") or {}).get("state", "")).lower()
    if any(s in state for s in ("printing", "paused", "pausing", "resuming", "cancelling")):
        raise ProfileConflict("Дождитесь завершения записи перед сменой листа.")
    profiles = ProfileService()
    cal = Calibration().merged(profiles.active()["calibration"])
    heights = (cal.pen_down_z, cal.pen_up_z, cal.z_max)
    if not cal.pen_calibrated or not all(math.isfinite(z) for z in heights):
        raise ProfileConflict("Сначала откалибруйте ручку на верхнем листе стопки.")
    # G-code coordinates use 0.001 mm; round each step to avoid accumulated
    # floating-point noise after many pages. Lift clearance remains unchanged.
    thickness = round(thickness_mm, 3)
    down = round(cal.pen_down_z - thickness, 3)
    up = round(cal.pen_up_z - thickness, 3)
    if not 0 <= down < up <= cal.z_max:
        raise ProfileConflict("Высота выйдет за пределы Z. Откалибруйте ручку заново.")
    profiles.update_active_calibration(
        profile_id,
        fingerprint,
        {
            "pen_down_z": down,
            "pen_up_z": up,
            "paper_thickness_mm": thickness,
        },
    )
