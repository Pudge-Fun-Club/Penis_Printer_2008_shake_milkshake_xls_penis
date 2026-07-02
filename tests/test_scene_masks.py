from __future__ import annotations

from plotter.scene import page_polylines


def _line(z: int = 0) -> dict:
    return {
        "id": f"line-{z}",
        "type": "line",
        "zOrder": z,
        "transform": {"x": 0, "y": 0, "rotation": 0, "scale": 1},
        "cachedPolylines": [[[-10, 5], [30, 5]]],
    }


def _mask(z: int = 1) -> dict:
    return {
        "id": f"mask-{z}",
        "type": "mask-rect",
        "zOrder": z,
        "data": {"mask": "erase"},
        "transform": {"x": 10, "y": 5, "rotation": 0, "scale": 1},
        "cachedPolylines": [[[-5, -5], [5, -5], [5, 5], [-5, 5], [-5, -5]]],
    }


def test_mask_rect_removes_lines_below_it():
    lines = page_polylines({"objects": [_line(0), _mask(1)]})

    assert lines == [[(-10.0, 5.0), (5.0, 5.0)], [(15.0, 5.0), (30.0, 5.0)]]


def test_mask_rect_does_not_remove_lines_above_it():
    lines = page_polylines({"objects": [_mask(0), _line(1)]})

    assert lines == [[(-10.0, 5.0), (30.0, 5.0)]]


def test_null_transform_coords_do_not_crash():
    # A malformed object (e.g. a fill whose NaN center serialised to null) must
    # not take down page_polylines / scoring for the whole page.
    obj = {
        "id": "broken",
        "type": "fill",
        "zOrder": 0,
        "transform": {"x": None, "y": None, "rotation": None, "scale": None},
        "cachedPolylines": [[[0, 0], [10, 0], [10, 10]]],
    }
    lines = page_polylines({"objects": [obj]})
    # Treated as x=y=0, rotation=0, scale=1 → geometry passes through unchanged.
    assert lines == [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]]
