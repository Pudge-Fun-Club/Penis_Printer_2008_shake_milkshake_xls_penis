from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from plotter.core.calibration import Calibration
from plotter.core.position import get_tracker
from plotter.services.printer import PrinterController
from plotter.services.profiles import ProfileService
from plotter.web.app import create_app
from plotter.web.routes import notes, printer


class Machine:
    configured = True

    def __init__(self):
        self.state = "Operational"
        self.commands = []
        self.uploaded = []

    def status(self):
        return {"online": True, "job": {"state": self.state}}

    def gcode(self, commands):
        self.commands.extend(commands)

    def upload(self, path, *, start=False):
        self.uploaded.append(path)
        return {"done": True}


@pytest.fixture
def setup(workspace, cal, monkeypatch):
    cal.pen_calibrated = True
    cal.save()
    machine = Machine()
    tracker = get_tracker()
    tracker.home(None)
    ctrl = PrinterController(machine, tracker)
    monkeypatch.setattr(notes, "printer_controller", lambda: ctrl, raising=False)
    monkeypatch.setattr(printer, "controller", lambda: ctrl)
    return TestClient(create_app()), machine


def next_sheet(client, thickness=0.1, stack=None):
    stack = stack or client.get("/api/notes/status").json()["paperStack"]
    return client.post(
        "/api/notes/next-sheet",
        json={
            "thickness_mm": thickness,
            "profile_id": stack["profileId"],
            "fingerprint": stack["fingerprint"],
        },
    )


def test_removed_sheets_lower_both_heights_and_persist_without_moving(setup):
    client, machine = setup
    first = next_sheet(client, 0.12)
    assert first.status_code == 200
    stack = first.json()["paperStack"]
    assert stack["penDownZ"] == 1.28
    assert stack["penUpZ"] == 7.28
    assert stack["thicknessMm"] == 0.12
    second = next_sheet(client, 0.12)
    assert second.status_code == 200
    assert second.json()["paperStack"]["penDownZ"] == 1.16
    assert second.json()["paperStack"]["penUpZ"] == 7.16
    assert Calibration.load().pen_down_z == 1.16
    assert Calibration.load().paper_thickness_mm == 0.12
    assert ProfileService().active()["calibration"]["pen_up_z"] == 7.16
    assert client.get("/api/notes/status").json()["paperStack"] == second.json()["paperStack"]
    assert not machine.commands
    assert not machine.uploaded


def test_duplicate_or_stale_sheet_confirmation_does_not_lower_twice(setup):
    client, _ = setup
    old = client.get("/api/notes/status").json()["paperStack"]
    assert next_sheet(client, stack=old).status_code == 200
    assert next_sheet(client, stack=old).status_code == 409
    assert Calibration.load().pen_down_z == 1.3


def test_profile_switch_rejects_confirmation_for_previous_stack(setup):
    client, _ = setup
    old = client.get("/api/notes/status").json()["paperStack"]
    profiles = ProfileService()
    other = profiles.create("Other stack")
    profiles.activate(other["id"])
    assert next_sheet(client, stack=old).status_code == 409
    assert Calibration.load().pen_down_z == 1.4


def test_concurrent_confirmations_apply_only_one_sheet_offset(setup):
    client, _ = setup
    old = client.get("/api/notes/status").json()["paperStack"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: next_sheet(client, stack=old), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert Calibration.load().pen_down_z == 1.3


@pytest.mark.parametrize("state", ["Printing", "Paused", "Pausing", "Resuming", "Cancelling"])
def test_cannot_adjust_stack_during_active_job(setup, state):
    client, machine = setup
    machine.state = state
    assert next_sheet(client).status_code == 409
    assert Calibration.load().pen_down_z == 1.4
    assert not machine.commands


@pytest.mark.parametrize("thickness", [0, -0.1, 1.1, "NaN", "Infinity"])
def test_invalid_sheet_thickness_leaves_calibration_intact(setup, thickness):
    client, machine = setup
    assert next_sheet(client, thickness).status_code == 422
    assert Calibration.load().pen_down_z == 1.4
    assert not machine.commands


@pytest.mark.parametrize(
    "updates",
    [
        {"pen_calibrated": False},
        {"pen_down_z": 0.05},
        {"pen_up_z": 1.0},
    ],
)
def test_uncalibrated_or_out_of_bounds_stack_is_not_changed(setup, updates):
    client, machine = setup
    before = Calibration.load().merged(updates)
    before.save()
    assert next_sheet(client).status_code == 409
    assert Calibration.load() == before
    assert not machine.commands


def test_next_sheet_regenerates_gcode_and_invalidates_previous_job(setup, workspace):
    client, machine = setup
    old = client.post("/api/notes/jobs", json={"text": "Лист"}).json()["jobs"][0]["filename"]
    assert next_sheet(client, 0.12).status_code == 200
    blocked = client.post("/api/printer/send", json={"filename": old, "start": True})
    assert blocked.status_code == 409
    assert not machine.uploaded
    new = client.post("/api/notes/jobs", json={"text": "Лист"}).json()["jobs"][0]["filename"]
    gcode = (workspace / "jobs" / new).read_text()
    assert "Z1.280" in gcode
    assert "Z7.280" in gcode
    assert not machine.commands
