"""Reading and backfilling gallery item metadata records (meta.json)."""

from __future__ import annotations

from pathlib import Path

from plotter.services.errors import ServiceError
from plotter.services.gallery.common import SVG_FILE, original_meta


def normalize(meta: dict) -> None:
    """Backfill fields added after an item was written (items uploaded before
    the uploader tag existed came from the public /upload page; items from
    before the unified asset model lack ``pages``/``mode``/``detail``)."""
    meta.setdefault("uploader", "public")
    if "pages" not in meta:
        meta["pages"] = [{
            "n": 1, "file": SVG_FILE,
            "width": meta.get("width"), "height": meta.get("height"),
            "lines": meta.get("lines"),
        }]
    meta.setdefault("mode", "vector" if meta.get("kind") == "svg" else "trace")
    meta.setdefault("detail", 2)
    meta.setdefault("continuous", True)
    meta.setdefault("original", legacy_original_meta(meta))


def attach_existing_original(meta: dict, item_dir: Path) -> None:
    original = meta.get("original")
    stored = (original or {}).get("stored")
    if stored and "/" not in stored and "\\" not in stored:
        path = item_dir / stored
        if path.exists():
            original["size"] = path.stat().st_size
            meta["original"] = original
            return
    meta["original"] = None


def legacy_original_meta(meta: dict) -> dict | None:
    kind = meta.get("kind")
    filename = meta.get("filename") or "original"
    if not kind:
        return None
    stored = f"original.{kind if kind != 'jpeg' else 'jpg'}"
    return original_meta(filename, stored, kind, 0)


def page_entry(meta: dict, page: int) -> dict:
    for p in meta.get("pages", []):
        if p["n"] == page:
            return p
    raise ServiceError(f"Seite {page} in Galerie-Eintrag {meta['id']} nicht gefunden")
