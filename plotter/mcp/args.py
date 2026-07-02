"""Scalar tool-argument coercion and the structured tool-error payload."""

from __future__ import annotations

import math
from typing import Any


class ToolPayloadError(RuntimeError):
    """Tool failure carrying a structured payload returned verbatim to the agent."""

    def __init__(self, payload: dict):
        super().__init__(str(payload.get("message") or payload.get("error") or "Tool error"))
        self.payload = payload


def require_arg(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string argument: {key}")
    return value


def int_arg(args: dict[str, Any], key: str, default: int, *, lo: int, hi: int) -> int:
    raw = args.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    return max(lo, min(value, hi))


def float_arg(args: dict[str, Any], key: str, default: float | None = None) -> float:
    raw = args.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not (value == value and abs(value) != float("inf")):
        raise ValueError(f"{key} must be finite")
    return value


def num(data: dict[str, Any], key: str, default: float | None = None) -> float:
    raw = data.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def segments(data: dict[str, Any], default: int = 96) -> int:
    return max(4, min(int(num(data, "segments", default)), 720))
