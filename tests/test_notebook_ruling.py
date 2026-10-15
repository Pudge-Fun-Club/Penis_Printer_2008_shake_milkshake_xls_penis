from __future__ import annotations

import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from plotter.notes.ruling import remove_ruling
from plotter.web.app import create_app


@pytest.fixture
def client(workspace, cal):
    return TestClient(create_app())


def notebook(grid: str, ink: str | None = None) -> bytes:
    image = Image.new("RGB", (400, 400), "white")
    pen = ImageDraw.Draw(image)
    for p in range(20, 400, 40):
        pen.line([(p, 0), (p, 399)], fill=grid, width=2)
        pen.line([(0, p), (399, p)], fill=grid, width=2)
    if ink:
        # A letter's vertical stroke lies exactly on a grid line, with other
        # grid lines crossing it. Erasing entire line bands would delete it.
        pen.line([(100, 60), (100, 140)], fill=ink, width=4)
        pen.rectangle((220, 130, 330, 250), outline=ink, width=4)
        # Keep a genuine underline and a decimal dot as well as the drawing.
        pen.line([(40, 310), (350, 310)], fill=ink, width=3)
        pen.ellipse((180, 200, 186, 206), fill=ink)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@pytest.mark.parametrize("grid", ["#c8e3ff", "#d0d0d0"])
def test_notebook_grid_alone_does_not_become_plot_strokes(client, grid):
    response = client.post("/api/notes/vectorize", files={"file": ("grid.png", notebook(grid))})
    assert response.status_code == 422


@pytest.mark.parametrize("grid", ["#c8e3ff", "#d0d0d0"])
@pytest.mark.parametrize("ink", ["black", "#0000ff"])
def test_ruling_removed_without_erasing_ink_at_crossings(client, grid, ink):
    response = client.post(
        "/api/notes/vectorize", files={"file": ("notes.png", notebook(grid, ink))}
    )
    assert response.status_code == 200
    response = client.post("/api/notes/vector-preview", json={"id": response.json()["id"]})
    assert response.status_code == 200
    lines = response.json()["pages"][0]["polylines"]
    points = [p for line in lines for p in line]
    # 400px square -> 150mm square with a 5mm margin, so all genuine ink
    # occupies x=20..137mm, y=27..122mm. Ruling would reach the page edges.
    assert all(18 <= x <= 138 and 25 <= y <= 125 for x, y in points)
    assert any(
        min(y for _, y in line) < 30
        and max(y for _, y in line) > 56
        and all(41 <= x <= 44 for x, _ in line)
        for line in lines
    )
    assert any(y > 120 and x > 130 for x, y in points)  # underline
    assert any(72 <= x <= 76 and 80 <= y <= 83 for x, y in points)  # dot
    assert any(x > 125 and 90 <= y <= 100 for x, y in points)  # diagram


def test_existing_uploaded_page_is_retraced_when_ruling_filter_changes(client, workspace):
    response = client.post(
        "/api/notes/vectorize", files={"file": ("old.png", notebook("#c8e3ff", "black"))}
    )
    asset_id = response.json()["id"]
    page_file = workspace / "notes" / asset_id / "page.json"
    page = json.loads(page_file.read_text())
    page.pop("trace_version", None)
    page["polylines"] = [[[0, 0], [page["width"], page["height"]]]]
    page_file.write_text(json.dumps(page))
    response = client.post("/api/notes/vector-preview", json={"id": asset_id})
    assert response.status_code == 200
    points = [p for line in response.json()["pages"][0]["polylines"] for p in line]
    assert len(points) > 10
    assert all(18 <= x <= 138 and 25 <= y <= 125 for x, y in points)


@pytest.mark.parametrize("ink", ["#9999ff", "#bbbbff"])
def test_many_lighter_blue_underlines_on_rules_are_preserved(ink):
    image = Image.open(io.BytesIO(notebook("#c8e3ff"))).convert("RGB")
    pen = ImageDraw.Draw(image)
    for y in [60, 100, 140, 180]:
        pen.line([(40, y), (350, y)], fill=ink, width=5)
    original = np.asarray(image)
    ink_pixels = np.all(original == np.asarray(Image.new("RGB", (1, 1), ink))[0, 0], axis=2)
    cleaned = remove_ruling(original)
    assert np.array_equal(cleaned[ink_pixels], original[ink_pixels])
    grid_pixels = np.all(original == [200, 227, 255], axis=2)
    assert np.all(cleaned[grid_pixels] == 255)
