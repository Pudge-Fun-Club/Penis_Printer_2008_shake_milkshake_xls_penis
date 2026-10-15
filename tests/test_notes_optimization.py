from __future__ import annotations

import json
import math
import re
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiLineString

from plotter.gcode.metrics import analyze_gcode
from plotter.gcode.preview import parse_gcode
from plotter.notes.optimize import optimize_strokes
from plotter.notes.print_plan import compact_gcode
from plotter.web.app import create_app


@pytest.fixture
def client(workspace, cal):
    return TestClient(create_app())


def stored_page(workspace, lines):
    asset = "a" * 24
    folder = workspace / "notes" / asset
    folder.mkdir(parents=True)
    (folder / "page.json").write_text(
        json.dumps(
            {
                "id": asset,
                "width": 160,
                "height": 160,
                "trace_version": 3,
                "polylines": lines,
            }
        )
    )
    return {"id": asset, "margin": 0}


def travel(lines):
    return sum(math.dist(a[-1], b[0]) for a, b in zip(lines, lines[1:], strict=False))


def test_connected_ink_becomes_single_strokes_without_bridges(client, workspace):
    original = [
        [(10, 10), (20, 10)],
        [(20, 10), (20, 20)],
        [(20, 20), (10, 20)],
        [(10, 20), (10, 10)],
        [(50, 10), (50, 20)],
        [(50, 20), (45, 25)],
        [(50, 20), (55, 25)],
        [(90, 90), (90.1, 90)],  # separate decimal dot
    ]
    payload = stored_page(workspace, original)
    response = client.post("/api/notes/vector-preview", json=payload)
    assert response.status_code == 200
    sheet = response.json()["pages"][0]
    result = sheet["polylines"]
    assert len(result) == 3
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) <= 0.021
    assert any(line == [[90, 90], [90.1, 90]] or line == [[90.1, 90], [90, 90]] for line in result)
    svg = ET.fromstring(sheet["svg"])
    assert len(svg.findall(".//{http://www.w3.org/2000/svg}path")) == 3


def test_svg_and_gcode_follow_short_route_instead_of_capture_order(client, workspace):
    payload = stored_page(
        workspace,
        [
            [(120, 20), (120, 10)],
            [(10, 10), (10, 20)],
            [(80, 20), (80, 10)],
            [(40, 10), (40, 20)],
        ],
    )
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
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) <= 0.021


def test_optimization_reports_lifts_and_travel_savings(client, workspace):
    payload = stored_page(
        workspace,
        [
            [(120, 20), (120, 10)],
            [(10, 10), (10, 20)],
            [(80, 20), (80, 10)],
            [(40, 10), (40, 20)],
        ],
    )
    sheet = client.post("/api/notes/vector-preview", json=payload).json()["pages"][0]
    stats = sheet["optimization"]
    assert stats["beforeStrokes"] == 4
    assert stats["afterStrokes"] == 4
    assert stats["beforeTravelMm"] == 220
    assert stats["afterTravelMm"] < 115


def test_retraces_use_shortest_physical_distance_instead_of_edge_count(cal):
    cal.pen_up_z, cal.pen_down_z, cal.z_feed = 20, 0, 60
    original = [
        [(20, 20), (120, 20)],
        [(20, 20), (20, 30)],
        [(20, 20), (15, 20)],
    ]
    result, _ = optimize_strokes(original, cal)
    assert len(result) == 1
    length = sum(math.dist(a, b) for line in result for a, b in zip(line, line[1:], strict=False))
    # 115mm original ink + the shortest 5mm branch retraced once.
    assert length == pytest.approx(120, abs=0.01)
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) < 0.021


def test_each_component_gets_its_own_lift_vs_retrace_decision(cal):
    cal.pen_up_z, cal.pen_down_z = 2, 1
    cal.draw_feed, cal.travel_feed, cal.z_feed = 60, 6000, 600
    original = [
        [(20, 20), (120, 20)],
        [(20, 20), (20, 30)],
        [(20, 20), (15, 20)],
        [(20, 70), (30, 70)],
        [(30, 70), (40, 70)],
        [(40, 70), (50, 70)],
    ]
    result, _ = optimize_strokes(original, cal)
    # Retracing 5mm is expensive at 1mm/s; the separate straight chain joins
    # without retracing. A whole-page yes/no decision cannot choose both.
    assert len(result) == 4
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) < 0.021


def test_closed_contour_starts_at_near_side_without_distorting_it(cal):
    original = [[(100, 100), (10, 100), (10, 10), (100, 10), (100, 100)]]
    result, _ = optimize_strokes(original, cal)
    assert math.dist((0, 0), result[0][0]) < 15
    assert result[0][0] == result[0][-1]
    assert MultiLineString(original).equals(MultiLineString(result))


def test_preview_shows_metrics_from_the_actual_printed_gcode(client, workspace, cal):
    cal.draw_feed = 1200
    cal.save()
    options = stored_page(workspace, [[(10, 10), (20, 10), (20, 20)]])
    result = client.post("/api/notes/vector-jobs", json=options).json()
    text = (workspace / "jobs" / result["jobs"][0]["filename"]).read_text()
    metrics = analyze_gcode(text)
    stats = result["pages"][0]["plotStats"]
    assert stats["estimatedSeconds"] == metrics.duration_s
    assert stats["penLifts"] == metrics.pen_lifts
    assert stats["drawMm"] == metrics.draw_mm
    assert stats["travelMm"] == metrics.travel_mm
    assert stats["penLiftMm"] == pytest.approx(6)
    # Feed is modal: a continuous stroke doesn't need F on every tiny move.
    draws = [line for line in text.splitlines() if line.startswith("G1 X")]
    assert len(draws) >= 2
    assert draws[0].endswith("F1200")
    assert " F" not in draws[1]


def test_modal_feed_compaction_keeps_z_travel_and_draw_speeds():
    original = (
        "G21\nG90\nG0 Z7.4 F300\nG0 X30 Y30 F2400\nG1 Z1.4 F300\n"
        "G1 X31 Y30 F1200\nG1 X32 Y30 F1200\nG0 Z7.4 F300\n"
        "G0 X40 Y30 F2400\nG1 Z1.4 F300\nG1 X41 Y30 F1200\nM2\n"
    )
    compact = compact_gcode(original)
    feeds = []
    feed = None
    for line in compact.splitlines():
        if not line.startswith(("G0 ", "G1 ")):
            continue
        match = re.search(r" F([\d.]+)", line)
        if match:
            feed = float(match.group(1))
        feeds.append(feed)
    assert feeds == [300, 2400, 300, 1200, 1200, 300, 2400, 300, 1200]
    assert len(compact) < len(original)


def test_large_junction_uses_bounded_weighted_fallback_without_losing_ink(cal):
    cal.pen_up_z, cal.pen_down_z, cal.z_feed = 20, 0, 60
    original = [
        [(80, 80), (80 + 30 * math.cos(i * math.tau / 42), 80 + 30 * math.sin(i * math.tau / 42))]
        for i in range(42)
    ]
    result, _ = optimize_strokes(original, cal)
    assert len(result) == 1
    assert MultiLineString(original).hausdorff_distance(MultiLineString(result)) < 0.021
    repeated, _ = optimize_strokes(original, cal)
    assert repeated == result
