"""Hand-written-look variation: per-glyph humanize, per-word jitter and a
smooth page-level warp. All amplitudes are fractions of the em."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from plotter.text.flatten import Polyline


@dataclass(frozen=True)
class Humanize:
    """Per-glyph variation that turns a clean print font into hand-printed
    handwriting. All amplitudes are fractions of the em (text size). Applied as
    rigid per-glyph transforms plus tiny vertex noise, so it adds no pen lifts
    and almost no draw length — the plot score stays high."""

    rotate_deg: float = 2.5   # max per-glyph tilt
    scale_var: float = 0.035  # per-glyph size wobble
    baseline: float = 0.05    # vertical bounce
    x_jitter: float = 0.02    # horizontal nudge
    advance: float = 0.03     # uneven letter spacing
    # Per-point waviness. Kept at 0 for clean print handwriting: it inflates
    # draw length (zig-zag between dense curve points) and lowers the score.
    vertex: float = 0.0


@dataclass(frozen=True)
class WordJitter:
    """Subtle per-word variation for cursive fonts so a line of handwriting does
    not sit on a ruler-straight baseline with identical words. Applied as one
    rigid transform per word *after* the word's letters are joined, so the
    intra-word connections (and the dots/accents) move together and stay intact.
    Amplitudes are fractions of the em except rotation (degrees)."""

    rotate_deg: float = 1.4
    scale: float = 0.02
    x: float = 0.012
    baseline: float = 0.03


@dataclass(frozen=True)
class Warp:
    """Smooth position-dependent displacement applied to the whole render so the
    baseline drifts and individual letters don't all sit on the same line. Being
    a pure function of position, coincident points (the cursive joins) move
    together, so no connection is ever broken. Amplitudes are fractions of em."""

    y: float = 0.022        # vertical amplitude
    x: float = 0.010        # horizontal amplitude
    wave_long: float = 3.2  # long wavelength in ems (baseline drift)
    wave_short: float = 1.15  # short wavelength in ems (per-letter ripple)


USER_PLOTTER_HUMANIZE = Humanize(
    rotate_deg=1.2,
    scale_var=0.012,
    baseline=0.018,
    x_jitter=0.01,
    advance=0.012,
    vertex=0.0015,
)


def warp(lines: list[Polyline], em_mm: float, seed: int, w: Warp) -> list[Polyline]:
    """Apply a smooth sinusoidal warp (baseline drift + gentle ripple) to every
    point. Pure function of position, so connections stay intact."""
    rng = random.Random(seed)
    p1, p2, p3 = (rng.uniform(0, 2 * math.pi) for _ in range(3))
    ay, ax = w.y * em_mm, w.x * em_mm
    k1 = 2 * math.pi / (w.wave_long * em_mm)
    k2 = 2 * math.pi / (w.wave_short * em_mm)
    kx = 2 * math.pi / (w.wave_long * 0.7 * em_mm)
    return [
        [
            (
                x + ax * math.sin(y * kx + p3),
                y + ay * math.sin(x * k1 + p1) + 0.45 * ay * math.sin(x * k2 + p2),
            )
            for x, y in line
        ]
        for line in lines
    ]


def jitter_word(
    strokes: list[Polyline], j: WordJitter, em_mm: float, rng: random.Random
) -> list[Polyline]:
    """Apply one rigid transform (rotation + scale + offset about the word's
    centre) to every stroke of a word, preserving all internal connections."""
    pts = [p for s in strokes for p in s]
    if not pts:
        return strokes
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ang = math.radians(rng.uniform(-j.rotate_deg, j.rotate_deg))
    sc = 1 + rng.uniform(-j.scale, j.scale)
    dx = rng.uniform(-j.x, j.x) * em_mm
    dy = rng.uniform(-j.baseline, j.baseline) * em_mm
    ca, sa = math.cos(ang), math.sin(ang)
    out: list[Polyline] = []
    for s in strokes:
        ns: Polyline = []
        for x, y in s:
            ox, oy = (x - cx) * sc, (y - cy) * sc
            ns.append((cx + ox * ca - oy * sa + dx, cy + ox * sa + oy * ca + dy))
        out.append(ns)
    return out


def humanize_glyph(
    strokes: list[Polyline], h: Humanize, em_mm: float, rng: random.Random
) -> tuple[list[Polyline], float]:
    """Apply a per-glyph rigid transform (+ tiny vertex noise) and return the
    transformed strokes plus an advance-width delta for uneven spacing."""
    advance = rng.uniform(-h.advance, h.advance) * em_mm
    if not strokes:
        return strokes, advance

    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    ang = math.radians(rng.uniform(-h.rotate_deg, h.rotate_deg))
    sc = 1 + rng.uniform(-h.scale_var, h.scale_var)
    dx = rng.uniform(-h.x_jitter, h.x_jitter) * em_mm
    dy = rng.uniform(-h.baseline, h.baseline) * em_mm
    ca, sa = math.cos(ang), math.sin(ang)
    vj = h.vertex * em_mm

    out: list[Polyline] = []
    for s in strokes:
        ns: Polyline = []
        for x, y in s:
            ox, oy = (x - cx) * sc, (y - cy) * sc
            rx, ry = ox * ca - oy * sa, ox * sa + oy * ca
            jx = rng.uniform(-vj, vj) if vj else 0.0
            jy = rng.uniform(-vj, vj) if vj else 0.0
            ns.append((cx + rx + dx + jx, cy + ry + dy + jy))
        out.append(ns)
    return out, advance
