from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from plotter.core.position import get_tracker
from plotter.services.printer import PrinterController
from plotter.web.app import create_app
from plotter.web.routes import printer


class Machine:
    """External USB boundary; record actual commands and uploaded file content."""

    configured = True

    def __init__(self):
        self.commands = []
        self.uploaded = []
        self.busy = False
        self.online = True
        self.loaded = None

    def status(self):
        job = {"state": "Printing"} if self.busy else None
        if self.loaded:
            job = {"state": "Operational", "job": {"file": {"name": self.loaded}}}
        return {"configured": True, "online": self.online, "backend": "serial", "job": job}

    def home(self, axes=None):
        self.commands.append("G28")

    def gcode(self, commands):
        self.commands.extend(commands)

    def upload(self, path: Path, *, start=False):
        self.uploaded.append((path.read_text(), start))
        return {"done": True}

    def job_command(self, command):
        self.commands.append(command)


@pytest.fixture
def setup(workspace, cal, monkeypatch):
    cal.pen_calibrated = True
    cal.save()
    tracker = get_tracker()
    tracker.home(None)
    machine = Machine()
    monkeypatch.setattr(printer, "controller", lambda: PrinterController(machine, tracker))
    client = TestClient(create_app())
    return client, machine, cal, tracker


def job(client):
    r = client.post("/api/notes/jobs", json={"text": "Проверка письма"})
    assert r.status_code == 200
    return r.json()["jobs"][0]["filename"]


def test_notes_start_does_not_home_with_installed_pen(setup):
    client, machine, _, _ = setup
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 200
    assert "G28" not in machine.commands
    assert machine.uploaded[0][1] is True
    assert {"M104 S0", "M140 S0"}.issubset(machine.commands)


def test_notes_refuse_uncalibrated_pen(setup):
    client, machine, cal, _ = setup
    cal.pen_calibrated = False
    cal.save()
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded
    assert not machine.commands


def test_notes_refuse_unknown_position(setup):
    client, machine, _, tracker = setup
    tracker.invalidate()
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded


def test_notes_refuse_uncalibrated_paper(setup):
    client, machine, cal, _ = setup
    cal.paper_corners = {}
    cal.save()
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded


def test_notes_do_not_replace_active_print(setup):
    client, machine, _, _ = setup
    machine.busy = True
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded
    assert not machine.commands


def test_notes_require_online_printer(setup):
    client, machine, _, _ = setup
    machine.online = False
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded


def test_notes_reject_changed_profile(setup):
    client, machine, cal, _ = setup
    filename = job(client)
    cal.pen_down_z += 1
    cal.save()
    r = client.post("/api/printer/send", json={"filename": filename, "start": True})
    assert r.status_code == 409
    assert not machine.uploaded


def test_loaded_notes_start_uses_same_calibration_guard(setup):
    client, machine, _, _ = setup
    machine.loaded = job(client)
    r = client.post("/api/printer/job", json={"command": "start"})
    assert r.status_code == 200
    assert "G28" not in machine.commands
    assert machine.uploaded


def test_captured_paper_must_contain_actual_plot_area(setup):
    client, machine, cal, _ = setup
    cal.paper_corners = {"bl": [20, 30], "tr": [40, 50]}
    cal.save()
    r = client.post("/api/printer/send", json={"filename": job(client), "start": True})
    assert r.status_code == 409
    assert not machine.uploaded
    assert not machine.commands


def test_first_travel_checked_from_current_head_not_zero(setup, workspace):
    from plotter.gcode.scene import save_scene_job

    client, machine, cal, tracker = setup
    cal.obstacles = [{"id": "clip", "x": 98, "y": 178, "w": 5, "h": 20}]
    cal.save()
    tracker.set_axes(x=150, y=190, z=cal.pen_up_z)
    path = save_scene_job(
        {
            "name": "first-travel",
            "continuous": False,
            "objects": [{"cachedPolylines": [[[5, 9], [6, 10]]]}],
        },
        cal,
        source_kind="notebook",
    )
    r = client.post("/api/printer/send", json={"filename": path.name, "start": True})
    assert r.status_code == 422
    assert not machine.uploaded
    assert not machine.commands
