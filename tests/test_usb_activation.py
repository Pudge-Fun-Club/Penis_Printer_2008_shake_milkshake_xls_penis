from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from test_printer_manager import FakeBackend
from test_serial_backend import FakeTransport, _wait_until

from plotter.printer import discovery, factory
from plotter.printer.manager import OCTOPRINT, PrinterManager, save_active
from plotter.printer.serial import reset_worker
from plotter.printer.serial import worker as serial_worker
from plotter.services.settings_store import load_saved, patch_saved
from plotter.web.app import create_app


@pytest.fixture
def usb(workspace, monkeypatch):
    for key in (
        "PRINTER_SERIAL_ENABLED",
        "PRINTER_USE_SERIAL",
        "PRINTER_SERIAL_PORT",
        "PRINTER_SERIAL_BAUD",
        "PRINTER_DEFAULT_BACKEND",
        "OCTOPRINT_URL",
        "OCTOPRINT_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_worker()
    opened = []
    board = FakeTransport()

    def connect(port, baud):
        opened.append((port, baud))
        return board

    monkeypatch.setattr(serial_worker, "default_transport", connect)
    monkeypatch.setattr(discovery, "resolve_auto_port", lambda: "/dev/serial/by-id/ender")
    yield TestClient(create_app()), opened, board
    reset_worker()


def test_default_install_enables_usb_on_selection_without_restart(usb):
    client, opened, board = usb
    assert client.get("/api/printer/backends").status_code == 200
    assert opened == []  # Listing devices must not reset the board.
    response = client.post("/api/printer/backend", json={"id": "serial"})
    assert response.status_code == 200
    assert response.json()["active"] == "serial"
    deadline = time.monotonic() + 2
    while (
        not client.get("/api/printer/status").json().get("online") and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert client.get("/api/printer/status").json()["online"] is True
    assert opened == [("/dev/serial/by-id/ender", 115200)]
    assert all(cmd in ("G21", "G90", "M105") for cmd in board.sent)
    saved = load_saved()
    assert saved["printer.serial_enabled"] is True
    assert saved["printer.default_backend"] == "serial"
    assert saved["printer.serial_port"] == "auto"
    assert client.post("/api/printer/backend", json={"id": "serial"}).status_code == 200
    assert opened == [("/dev/serial/by-id/ender", 115200)]  # no second USB reset
    reset_worker()
    factory.reset_manager()
    assert client.get("/api/printer/status").json()["backend"] == "serial"


def test_saved_usb_settings_are_used_by_normal_startup(usb, monkeypatch):
    client, opened, _ = usb
    monkeypatch.setenv("PRINTER_SERIAL_ENABLED", "false")
    monkeypatch.setenv("PRINTER_SERIAL_PORT", "/dev/wrong")
    patch_saved(
        {
            "printer.serial_enabled": True,
            "printer.serial_port": "/dev/ttyUSB9",
            "printer.serial_baud": 57600,
            "printer.default_backend": "serial",
        }
    )
    assert client.get("/api/printer/status").json()["backend"] == "serial"
    assert _wait_until(lambda: opened == [("/dev/ttyUSB9", 57600)])


def test_usb_activation_cannot_interrupt_another_print(usb, monkeypatch):
    client, opened, _ = usb
    manager = PrinterManager({OCTOPRINT: FakeBackend(job_state="Printing")}, OCTOPRINT)
    monkeypatch.setattr(factory, "_manager", manager)
    response = client.post("/api/printer/backend", json={"id": "serial"})
    assert response.status_code == 409
    assert manager.active_id == "octoprint"
    assert opened == []
    assert not load_saved().get("printer.serial_enabled")


def test_existing_inactive_usb_connection_uses_auto_on_activation(usb, monkeypatch):
    client, opened, _ = usb
    monkeypatch.setenv("PRINTER_SERIAL_ENABLED", "true")
    save_active("octoprint")
    assert client.get("/api/printer/status").json()["backend"] == "octoprint"
    response = client.post("/api/printer/backend", json={"id": "serial"})
    assert response.status_code == 200
    assert _wait_until(lambda: bool(opened))
    assert opened == [("/dev/serial/by-id/ender", 115200)]
