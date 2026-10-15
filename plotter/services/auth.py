from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from plotter.core.calibration import data_dir
from plotter.core.jsonstore import atomic_write_json, now
from plotter.core.state import create_store

from .errors import ServiceError


class AuthError(ServiceError):
    status_code = 401


class AuthConflict(ServiceError):
    status_code = 409


class AuthNotConfigured(ServiceError):
    status_code = 503


_lock = threading.RLock()
_hasher = PasswordHasher()
_store = None


def _state():
    global _store
    if _store is None:
        _store = create_store()
    return _store


def _key(prefix: str, token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"auth_{prefix}_{digest}"


class AuthService:
    """Single-admin username/password authentication and session store."""

    def __init__(self, root: Path | None = None):
        self.root = root or (data_dir() / "auth")
        self.path = self.root / "admin.json"

    def configured(self) -> bool:
        return self.path.exists()

    def status(self, token: str | None = None) -> dict:
        session = self.validate_session(token) if token else None
        admin = self._read_admin() if self.configured() else None
        return {
            "configured": self.configured(),
            "authenticated": session is not None,
            "username": admin.get("username") if admin else None,
        }

    def setup(self, username: str, password: str) -> dict:
        username = username.strip()
        if self.configured():
            raise AuthConflict("Admin ist bereits eingerichtet.")
        if not username:
            raise AuthError("Benutzername fehlt.")
        if len(password) < 10:
            raise AuthError("Passwort muss mindestens 10 Zeichen lang sein.")
        admin = {
            "username": username,
            "password_hash": _hasher.hash(password),
            "created": now(),
            "modified": now(),
        }
        with _lock:
            if self.configured():
                raise AuthConflict("Admin ist bereits eingerichtet.")
            atomic_write_json(self.path, admin)
        token, expires = self.create_session(admin["username"])
        return {"token": token, "expires": expires}

    def login(
        self,
        username: str,
        password: str,
    ) -> dict:
        admin = self._require_admin()
        if username.strip() != admin.get("username"):
            raise AuthError("Login fehlgeschlagen.")
        try:
            ok = _hasher.verify(admin["password_hash"], password)
        except VerifyMismatchError:
            ok = False
        if not ok:
            raise AuthError("Login fehlgeschlagen.")
        # Existing accounts keep their password and sessions. Remove obsolete
        # second-factor material only after a successful password check.
        if "totp_secret" in admin or "recovery_code_hashes" in admin:
            admin.pop("totp_secret", None)
            admin.pop("recovery_code_hashes", None)
            self._write_admin(admin)
        token, expires = self.create_session(admin["username"])
        return {"token": token, "expires": expires}

    def create_session(self, username: str) -> tuple[str, float]:
        token = secrets.token_urlsafe(32)
        ttl = session_ttl_seconds()
        expires = now() + ttl
        _state().set(_key("session", token), {"username": username, "expires": expires})
        return token, expires

    def validate_session(self, token: str | None) -> dict | None:
        if not token or not self.configured():
            return None
        session = _state().get(_key("session", token))
        if not session or session.get("expires", 0) < now():
            return None
        admin = self._read_admin()
        if not admin or session.get("username") != admin.get("username"):
            return None
        return {"username": admin["username"], "expires": session["expires"]}

    def logout(self, token: str | None) -> None:
        if token:
            _state().set(_key("session", token), {"expires": 0})

    def _require_admin(self) -> dict:
        admin = self._read_admin()
        if not admin:
            raise AuthNotConfigured("Admin ist noch nicht eingerichtet.")
        return admin

    def _read_admin(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write_admin(self, admin: dict) -> None:
        admin["modified"] = now()
        atomic_write_json(self.path, admin)


def session_ttl_seconds() -> int:
    raw = os.environ.get("PLOTTER_AUTH_SESSION_TTL", str(14 * 24 * 60 * 60))
    try:
        return max(60, int(raw))
    except ValueError:
        return 14 * 24 * 60 * 60
