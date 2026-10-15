from __future__ import annotations

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from plotter.core.jobmeta import read_job_meta
from plotter.gcode.safety import GcodeSafetyChecker
from plotter.web.app import create_app

ALPHABET = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"


@pytest.fixture
def client(workspace, cal):
    return TestClient(create_app())


def photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (80, 80), "white").save(out, format="PNG")
    return out.getvalue()


def test_missing_ocr_key_is_actionable(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    r = client.post("/api/notes/transcribe", files={"file": ("notes.png", photo())})
    assert r.status_code == 503
    assert "ключ" in r.json()["detail"].lower()


def test_corrupt_photo_rejected_before_provider(client):
    r = client.post("/api/notes/transcribe", files={"file": ("notes.png", b"broken")})
    assert r.status_code == 415


@pytest.mark.parametrize("font", ["notes-neat", "notes-slant", "notes-human"])
def test_every_cyrillic_letter_has_real_strokes(client, font):
    for ch in ALPHABET:
        r = client.post("/api/notes/preview", json={"text": ch, "font": font})
        assert r.status_code == 200, (ch, r.text)
        assert r.json()["pages"][0]["polylines"], ch


def test_paginate_preserves_all_words_and_fits_paper(client):
    words = [f"Строка{i}" for i in range(220)]
    r = client.post("/api/notes/preview", json={"text": " ".join(words), "size": 8})
    assert r.status_code == 200
    pages = r.json()["pages"]
    assert len(pages) > 1
    assert " ".join(p["text"] for p in pages).split() == words
    for p in pages:
        for line in p["polylines"]:
            assert len(line) >= 2
            assert all(0 <= x <= p["width"] and 0 <= y <= p["height"] for x, y in line)


def test_long_word_wraps_without_losing_characters(client):
    word = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя" * 6
    r = client.post("/api/notes/preview", json={"text": word, "size": 8})
    assert r.status_code == 200
    result = "".join(p["text"].replace("\n", "") for p in r.json()["pages"])
    assert result == word


def test_paragraph_breaks_preserved(client):
    r = client.post("/api/notes/preview", json={"text": "Первый\n\nВторой"})
    assert r.status_code == 200
    assert r.json()["pages"][0]["text"] == "Первый\n\nВторой"


def test_unsupported_glyph_is_not_silently_dropped(client):
    r = client.post("/api/notes/preview", json={"text": "Задача 🦄"})
    assert r.status_code == 422
    assert "🦄" in r.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "   "},
        {"text": "x", "size": 0},
        {"text": "x", "size": float("inf")},
        {"text": "x", "font": "missing"},
    ],
)
def test_invalid_layout_rejected(client, payload):
    if payload.get("size") == float("inf"):
        r = client.post(
            "/api/notes/preview",
            content='{"text":"x","size":1e999}',
            headers={"Content-Type": "application/json"},
        )
    else:
        r = client.post("/api/notes/preview", json=payload)
    assert r.status_code == 422


def test_jobs_are_safe_and_profile_bound(client, workspace, cal):
    r = client.post("/api/notes/jobs", json={"text": "Конспект: русский текст. Ёжик!"})
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert jobs
    for job in jobs:
        path = workspace / "jobs" / job["filename"]
        code = path.read_text()
        GcodeSafetyChecker(cal).check(code)
        assert "G28" not in code
        assert not any(
            line.startswith(("M104", "M109", "M140", "M190")) for line in code.splitlines()
        )
        meta = read_job_meta(path)
        assert meta["source"]["kind"] == "notebook"
        assert meta["profile"]["id"]


def test_ocr_settings_do_not_disclose_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.put("/api/notes/ocr-settings", json={"api_key": "test-secret-key"})
    assert r.status_code == 200
    assert r.json()["ocrReady"] is True
    assert "test-secret-key" not in r.text
    assert "test-secret-key" not in client.get("/api/notes/status").text


def test_real_ocr_request_decodes_transcription(client, monkeypatch):
    from openai import OpenAI

    from plotter.notes import ocr

    def respond(request):
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["input"][0]["content"][0]["type"] == "input_image"
        assert body["input"][0]["content"][0]["image_url"].startswith("data:image/png;base64,")
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "gpt-4.1-mini",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_test",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Лекция 1\nРусский текст",
                                "annotations": [],
                            }
                        ],
                    }
                ],
            },
        )

    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")
    monkeypatch.setattr(
        ocr,
        "make_client",
        lambda _: OpenAI(
            api_key="local-test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        ),
    )
    r = client.post("/api/notes/transcribe", files={"file": ("notes.png", photo())})
    assert r.status_code == 200
    assert r.json()["text"] == "Лекция 1\nРусский текст"


def test_truncated_ocr_is_not_printable(client, monkeypatch):
    from types import SimpleNamespace

    from plotter.notes import ocr

    monkeypatch.setenv("OPENAI_API_KEY", "local-test-key")
    response = SimpleNamespace(status="incomplete", output_text="Полконспекта")
    client_double = SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kw: response), close=lambda: None
    )
    monkeypatch.setattr(ocr, "make_client", lambda _: client_double)
    r = client.post("/api/notes/transcribe", files={"file": ("notes.png", photo())})
    assert r.status_code == 502


def test_notes_endpoints_require_login(client, monkeypatch):
    monkeypatch.delenv("PLOTTER_AUTH_TEST_BYPASS")
    assert client.get("/api/notes/status").status_code == 401
