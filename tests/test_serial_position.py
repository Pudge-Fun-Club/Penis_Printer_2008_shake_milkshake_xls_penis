from __future__ import annotations

import time

import pytest
from test_serial_backend import FakeTransport

from plotter.core.position import get_tracker
from plotter.printer.manager import PrinterManager
from plotter.printer.serial import SerialClient, reset_worker
from plotter.services.printer import PrinterController


@pytest.fixture
def connected(workspace):
    reset_worker()
    transport = FakeTransport(
        responder=lambda cmd: (
            [b"X:110.00 Y:110.00 Z:10.00 E:0.00 Count X:8800 Y:8800 Z:4000\n", b"ok\n"]
            if cmd == "M114"
            else [b"ok\n"]
        )
    )
    client = SerialClient("fake", transport_factory=lambda p, b: transport)
    manager = PrinterManager({"serial": client}, "serial")
    deadline = time.monotonic() + 3
    while not manager.status().get("online") and time.monotonic() < deadline:
        time.sleep(0.01)
    assert manager.status().get("online")
    yield manager, transport
    reset_worker()


def test_neo_homing_tracks_reported_center_and_z(connected):
    manager, transport = connected
    position = PrinterController(manager, get_tracker()).home()
    assert position["homed"] is True
    assert (position["x"], position["y"], position["z"]) == (110, 110, 10)
    assert "M114" in transport.sent


def test_serial_reconnect_invalidates_saved_home(workspace):
    reset_worker()
    tracker = get_tracker()
    tracker.home(None)
    transport = FakeTransport()
    client = SerialClient("fake", transport_factory=lambda p, b: transport)
    manager = PrinterManager({"serial": client}, "serial")
    try:
        deadline = time.monotonic() + 3
        while not manager.status().get("online") and time.monotonic() < deadline:
            time.sleep(0.01)
        assert manager.status().get("online")
        assert tracker.homed is False
    finally:
        reset_worker()


def test_completed_job_synchronizes_shared_position(connected, workspace):
    manager, transport = connected
    tracker = get_tracker()
    tracker.home(None)
    tracker.set_axes(x=20, y=20, z=20)
    job = workspace / "complete.gcode"
    job.write_text("G90\nG1 X110 Y110 Z10\n")
    manager.upload(job, start=True)
    deadline = time.monotonic() + 3
    while manager.status().get("job") and time.monotonic() < deadline:
        time.sleep(0.01)
    assert tracker.snapshot()["z"] == 10
    assert tracker.snapshot()["x"] == 110
    assert "M400" in transport.sent


def test_busy_job_cannot_be_replaced_atomically(connected, workspace):
    from plotter.printer.base import PrinterError

    manager, transport = connected
    # No G1 ACK: the first job remains active during the second upload.
    transport._responder = lambda cmd: [] if cmd.startswith("G1") else [b"ok\n"]
    first = workspace / "first.gcode"
    first.write_text("G1 X10\n")
    second = workspace / "second.gcode"
    second.write_text("G1 X200\n")
    manager.upload(first, start=True)
    with pytest.raises(PrinterError, match="already"):
        manager.upload(second, start=True)
    assert manager.status()["job"]["job"]["file"]["name"] == "first.gcode"
