from __future__ import annotations

import io
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from plotter.core.jobmeta import read_job_meta
from plotter.gcode.safety import GcodeSafetyChecker
from plotter.web.app import create_app


@pytest.fixture
def client(workspace, cal):
    return TestClient(create_app())


def page_photo():
    image = Image.new("RGB", (400, 500), "white")
    pen = ImageDraw.Draw(image)
    # Letter A, fraction/formula, and a circle with arrow; no OCR involved.
    pen.line([(40, 100), (60, 50), (80, 100)], fill="black", width=4)
    pen.line([(48, 80), (72, 80)], fill="black", width=4)
    pen.line([(160, 65), (240, 65)], fill="black", width=4)
    pen.line([(200, 45), (200, 90)], fill="black", width=4)
    pen.ellipse((120, 200, 220, 300), outline="black", width=4)
    pen.line([(220, 250), (330, 250), (310, 235)], fill="black", width=4)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def upload(client):
    r = client.post("/api/notes/vectorize", files={"file": ("page.png", page_photo())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_photo_becomes_svg_without_ocr_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    asset = upload(client)
    r = client.post("/api/notes/vector-preview", json={"id": asset, "font": "original"})
    assert r.status_code == 200
    sheet = r.json()["pages"][0]
    svg = ET.fromstring(sheet["svg"])
    assert svg.findall(".//{http://www.w3.org/2000/svg}path")
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    # Diagram still has strokes in lower half, text/formula in upper half.
    ys = [y for line in sheet["polylines"] for _, y in line]
    assert min(ys) < sheet["height"] * 0.3
    assert max(ys) > sheet["height"] * 0.5


def test_vector_svg_and_print_job_use_same_geometry(client, workspace, cal):
    asset = upload(client)
    payload = {"id": asset, "font": "original"}
    preview = client.post("/api/notes/vector-preview", json=payload).json()
    r = client.post("/api/notes/vector-jobs", json=payload)
    assert r.status_code == 200
    result = r.json()
    assert result["pages"][0]["polylines"] == preview["pages"][0]["polylines"]
    path = workspace / "jobs" / result["jobs"][0]["filename"]
    GcodeSafetyChecker(cal).check(path.read_text())
    assert read_job_meta(path)["source"]["kind"] == "notebook"
    assert read_job_meta(path)["source"]["vector_id"] == asset


def test_empty_photo_does_not_create_print_job(client):
    out = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(out, format="PNG")
    r = client.post("/api/notes/vectorize", files={"file": ("empty.png", out.getvalue())})
    assert r.status_code == 422


def test_vector_id_cannot_escape_storage(client):
    r = client.post("/api/notes/vector-preview", json={"id": "../user_settings"})
    assert r.status_code == 422


def test_missing_vector_has_useful_error(client):
    r = client.post("/api/notes/vector-preview", json={"id": "a" * 24})
    assert r.status_code == 404


def test_large_diagram_is_not_mistaken_for_page_by_default(client, workspace):
    image = Image.new("RGB", (400, 500), "white")
    pen = ImageDraw.Draw(image)
    pen.line([(40, 50), (80, 50)], fill="black", width=4)
    pen.rectangle((30, 100, 370, 480), outline="black", width=4)
    out = io.BytesIO()
    image.save(out, format="PNG")
    r = client.post("/api/notes/vectorize", files={"file": ("table.png", out.getvalue())})
    assert r.status_code == 200
    stored = Image.open(workspace / "notes" / r.json()["id"] / "photo.png")
    assert stored.size == (400, 500)


def test_decimal_dot_survives_svg_and_gcode(client, workspace):
    from plotter.gcode.preview import parse_gcode

    image = Image.new("RGB", (300, 200), "white")
    pen = ImageDraw.Draw(image)
    pen.line([(20, 100), (100, 100)], fill="black", width=4)
    pen.ellipse((200, 100, 206, 106), fill="black")
    out = io.BytesIO()
    image.save(out, format="PNG")
    r = client.post("/api/notes/vectorize", files={"file": ("dot.png", out.getvalue())})
    assert r.status_code == 200
    options = {"id": r.json()["id"]}
    r = client.post("/api/notes/vector-preview", json=options)
    assert r.status_code == 200
    points = [p for line in r.json()["pages"][0]["polylines"] for p in line]
    assert any(103 <= x <= 110 and 75 <= y <= 85 for x, y in points)
    r = client.post("/api/notes/vector-jobs", json=options)
    assert r.status_code == 200
    path = workspace / "jobs" / r.json()["jobs"][0]["filename"]
    printed = [p for line in parse_gcode(path)["polylines"] for p in line]
    assert any(128 <= x <= 138 and 110 <= y <= 120 for x, y in printed)


def test_replacing_handwriting_keeps_diagram_geometry(client, monkeypatch, workspace):
    from plotter.notes import ocr

    asset = upload(client)
    monkeypatch.setattr(
        ocr,
        "text_regions",
        lambda data: [
            {"text": "А", "box": [80, 80, 225, 230]},
        ],
    )
    original = client.post("/api/notes/vector-preview", json={"id": asset}).json()["pages"][0]
    changed = client.post(
        "/api/notes/vector-preview", json={"id": asset, "font": "notes-slant"}
    ).json()["pages"][0]
    assert changed["polylines"] != original["polylines"]
    # Every diagram stroke (well outside the text region) is retained verbatim.
    diagram = [line for line in original["polylines"] if min(y for _, y in line) > 60]
    assert diagram
    assert all(line in changed["polylines"] for line in diagram)
