from __future__ import annotations

import json
from fastapi.testclient import TestClient

from plotter.services.auth import AuthService
from plotter.web.app import create_app


def client(workspace, monkeypatch) -> TestClient:
    monkeypatch.delenv("PLOTTER_AUTH_TEST_BYPASS", raising=False)
    return TestClient(create_app())


def setup_admin(
    c: TestClient,
    username: str = "admin",
    password: str = "supersecret12",
) -> dict:
    response = c.post("/api/auth/setup", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


class TestAuthSetup:
    def test_session_reports_unconfigured(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        assert c.get("/api/auth/session").json() == {
            "configured": False,
            "authenticated": False,
            "username": None,
        }

    def test_setup_creates_admin_and_session(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        result = setup_admin(c)
        assert set(result) == {"expires"}
        assert result["expires"] > 0
        session = c.get("/api/auth/session").json()
        assert session["configured"] is True
        assert session["authenticated"] is True
        assert session["username"] == "admin"
        assert (workspace / "auth" / "admin.json").exists()
        assert c.get("/api/jobs").status_code == 200

    def test_second_setup_is_rejected(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        setup_admin(c)
        r = c.post("/api/auth/setup", json={"username": "x", "password": "supersecret12"})
        assert r.status_code == 409

    def test_setup_rejects_weak_password(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        response = c.post("/api/auth/setup", json={"username": "admin", "password": "short"})
        assert response.status_code == 401
        assert not (workspace / "auth" / "admin.json").exists()


class TestAuthLogin:
    def test_dev_bypass_reports_authenticated_session(self, workspace, monkeypatch):
        monkeypatch.delenv("PLOTTER_AUTH_TEST_BYPASS", raising=False)
        monkeypatch.setenv("PLOTTER_AUTH_DEV_BYPASS", "1")
        c = TestClient(create_app())

        assert c.get("/api/auth/session").json() == {
            "configured": True,
            "authenticated": True,
            "username": "dev",
        }
        assert c.get("/api/jobs").status_code == 200

    def test_protected_route_requires_login(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        assert c.get("/api/jobs").status_code == 401

    def test_password_alone_allows_protected_route(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        setup_admin(c)
        c.post("/api/auth/logout")
        r = c.post(
            "/api/auth/login",
            json={
                "username": "admin",
                "password": "supersecret12",
            },
        )
        assert r.status_code == 200
        assert c.get("/api/jobs").status_code == 200

    def test_existing_2fa_account_logs_in_without_code(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        setup_admin(c)
        service = AuthService()
        admin = service._read_admin()
        admin.update(totp_secret="LEGACY-TOTP-SECRET", recovery_code_hashes=["old-hash"])
        service.path.write_text(json.dumps(admin))
        c.post("/api/auth/logout")
        r = c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "supersecret12"},
        )
        assert r.status_code == 200
        assert c.get("/api/jobs").status_code == 200
        assert "totp_secret" not in service._read_admin()
        assert "recovery_code_hashes" not in service._read_admin()

    def test_wrong_password_stays_rejected(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        setup_admin(c)
        c.post("/api/auth/logout")
        response = c.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert c.get("/api/jobs").status_code == 401

    def test_logout_invalidates_session(self, workspace, monkeypatch):
        c = client(workspace, monkeypatch)
        setup_admin(c)
        c.post("/api/auth/logout")
        assert c.get("/api/jobs").status_code == 401

    def test_gallery_upload_stays_public(self, workspace, cal, monkeypatch):
        monkeypatch.setenv("GALLERY_UPLOAD_ENABLED", "1")
        c = client(workspace, monkeypatch)
        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm">'
            b'<line x1="0" y1="0" x2="5" y2="5" stroke="black"/></svg>'
        )
        r = c.post(
            "/api/gallery",
            files={"file": ("art.svg", svg, "image/svg+xml")},
            data={"title": "Art"},
        )
        assert r.status_code == 200
        assert c.get("/api/gallery").status_code == 401
