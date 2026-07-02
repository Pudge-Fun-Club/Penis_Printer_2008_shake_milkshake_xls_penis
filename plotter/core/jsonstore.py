"""Shared helpers for the JSON-file-backed stores (jobs, profiles, auth, …)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path


def atomic_write_json(path: Path, payload: dict | list) -> None:
    """Write JSON via a temp file + rename so readers never see a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


def new_id(prefix: str, nibbles: int) -> str:
    """Random short id like ``prof-3fa9c2d1`` (prefix + hex nibbles)."""
    return prefix + uuid.uuid4().hex[:nibbles]


def now() -> float:
    """Wall-clock timestamp used in store records (seconds since epoch)."""
    return time.time()
