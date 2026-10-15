"""Keep a photographed page as real SVG strokes, including all illustrations.

Handwriting replacement is optional: vision finds text boxes, the original
non-text strokes remain, and only those boxes receive new letter strokes.
"""

from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET

import cv2
import numpy as np
from PIL import Image

from plotter.artwork.trace import centerline_image_to_drawing
from plotter.core.calibration import Calibration, data_dir
from plotter.core.jsonstore import atomic_write_json
from plotter.gcode.scene import save_scene_job
from plotter.geometry.primitives import apply_masks
from plotter.notes import ocr
from plotter.notes.guards import check_ink
from plotter.notes.layout import _bounds, _render
from plotter.notes.optimize import optimize_strokes
from plotter.notes.ruling import remove_ruling
from plotter.services.errors import ServiceError
from plotter.services.profiles import ProfileService, profile_meta

_SVG_NS = "http://www.w3.org/2000/svg"
_TRACE_VERSION = 3
ET.register_namespace("", _SVG_NS)


def _folder(asset_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{24}", asset_id):
        raise ServiceError("Некорректный идентификатор страницы.")
    folder = data_dir() / "notes" / asset_id
    if not (folder / "page.json").exists():
        error = ServiceError("Страница не найдена. Загрузите фотографию заново.")
        error.status_code = 404
        raise error
    return folder


def svg_document(width: float, height: float, groups: dict[str, list]) -> str:
    root = ET.Element(
        f"{{{_SVG_NS}}}svg",
        {
            "width": f"{width:.3f}mm",
            "height": f"{height:.3f}mm",
            "viewBox": f"0 0 {width:.3f} {height:.3f}",
            "fill": "none",
            "stroke": "black",
            "stroke-width": "0.3",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        },
    )
    for name, lines in groups.items():
        group = ET.SubElement(root, f"{{{_SVG_NS}}}g", {"id": name})
        for line in lines:
            if len(line) >= 2:
                path = "M" + "L".join(f"{x:.3f},{y:.3f}" for x, y in line)
                ET.SubElement(group, f"{{{_SVG_NS}}}path", {"d": path})
    return ET.tostring(root, encoding="unicode")


def _straighten(rgb: np.ndarray) -> np.ndarray:
    """Correct perspective only when a large quadrilateral page is found."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4 or cv2.contourArea(approx) < gray.size * 0.5:
            continue
        points = approx.reshape(4, 2).astype(np.float32)
        ordered = np.array(
            [
                points[np.argmin(points.sum(axis=1))],
                points[np.argmin(np.diff(points, axis=1))],
                points[np.argmax(points.sum(axis=1))],
                points[np.argmax(np.diff(points, axis=1))],
            ],
            dtype=np.float32,
        )
        if len(np.unique(ordered, axis=0)) != 4:
            continue
        tl, tr, br, bl = ordered
        width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if width < 100 or height < 100:
            continue
        target = np.array(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32
        )
        return cv2.warpPerspective(
            rgb,
            cv2.getPerspectiveTransform(ordered, target),
            (width, height),
            borderValue=(255, 255, 255),
        )
    return rgb


def create(data: bytes, *, straighten: bool = False, detail: int = 3) -> dict:
    prepared, _ = ocr.prepare_image(data)
    image = np.asarray(Image.open(io.BytesIO(prepared)).convert("RGB"))
    if straighten:
        image = _straighten(image)
    asset_id = uuid4().hex[:24]
    folder = data_dir() / "notes" / asset_id
    folder.mkdir(parents=True)
    try:
        Image.fromarray(image).save(folder / "photo.png")
        page = _trace_page(folder, asset_id, image, detail)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {"id": asset_id, "width": page["width"], "height": page["height"],
            "strokes": len(page["polylines"])}


def _trace_page(folder: Path, asset_id: str, image: np.ndarray, detail: int = 3) -> dict:
    Image.fromarray(remove_ruling(image)).save(folder / "trace.png")
    drawing = centerline_image_to_drawing(
        folder / "trace.png", folder / "original.svg", detail=detail, preserve_dots=True
    )
    page = {
        "id": asset_id, "width": drawing.width, "height": drawing.height,
        "trace_version": _TRACE_VERSION,
        "polylines": [[[round(float(p.real), 5), round(float(p.imag), 5)] for p in line]
                      for line in drawing.polylines],
    }
    atomic_write_json(folder / "page.json", page)
    return page


def _replace_text(page: dict, folder: Path, font: str) -> tuple[list, list, list]:
    regions_file = folder / "regions.json"
    if regions_file.exists():
        regions = json.loads(regions_file.read_text())
    else:
        regions = ocr.text_regions((folder / "photo.png").read_bytes())
        atomic_write_json(regions_file, regions)
    if not regions:
        raise ServiceError("Текстовые строки не найдены. Выберите «Как на фото».")
    masks, replacement = [], []
    for region in regions:
        x0, y0, x1, y1 = region["box"]
        x0, x1 = x0 * page["width"] / 1000, x1 * page["width"] / 1000
        y0, y1 = y0 * page["height"] / 1000, y1 * page["height"] / 1000
        row_text = region["text"].splitlines()
        for i, text in enumerate(row_text):
            strokes = _render(text, font, 10)
            b = _bounds(strokes)
            scale = min(
                (x1 - x0) / max(b[2] - b[0], 0.01),
                (y1 - y0) / (max(len(row_text), 1) * max(b[3] - b[1], 0.01)),
            )
            top = y0 + i * (y1 - y0) / len(row_text)
            replacement.extend(
                [
                    [[x0 + (x - b[0]) * scale, top + (y - b[1]) * scale] for x, y in line]
                    for line in strokes
                ]
            )
        masks.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    graphics = apply_masks(page["polylines"], masks)
    return graphics, replacement, regions


def preview(id: str, font: str = "original", margin: float = 5) -> dict:
    folder = _folder(id)
    page = json.loads((folder / "page.json").read_text())
    if page.get("trace_version", 0) < _TRACE_VERSION:
        image = np.asarray(Image.open(folder / "photo.png").convert("RGB"))
        page = _trace_page(folder, id, image)
    profile = ProfileService().active()
    cal = Calibration().merged(profile["calibration"])
    scale = min(
        (cal.plot_width - 2 * margin) / page["width"],
        (cal.plot_height - 2 * margin) / page["height"],
    )
    if scale <= 0:
        raise ServiceError("Поля слишком большие для рабочего участка бумаги.")
    left = (cal.plot_width - page["width"] * scale) / 2
    top = (cal.plot_height - page["height"] * scale) / 2
    if font == "original":
        graphics, text, regions = page["polylines"], [], []
    else:
        graphics, text, regions = _replace_text(page, folder, font)

    def placed(lines):
        return [
            [[round(x * scale + left, 3), round(y * scale + top, 3)] for x, y in line]
            for line in lines
        ]

    graphics, text = placed(graphics), placed(text)
    check_ink(graphics + text, cal)
    optimized, optimization = optimize_strokes(graphics + text, cal)
    check_ink(optimized, cal)
    svg = svg_document(cal.plot_width, cal.plot_height, {"strokes": optimized})
    return {
        "pages": [
            {
                "number": 1,
                "text": "",
                "width": cal.plot_width,
                "height": cal.plot_height,
                "polylines": optimized,
                "graphics": graphics,
                "svg": svg,
                "optimization": optimization,
            }
        ],
        "profile": profile_meta(profile),
        "regions": regions,
        "warnings": ["Проверьте области замены текста: рисунки и формулы должны остаться вне них."]
        if font != "original"
        else [],
    }


def jobs(id: str, font: str = "original", margin: float = 5) -> dict:
    result = preview(id, font, margin)
    active = ProfileService().active()
    if profile_meta(active) != result["profile"]:
        raise ServiceError("Профиль изменился. Обновите предпросмотр SVG.")
    sheet = result["pages"][0]
    cal = Calibration().merged(active["calibration"])
    name = f"svg-{id[:8]}-{uuid4().hex[:8]}"
    source_svg = _folder(id) / f"{name}.svg"
    source_svg.write_text(sheet["svg"])
    # The SVG is the actual intermediate document consumed for printing.
    from plotter.artwork.drawing import load_svg_drawing

    # Keep the reviewed route: the general SVG importer's endpoint merging can
    # reorder paths or bridge small intentional gaps between characters.
    drawing = load_svg_drawing(source_svg, quantization_mm=0.01, merge=False)
    printable = [[[float(p.real), float(p.imag)] for p in line] for line in drawing.polylines]
    page = {
        "id": id,
        "name": name,
        "continuous": False,
        "objects": [
            {"cachedPolylines": printable, "cachedFeeds": [[1.0] * len(line) for line in printable]}
        ],
    }
    path = save_scene_job(
        page,
        cal,
        result["profile"],
        source_kind="notebook",
        source_extra={"vector_id": id, "font": font, "format": "svg"},
    )
    path.with_suffix(".svg").write_text(sheet["svg"])
    result["jobs"] = [{"number": 1, "filename": path.name}]
    return result
