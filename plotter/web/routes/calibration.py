from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from plotter.artwork.export import CalibrationImportError, calibration_from_xml, calibration_to_xml
from plotter.core.calibration import Calibration
from plotter.web.deps import printer_controller

router = APIRouter(tags=["calibration"])


@router.get("/calibration/export")
def export_calibration() -> Response:
    """Download the full calibration as XML."""
    return Response(
        calibration_to_xml(Calibration.load()),
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="plotter-calibration.xml"'},
    )


@router.post("/calibration/import")
async def import_calibration(file: UploadFile = File(...)) -> dict:
    """Replace the calibration from an uploaded XML file.

    Missing fields fall back to the current calibration, so a partial export
    still imports cleanly.
    """
    try:
        text = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CalibrationImportError("Datei ist kein UTF-8-Text.") from exc
    cal = calibration_from_xml(text, base=Calibration.load())
    cal.save()
    return cal.as_dict()


@router.get("/calibration")
def get_calibration() -> dict:
    return Calibration.load().as_dict()


@router.put("/calibration")
def put_calibration(updates: dict) -> dict:
    cal = Calibration.load().merged(updates)
    cal.save()
    return cal.as_dict()


class PenHeightRequest(BaseModel):
    which: str  # up | down


@router.post("/calibration/pen-from-position")
def pen_from_position(req: PenHeightRequest) -> dict:
    """Store the current head Z as the pen-up or pen-down height."""
    return printer_controller().pen_height_from_position(req.which).as_dict()
