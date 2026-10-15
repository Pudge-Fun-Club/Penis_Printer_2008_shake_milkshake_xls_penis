from __future__ import annotations

import math

from fastapi import APIRouter, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from plotter.core.calibration import Calibration
from plotter.notes import layout, ocr, vectorize
from plotter.notes.guards import paper_applied
from plotter.notes.handwriting import STYLES
from plotter.notes.paper_stack import remove_sheet, stack_status
from plotter.services.errors import ServiceError
from plotter.services.fonts import list_fonts
from plotter.services.profiles import ProfileService
from plotter.services.settings_store import patch_saved
from plotter.services.upload_validation import MAX_UPLOAD_BYTES
from plotter.web.deps import printer_controller

router = APIRouter(tags=["notes"])


class LayoutRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=20000)
    font: str = "notes-neat"
    size: float = Field(default=4, ge=1.5, le=15)
    margin: float = Field(default=5, ge=0, le=50)
    line_spacing: float = Field(default=1.9, ge=1.5, le=4)

    @field_validator("size", "margin", "line_spacing", mode="before")
    @classmethod
    def finite_dimensions(cls, value):
        try:
            finite = math.isfinite(float(value))
        except (TypeError, ValueError):
            return value
        if not finite:
            raise ServiceError("Размеры должны быть конечными числами.")
        return value


class OcrSettingsRequest(BaseModel):
    api_key: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, min_length=1, max_length=100)


@router.get("/notes/status")
def status() -> dict:
    profile = ProfileService().active()
    cal = Calibration().merged(profile["calibration"])
    return {
        **ocr.status(),
        "penCalibrated": cal.pen_calibrated,
        "paperCalibrated": paper_applied(cal),
        "width": cal.plot_width,
        "height": cal.plot_height,
        "paperStack": stack_status(profile),
        "fonts": [
            *STYLES,
            *[{"id": f.id, "label": f.label} for f in list_fonts() if f.id != "block"],
        ],
    }


class NextSheetRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    thickness_mm: float = Field(ge=0.001, le=1)
    profile_id: str = Field(min_length=1, max_length=100)
    fingerprint: str = Field(min_length=1, max_length=100)


@router.post("/notes/next-sheet")
def next_sheet(req: NextSheetRequest) -> dict:
    # Change only future job coordinates; do not jog or home the printer.
    remove_sheet(**req.model_dump(), status=printer_controller().status())
    return status()


@router.put("/notes/ocr-settings")
def ocr_settings(req: OcrSettingsRequest) -> dict:
    updates = {}
    if req.api_key is not None:
        updates["notes.api_key"] = req.api_key.strip()
    if req.model is not None:
        updates["notes.model"] = req.model.strip() or ocr.DEFAULT_MODEL
    patch_saved(updates)
    return ocr.status()


@router.post("/notes/transcribe")
async def transcribe(file: UploadFile) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    return await run_in_threadpool(ocr.transcribe, data)


@router.post("/notes/preview")
def preview(req: LayoutRequest) -> dict:
    return layout.preview(**req.model_dump())


@router.post("/notes/jobs")
def jobs(req: LayoutRequest) -> dict:
    return layout.jobs(**req.model_dump())


class VectorRequest(BaseModel):
    id: str = Field(pattern=r"^[a-f0-9]{24}$")
    font: str = "original"
    margin: float = Field(default=5, ge=0, le=50)

    @field_validator("margin", mode="before")
    @classmethod
    def finite_margin(cls, value):
        return LayoutRequest.finite_dimensions(value)


@router.post("/notes/vectorize")
async def vectorize_photo(
    file: UploadFile, straighten: bool = Form(False), detail: int = Form(3)
) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    return await run_in_threadpool(
        vectorize.create, data, straighten=straighten, detail=max(1, min(detail, 3))
    )


@router.post("/notes/vector-preview")
def vector_preview(req: VectorRequest) -> dict:
    return vectorize.preview(**req.model_dump())


@router.post("/notes/vector-jobs")
def vector_jobs(req: VectorRequest) -> dict:
    return vectorize.jobs(**req.model_dump())
