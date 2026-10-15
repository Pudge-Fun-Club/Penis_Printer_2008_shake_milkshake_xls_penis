from __future__ import annotations

import time

import pytest
from test_serial_backend import FakeTransport, _wait_until

from plotter.core.position import get_tracker
from plotter.printer.base import PrinterError
from plotter.printer.serial import SerialWorker
from plotter.printer.serial import worker as worker_module


@pytest.fixture(autouse=True)
def fast_serial(workspace, monkeypatch):
    monkeypatch.setattr(worker_module, "RECONNECT_DELAY", 0.03)
    monkeypatch.setattr(worker_module, "HEARTBEAT_INTERVAL", 0.05, raising=False)
    monkeypatch.setattr(worker_module, "HEARTBEAT_TIMEOUT", 0.1, raising=False)
    monkeypatch.setattr(worker_module, "ACK_TIMEOUT", 0.15)


class DisconnectableTransport(FakeTransport):
    connected = True

    def write(self, data):
        if not self.connected:
            raise OSError("USB device disconnected")
        return super().write(data)

    def readline(self):
        if not self.connected:
            raise OSError("USB device disconnected")
        return super().readline()


def test_idle_disconnect_is_detected_and_new_usb_device_reconnects():
    first = DisconnectableTransport()
    replacement = FakeTransport()
    available = [first]

    def factory(port, baud):
        if available[0] is None:
            raise OSError("USB device missing")
        return available[0]

    worker = SerialWorker("/dev/serial/by-id/printer", transport_factory=factory)
    try:
        assert _wait_until(lambda: worker.status().get("online"))
        get_tracker().home(None)
        available[0] = None
        first.connected = False
        assert _wait_until(lambda: not worker.status().get("online"), timeout=0.8)
        assert get_tracker().homed is False
        available[0] = replacement
        assert _wait_until(lambda: worker.status().get("online"))
        assert worker.status().get("error") is None
        assert worker.status()["job"] is None
        assert get_tracker().homed is False
        assert all(cmd in ("G21", "G90", "M105") for cmd in replacement.sent)
    finally:
        worker.shutdown()


def test_silent_idle_printer_is_reopened_without_manual_command():
    silent = FakeTransport(responder=lambda cmd: [] if cmd == "M105" else [b"ok\n"])
    healthy = FakeTransport()
    opened = []

    def factory(port, baud):
        transport = silent if not opened else healthy
        opened.append(transport)
        return transport

    worker = SerialWorker("fake", transport_factory=factory)
    try:
        assert _wait_until(lambda: worker.status().get("online"))
        assert _wait_until(lambda: len(opened) >= 2, timeout=0.8)
        assert _wait_until(lambda: worker.status().get("online"))
        assert silent.is_open is False
        assert worker.status()["job"] is None
    finally:
        worker.shutdown()


def test_command_ack_timeout_marks_offline_and_retries():
    transport = FakeTransport(responder=lambda cmd: [] if cmd == "M115" else [b"ok\n"])
    replacement = FakeTransport()
    retry_allowed = [False]
    attempts = []

    def factory(port, baud):
        attempts.append(time.monotonic())
        if len(attempts) == 1:
            return transport
        if not retry_allowed[0]:
            raise OSError("USB still unavailable")
        return replacement

    worker = SerialWorker("fake", transport_factory=factory)
    try:
        assert _wait_until(lambda: worker.status().get("online"))
        get_tracker().home(None)
        with pytest.raises(PrinterError, match="timeout"):
            worker.gcode(["M115"])
        assert _wait_until(lambda: not worker.status().get("online"), timeout=0.8)
        assert get_tracker().homed is False
        retry_allowed[0] = True
        assert _wait_until(lambda: worker.status().get("online"))
    finally:
        worker.shutdown()


def test_firmware_restart_aborts_old_job_before_next_move(workspace):
    reset_board = FakeTransport(
        responder=lambda cmd: [b"start\n", b"ok\n"] if cmd == "G1 X1" else [b"ok\n"]
    )
    restarted_board = FakeTransport()
    opened = []

    def factory(port, baud):
        transport = reset_board if not opened else restarted_board
        opened.append(transport)
        return transport

    worker = SerialWorker("fake", transport_factory=factory)
    try:
        assert _wait_until(lambda: worker.status().get("online"))
        get_tracker().home(None)
        job = workspace / "interrupted.gcode"
        job.write_text("G1 X1\nG1 X200\n")
        worker.upload(job, start=True)
        assert _wait_until(lambda: "G1 X1" in reset_board.sent)
        assert _wait_until(lambda: len(opened) >= 2, timeout=0.8)
        assert _wait_until(lambda: worker.status().get("online"))
        assert worker.status()["job"] is None
        assert get_tracker().homed is False
        assert "G1 X200" not in reset_board.sent + restarted_board.sent
        assert all(cmd in ("G21", "G90", "M105") for cmd in restarted_board.sent)
    finally:
        worker.shutdown()
