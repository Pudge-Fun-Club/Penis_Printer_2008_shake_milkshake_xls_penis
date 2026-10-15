"""Word wrapping and pagination in calibrated plot-area millimetres."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from uuid import uuid4

from plotter.core.calibration import Calibration
from plotter.gcode.scene import save_scene_job
from plotter.notes.guards import check_ink
from plotter.notes.handwriting import STYLES, render_line
from plotter.services.errors import ServiceError
from plotter.services.profiles import ProfileService, profile_meta


def _bounds(lines: list) -> tuple[float, float, float, float]:
    pts = [p for line in lines for p in line]
    if not pts:
        return 0, 0, 0, 0
    return (
        min(p[0] for p in pts),
        min(p[1] for p in pts),
        max(p[0] for p in pts),
        max(p[1] for p in pts),
    )


def _render(text: str, font: str, size: float) -> list:
    if font in {s["id"] for s in STYLES}:
        return render_line(text, font, size)
    if font.startswith("stroke-"):
        from plotter.services.stroke_fonts import StrokeFontService

        result = StrokeFontService().render(font, text, size)
        if result.missing:
            raise ServiceError("В выбранном почерке нет символов: " + " ".join(result.missing))
        lines = result.polylines
    else:
        from plotter.text import text_polylines
        from plotter.text.fonts import load_font

        cmap = load_font(font).getBestCmap() or {}
        missing = sorted({ch for ch in text if not ch.isspace() and ord(ch) not in cmap})
        if missing:
            raise ServiceError("В выбранном шрифте нет символов: " + " ".join(missing))
        lines = text_polylines(text, font=font, size=size)
    if text.strip() and not lines:
        raise ServiceError("В выбранном шрифте отсутствуют штрихи для текста.")
    return lines


def preview(text: str, font: str, size: float, margin: float, line_spacing: float) -> dict:
    if not text.strip():
        raise ServiceError("Добавьте текст конспекта.")
    if len(text) > 20000:
        raise ServiceError("Конспект слишком длинный: максимум 20 000 символов за раз.")
    if not all(math.isfinite(v) for v in (size, margin, line_spacing)):
        raise ServiceError("Размеры должны быть конечными числами.")
    active = ProfileService().active()
    cal = Calibration().merged(active["calibration"])
    width, height = cal.plot_width, cal.plot_height
    available = width - margin * 2
    row_height = size * line_spacing
    rows_per_page = math.floor((height - margin * 2) / row_height)
    if available <= 0 or rows_per_page < 1:
        raise ServiceError("Текст не помещается. Уменьшите поля или размер почерка.")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")

    @lru_cache(maxsize=1024)
    def rendered(line: str) -> tuple[list, tuple]:
        lines = _render(line, font, size)
        return lines, _bounds(lines)

    def fits(line: str) -> bool:
        _, b = rendered(line)
        return b[2] - b[0] <= available + 1e-7

    wrapped: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            wrapped.append("")
            continue
        line = ""
        for word in re.findall(r"\S+", paragraph):
            candidate = f"{line} {word}" if line else word
            if fits(candidate):
                line = candidate
                continue
            if line:
                wrapped.append(line)
                line = ""
            for ch in word:
                if not fits(line + ch):
                    if not line:
                        raise ServiceError(f"Символ «{ch}» не помещается по ширине листа.")
                    wrapped.append(line)
                    line = ""
                line += ch
        if line:
            wrapped.append(line)

    pages = []
    for offset in range(0, len(wrapped), rows_per_page):
        rows = wrapped[offset : offset + rows_per_page]
        lines = []
        for i, row in enumerate(rows):
            strokes, b = rendered(row)
            if b[3] - b[1] > row_height + 1e-7:
                raise ServiceError("Строки перекрываются. Увеличьте межстрочный интервал.")
            lines.extend(
                [
                    [
                        [round(x - b[0] + margin, 3), round(y - b[1] + margin + i * row_height, 3)]
                        for x, y in stroke
                    ]
                    for stroke in strokes
                    if len(stroke) >= 2
                ]
            )
        pages.append(
            {
                "number": len(pages) + 1,
                "text": "\n".join(rows),
                "width": width,
                "height": height,
                "polylines": lines,
            }
        )
    return {
        "pages": pages,
        "profile": profile_meta(active),
        "warnings": [],
    }


def jobs(text: str, font: str, size: float, margin: float, line_spacing: float) -> dict:
    result = preview(text, font, size, margin, line_spacing)
    active = ProfileService().active()
    profile = profile_meta(active)
    if profile != result["profile"]:
        raise ServiceError("Калибровка изменилась. Повторите создание конспекта.")
    cal = Calibration().merged(active["calibration"])
    batch = uuid4().hex[:12]
    result["jobs"] = []
    for sheet in result["pages"]:
        # Pure whitespace pages are kept in the preview, but have nothing to plot.
        if not sheet["polylines"]:
            result["jobs"].append({"number": sheet["number"], "filename": None})
            continue
        page = {
            "id": f"notes-{batch}-{sheet['number']}",
            "name": f"конспект-{batch}-лист-{sheet['number']}",
            "continuous": False,
            "objects": [
                {
                    "cachedPolylines": sheet["polylines"],
                    "cachedFeeds": [[1.0] * len(line) for line in sheet["polylines"]],
                }
            ],
        }
        check_ink(sheet["polylines"], cal)
        path = save_scene_job(
            page,
            cal,
            profile,
            source_kind="notebook",
            source_extra={"batch": batch, "sheet": sheet["number"], "font": font},
        )
        result["jobs"].append({"number": sheet["number"], "filename": path.name})
    return result
