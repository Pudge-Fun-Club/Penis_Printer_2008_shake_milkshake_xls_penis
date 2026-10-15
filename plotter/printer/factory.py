from __future__ import annotations

import os
import threading

from .base import PrinterBackend
from .manager import (
    OCTOPRINT,
    SERIAL,
    PrinterManager,
    load_active,
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def use_serial() -> bool:
    """Back-compat flag: whether serial is involved at all (enabled or default)."""
    return serial_enabled()


def serial_enabled() -> bool:
    return _printer_settings().serial_enabled


def _printer_settings():
    from plotter.core.config import load_settings
    from plotter.services.settings_store import load_saved

    return load_settings(saved=load_saved()).printer


def octoprint_configured() -> bool:
    return bool(os.environ.get("OCTOPRINT_URL") and os.environ.get("OCTOPRINT_API_KEY"))


_manager_lock = threading.Lock()
_manager: PrinterManager | None = None


def get_printer_client() -> PrinterBackend:
    """Return the process-wide :class:`PrinterManager` (holds all backends)."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = _build_manager()
        return _manager


def reset_manager() -> None:
    """Drop the cached manager (used by tests after changing the environment)."""
    global _manager
    with _manager_lock:
        _manager = None


def _build_manager() -> PrinterManager:
    from .octoprint import OctoPrintClient

    # OctoPrint is always present (it self-reports configured=false when its env
    # is unset), so the legacy single-backend behaviour is preserved. Serial is
    # only added when explicitly enabled.
    backends: dict[str, PrinterBackend] = {OCTOPRINT: OctoPrintClient()}
    settings = _printer_settings()
    if settings.serial_enabled:
        from .serial import SerialClient

        backends[SERIAL] = SerialClient(port=settings.serial_port, baud=settings.serial_baud)
    return PrinterManager(backends, _resolve_initial_active(backends))


def activate_serial(manager: PrinterManager) -> None:
    """Enable USB explicitly from the UI, including on a default installation."""
    from plotter.core.config import load_settings_with_sources
    from plotter.printer.serial import SerialClient
    from plotter.services.settings_store import load_saved, patch_saved

    settings, sources = load_settings_with_sources(saved=load_saved())
    cfg = settings.printer
    port = "auto" if sources["printer"]["serial_port"] == "default" else cfg.serial_port
    updates = {"printer.serial_enabled": True, "printer.default_backend": SERIAL}
    if manager.active_id != SERIAL:
        # An inactive client may still carry the old default ttyUSB0 config.
        # Replace it before connecting so the effective selection takes effect.
        manager.register_backend(SERIAL, SerialClient(port=port, baud=cfg.serial_baud))
        manager.set_active(SERIAL)
        updates["printer.serial_port"] = port
        updates["printer.serial_baud"] = cfg.serial_baud
    patch_saved(updates)


def _resolve_initial_active(backends: dict[str, PrinterBackend]) -> str:
    # Priority: persisted choice -> env default -> back-compat -> first available.
    saved = load_active()
    if saved in backends:
        return saved
    preferred = _printer_settings().default_backend
    if preferred in backends:
        return preferred
    if _truthy(os.environ.get("PRINTER_USE_SERIAL")) and SERIAL in backends:
        return SERIAL
    if SERIAL in backends and not octoprint_configured():
        return SERIAL
    for pref in (OCTOPRINT, SERIAL):
        if pref in backends:
            return pref
    # No backend configured at all — the manager reports unconfigured.
    return OCTOPRINT
