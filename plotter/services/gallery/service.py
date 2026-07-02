"""The GalleryService facade. Heavy lifting lives in the sibling modules:
:mod:`builders` (create/rerender), :mod:`stl` (STL layers), :mod:`previews`
(polyline previews), :mod:`records` (meta.json normalisation)."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from plotter.artwork.drawing import load_svg_drawing
from plotter.artwork.pipeline import PlotterError
from plotter.core.calibration import Calibration, data_dir
from plotter.core.jobmeta import profile_comment
from plotter.services.asset_pages import (
    DESIGNER_POINTS,
    VALID_MODES,
    build_pages,
    preview_for,
    thumbnail_for,
)
from plotter.services.errors import ServiceError
from plotter.services.gallery import builders, previews, records, stl
from plotter.services.gallery.common import (
    FULL_PREVIEW_POINTS,
    GCODE_FILE,
    MAX_TITLE_LEN,
    SVG_FILE,
    THUMB_PREVIEW_POINTS,
    clear_derived,
    fitted_gcode,
    original_meta,
)
from plotter.services.profiles import ProfileService, profile_meta
from plotter.services.upload_validation import (
    MAX_STL_BYTES,
    MAX_UPLOAD_BYTES,
    UploadTooLarge,
    check_stl,
    sniff_asset_kind,
    sniff_kind,
)


class GalleryService:
    """The unified asset library.

    Two kinds of upload share ``data/gallery/<id>/``:

    - **Public submissions** (``/upload`` competition, ``uploader="public"``):
      a single image/SVG, traced, fitted and **scored** for plottability —
      stored as ``image.svg`` + ``job.gcode`` (the original behaviour).
    - **Admin assets** (``uploader="admin"``): general documents (PDF/Office)
      and images rendered to one or more page SVGs via the shared
      :mod:`asset_pages` core, with **on-demand** previews and **no** upfront
      score (placement is scored later via ``pageScore``).

    Every item carries a unified ``pages`` list; uploads that bust the size
    limits are deleted immediately and never listed.
    """

    def __init__(self, root: Path | None = None):
        self.root = root or (data_dir() / "gallery")
        self.root.mkdir(parents=True, exist_ok=True)

    # -- creation --------------------------------------------------------------

    def create(
        self,
        filename: str,
        data: bytes,
        title: str = "",
        uploader: str = "public",
        *,
        mode: str = "auto",
        detail: int = 2,
    ) -> dict:
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadTooLarge(
                f"Datei zu groß — maximal {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )
        uploader = uploader if uploader in ("admin", "public") else "public"
        name = Path(filename).name
        title = title.strip()[:MAX_TITLE_LEN]
        # Public uploads are scored single-image competition entries; only the
        # admin library accepts documents and uses the multi-page asset path.
        if uploader == "admin":
            if mode not in VALID_MODES:
                raise ServiceError(f"Unbekannter Modus: {mode}")
            kind = sniff_asset_kind(name, data)
        else:
            kind = sniff_kind(name, data)

        item_id = uuid.uuid4().hex[:12]
        item_dir = self.root / item_id
        item_dir.mkdir(parents=True)
        try:
            if uploader == "admin":
                meta = builders.build_asset(
                    item_dir, name, data, kind, title, item_id, mode, detail
                )
            else:
                meta = builders.build_submission(item_dir, name, data, kind, title, item_id)
        except Exception:
            shutil.rmtree(item_dir, ignore_errors=True)
            raise
        (item_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    # -- STL assets (client-rendered, server-stored) ---------------------------

    def create_stl(
        self,
        filename: str,
        stl_bytes: bytes,
        layers: list[dict],
        params: dict,
        title: str = "",
    ) -> dict:
        """Store an STL plus its client-rendered colour layers.

        The 3D→2D projection happens in the browser; here we persist the source
        ``.stl`` (so it can be re-opened and re-rendered with a new orientation)
        and one SVG page per pen colour, then build the usual previews.
        """
        if len(stl_bytes) > MAX_STL_BYTES:
            raise UploadTooLarge(
                f"STL zu groß — maximal {MAX_STL_BYTES // (1024 * 1024)} MB."
            )
        name = Path(filename).name
        check_stl(name, stl_bytes)
        title = title.strip()[:MAX_TITLE_LEN]
        item_id = uuid.uuid4().hex[:12]
        item_dir = self.root / item_id
        item_dir.mkdir(parents=True)
        try:
            original = item_dir / "original.stl"
            original.write_bytes(stl_bytes)
            pages = stl.write_stl_layers(item_dir, layers)
            (item_dir / "params.json").write_text(json.dumps(params))
            meta = {
                "id": item_id,
                "title": title,
                "filename": name,
                "kind": "stl",
                "uploader": "admin",
                "created": time.time(),
                "status": "active",
                "mode": "stl",
                "detail": 2,
                "continuous": True,
                "pages": pages,
                "width": max(p["width"] for p in pages),
                "height": max(p["height"] for p in pages),
                "lines": sum(p["lines"] for p in pages),
                "stl_params": params,
                "original": original_meta(name, "original.stl", "stl", len(stl_bytes)),
            }
        except Exception:
            shutil.rmtree(item_dir, ignore_errors=True)
            raise
        (item_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    def update_stl(self, item_id: str, layers: list[dict], params: dict) -> dict:
        """Replace an STL item's colour layers + params; the original .stl stays."""
        meta = self.get(item_id)
        if meta.get("kind") != "stl":
            raise ServiceError("Eintrag ist kein STL-Modell.")
        item_dir = self.root / item_id
        with tempfile.TemporaryDirectory(prefix=f"gallery-stl-{item_id}-") as tmp_raw:
            tmp = Path(tmp_raw)
            pages = stl.write_stl_layers(tmp, layers)  # validate everything first
            clear_derived(item_dir)
            for page in pages:
                shutil.copy(tmp / page["file"], item_dir / page["file"])
        (item_dir / "params.json").write_text(json.dumps(params))
        meta.update(
            {
                "pages": pages,
                "width": max(p["width"] for p in pages),
                "height": max(p["height"] for p in pages),
                "lines": sum(p["lines"] for p in pages),
                "stl_params": params,
            }
        )
        (item_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    def stl_params(self, item_id: str) -> dict:
        meta = self.get(item_id)
        if meta.get("kind") != "stl":
            raise ServiceError("Eintrag ist kein STL-Modell.")
        return meta.get("stl_params") or {}

    def rerender(
        self, item_id: str, *, mode: str, detail: int, continuous: bool = True
    ) -> dict:
        """Rebuild derived pages/previews from the stored original, in-place.

        The original file and stable item identity are preserved. All derived
        artifacts are generated in a temporary directory first, then swapped in
        only after conversion succeeds.
        """
        if mode not in VALID_MODES:
            raise ServiceError(f"Unbekannter Modus: {mode}")
        detail = max(1, min(int(detail), 3))
        meta = self.get(item_id)
        item_dir = self.root / item_id
        original, original_info = self.original_path(item_id)
        suffix = original.suffix.lower()
        with tempfile.TemporaryDirectory(prefix=f"gallery-render-{item_id}-") as tmp_raw:
            tmp = Path(tmp_raw)
            source = original
            if suffix == ".svg":
                # build_pages() treats SVGs as already-rendered pages, so place a
                # copy in the temp dir to make the later swap self-contained.
                source = tmp / "page-0001.svg"
                shutil.copy(original, source)
            pages, mode_used = build_pages(source, tmp, suffix, mode, detail)
            if meta.get("uploader") == "admin":
                updated = builders.rerender_asset(
                    meta, item_dir, tmp, pages, mode_used, detail, continuous
                )
            else:
                updated = builders.rerender_submission(
                    meta, item_dir, tmp, pages, mode_used, detail, continuous
                )
        updated["original"] = {**original_info, "size": original.stat().st_size}
        (item_dir / "meta.json").write_text(json.dumps(updated, indent=2))
        return updated

    # -- queries ---------------------------------------------------------------

    def list(self, *, include_archived: bool = True, uploader: str | None = None) -> list[dict]:
        metas = []
        for meta_file in self.root.glob("*/meta.json"):
            try:
                meta = json.loads(meta_file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            records.normalize(meta)
            records.attach_existing_original(meta, meta_file.parent)
            # Drafts (e.g. unsaved AI results) are never listed in the gallery.
            if meta.get("status") == "draft":
                continue
            if not include_archived and meta.get("status") == "archived":
                continue
            if uploader and meta.get("uploader") != uploader:
                continue
            metas.append(meta)
        return sorted(metas, key=lambda m: m.get("created", 0), reverse=True)

    def get(self, item_id: str) -> dict:
        meta_file = self.root / item_id / "meta.json"
        if not meta_file.exists():
            raise ServiceError(f"Einreichung nicht gefunden: {item_id}")
        meta = json.loads(meta_file.read_text())
        records.normalize(meta)
        records.attach_existing_original(meta, meta_file.parent)
        return meta

    def original_path(self, item_id: str) -> tuple[Path, dict]:
        meta = self.get(item_id)
        original = meta.get("original") or {}
        stored = original.get("stored")
        if not stored or "/" in stored or "\\" in stored:
            raise ServiceError(f"Originaldatei nicht gefunden: {item_id}")
        path = self.root / item_id / stored
        if not path.exists():
            raise ServiceError(f"Originaldatei nicht gefunden: {item_id}")
        info = dict(original)
        info["size"] = path.stat().st_size
        return path, info

    def gcode_path(self, item_id: str) -> Path:
        path = self.root / item_id / GCODE_FILE
        if not path.exists():
            raise ServiceError(f"Einreichung nicht gefunden: {item_id}")
        return path

    def gcode_preview_text(self, item_id: str, page: int = 1) -> str:
        """Stored submission G-code, or transient fitted G-code for admin assets."""
        path = self.root / item_id / GCODE_FILE
        if path.exists():
            return path.read_text(errors="replace")
        meta = self.get(item_id)
        entry = records.page_entry(meta, page)
        drawing = load_svg_drawing(self.root / item_id / entry["file"], quantization_mm=0.25)
        if drawing.is_empty():
            raise PlotterError("Die Seite enthält keine plottbaren Linien.")
        profile = ProfileService().active()
        active_meta = profile_meta(profile)
        cal = Calibration().merged(profile["calibration"])
        return profile_comment(active_meta) + fitted_gcode(
            drawing, cal, name=meta.get("filename") or item_id
        )

    def svg_preview(self, item_id: str, *, max_points: int = FULL_PREVIEW_POINTS) -> dict:
        return previews.svg_preview(self.root / item_id, item_id, max_points=max_points)

    def svg_thumbnail(self, item_id: str) -> dict:
        return self.svg_preview(item_id, max_points=THUMB_PREVIEW_POINTS)

    def preview(self, item_id: str, page: int = 1, *, max_points: int = DESIGNER_POINTS) -> dict:
        """On-demand downsampled preview of one page, for any item type.

        Single-image submissions keep their ``image.svg`` cache; multi-page
        admin assets go through the shared :mod:`asset_pages` page cache.
        """
        meta = self.get(item_id)
        entry = records.page_entry(meta, page)
        if entry["file"] == SVG_FILE:
            return self.svg_preview(item_id, max_points=max_points)
        return preview_for(self.root / item_id, entry["file"], page, max_points)

    def thumbnail(self, item_id: str) -> dict:
        """Page-1 grid thumbnail for any item type."""
        meta = self.get(item_id)
        entry = records.page_entry(meta, 1)
        if entry["file"] == SVG_FILE:
            return self.svg_thumbnail(item_id)
        return thumbnail_for(self.root / item_id, entry["file"])

    def svg_thumbnails(self) -> dict:
        """All grid thumbnails in one shot (disk-cached), so the gallery loads
        with a single request instead of one round-trip per card."""
        out: dict[str, dict] = {}
        for meta in self.list(include_archived=True):
            try:
                out[meta["id"]] = self.thumbnail(meta["id"])
            except (ServiceError, OSError):
                pass
        return out

    # -- mutation ----------------------------------------------------------------

    def set_status(self, item_id: str, status: str) -> dict:
        if status not in ("active", "archived"):
            raise ServiceError(f"Unbekannter Status: {status}")
        return self._update_meta(item_id, status=status)

    def set_title(self, item_id: str, title: str) -> dict:
        return self._update_meta(item_id, title=title.strip()[:MAX_TITLE_LEN])

    def _update_meta(self, item_id: str, **fields) -> dict:
        meta = self.get(item_id)
        meta.update(fields)
        (self.root / item_id / "meta.json").write_text(json.dumps(meta, indent=2))
        return meta

    def delete(self, item_id: str) -> None:
        shutil.rmtree(self.root / item_id, ignore_errors=True)
