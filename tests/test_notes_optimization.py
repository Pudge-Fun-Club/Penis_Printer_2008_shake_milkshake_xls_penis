from __future__ import annotations

import json
import math
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiLineString

from plotter.gcode.preview import parse_gcode
from plotter.web.app import create_app


@pytest.fixture
def client(workspace, cal):
    return TestClient(create_app())


def stored_page(workspace, lines):
    asset = "a" * 24
    folder = workspace / "notes" / asset
    folder.mkdir(parents=True)
    (folder / "page.json").write_text(json.dumps({
        "id": asset, "width": 160, "height": 160, "trace_version": 3, "polylines": lines,
    }))
    return {"id": asset, "margin": 0}


def travel(lines):
    return sum(math.dist(a[-1], b[0]) for a, b in zip(lines, lines[1:], strict=False))


def test_connected_ink_becomes_single_strokes_without_bridges(client, workspace):
    original = [
        [(10, 10), (20, 10)], [(20, 10), (20, 20)],
        [(20, 20), (10, 20)], [(10, 20), (10, 10)],
        [(50, 10), (50, 20)], [(50, 20), (45, 25)], [(50, 20), (55, 25)],
        [(90, 90), (90.1, 90)],  # separate decimal dot
    ]
    payload = stored_page(workspace, original)
    response = client.post("/api/notes/vector-preview", json=payload)
    assert response.status_code == 200
    sheet = response.json()["pages"][0]
    result = sheet["polylines"]
    assert len(result) == 3
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) <= .021
    assert any(line == [[90, 90], [90.1, 90]] or line == [[90.1, 90], [90, 90]]
               for line in result)
    svg = ET.fromstring(sheet["svg"])
    assert len(svg.findall(".//{http://www.w3.org/2000/svg}path")) == 3


def test_svg_and_gcode_follow_short_route_instead_of_capture_order(client, workspace):
    payload = stored_page(workspace, [
        [(120, 20), (120, 10)], [(10, 10), (10, 20)],
        [(80, 20), (80, 10)], [(40, 10), (40, 20)],
    ])
    before = client.post("/api/notes/vector-preview", json=payload).json()["pages"][0]
    assert travel(before["polylines"]) < 115
    response = client.post("/api/notes/vector-jobs", json=payload)
    assert response.status_code == 200
    result = response.json()
    sheet = result["pages"][0]
    assert sheet == before
    printed = parse_gcode(workspace / "jobs" / result["jobs"][0]["filename"])
    assert len(printed["polylines"]) == 4
    assert travel(printed["polylines"]) < 115
    # The printer-space Y flip must preserve the reviewed SVG stroke order.
    svg_order = [line[0][0] for line in sheet["polylines"]]
    assert [line[0][0] - 25 for line in printed["polylines"]] == svg_order


def test_redundant_vertices_removed_but_tiny_closed_mark_survives(client, workspace):
    original = [
        [(x, 50) for x in range(10, 101)],
        [(130, 100), (130.1, 100), (130.05, 100.1), (130, 100)],
    ]
    response = client.post("/api/notes/vector-preview", json=stored_page(workspace, original))
    assert response.status_code == 200
    result = response.json()["pages"][0]["polylines"]
    assert len(result) == 2
    assert sum(len(line) for line in result) <= 8
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) <= .021


def test_optimization_reports_lifts_and_travel_savings(client, workspace):
    payload = stored_page(workspace, [
        [(120, 20), (120, 10)], [(10, 10), (10, 20)],
        [(80, 20), (80, 10)], [(40, 10), (40, 20)],
    ])
    sheet = client.post("/api/notes/vector-preview", json=payload).json()["pages"][0]
    stats = sheet["optimization"]
    assert stats["beforeStrokes"] == 4
    assert stats["afterStrokes"] == 4
    assert stats["beforeTravelMm"] == 220
    assert stats["afterTravelMm"] < 115
