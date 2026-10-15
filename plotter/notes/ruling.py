"""Suppress repeated faint notebook rules while retaining darker pen strokes."""

from __future__ import annotations

import cv2
import numpy as np


def remove_ruling(rgb: np.ndarray) -> np.ndarray:
    # The darkest channel distinguishes light blue/red paper rules from even
    # saturated blue ink. Taking the brightest channel would erase blue ink.
    tone = rgb.min(axis=2)
    background = cv2.morphologyEx(
        tone, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    )
    contrast = background.astype(np.int16) - tone.astype(np.int16)
    faint = (tone >= 140) & (contrast >= 5)
    h, w = tone.shape
    segments = cv2.HoughLinesP(
        faint.astype(np.uint8) * 255,
        1,
        np.pi / 180,
        threshold=35,
        minLineLength=max(25, min(h, w) // 4),
        maxLineGap=max(8, min(h, w) // 30),
    )
    if segments is None:
        return rgb
    segments = segments[:, 0].astype(float)
    dx, dy = segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1]
    angles = np.mod(np.arctan2(dy, dx), np.pi)
    lengths = np.hypot(dx, dy)
    remaining = np.ones(len(segments), dtype=bool)
    erase = np.zeros((h, w), dtype=bool)
    yy, xx = np.indices((h, w), dtype=np.float32)

    for _ in range(4):
        if not remaining.any():
            break
        bins = np.mod(np.rint(angles / np.pi * 90).astype(int), 90)
        counts = np.bincount(bins[remaining], weights=lengths[remaining], minlength=90)
        center = np.argmax(counts) * np.pi / 90
        distance = abs(np.arctan2(np.sin(2 * (angles - center)), np.cos(2 * (angles - center)))) / 2
        family = remaining & (distance <= np.deg2rad(3))
        remaining[family] = False
        normal = np.array([-np.sin(center), np.cos(center)])
        mids = (segments[family, :2] + segments[family, 2:]) / 2
        offsets = np.sort(mids @ normal)
        clusters: list[list[float]] = []
        for offset in offsets:
            if clusters and offset - clusters[-1][-1] <= 4:
                clusters[-1].append(float(offset))
            else:
                clusters.append([float(offset)])
        centers = np.array([np.mean(cluster) for cluster in clusters])
        if len(centers) < 4:
            continue
        pitch = float(np.median(np.diff(centers)))
        if pitch < 8:
            continue
        tolerance = max(2.5, pitch * 0.10)
        phases = abs((centers[:, None] - centers[None, :] + pitch / 2) % pitch - pitch / 2)
        votes = (phases <= tolerance).sum(axis=0)
        anchor = float(centers[np.argmax(votes)])
        if votes.max() < 4 or votes.max() < len(centers) * 0.7:
            continue
        projection = xx * normal[0] + yy * normal[1]
        line_distance = abs((projection - anchor + pitch / 2) % pitch - pitch / 2)
        bands = line_distance <= tolerance + 2
        samples = tone[faint & bands]
        if len(samples) < 50:
            continue
        # Keep ink at crossings: its colour is darker than the surrounding
        # ruling. Never whiten whole horizontal/vertical bands.
        # Infer ruling brightness from the lighter half of the samples. A
        # lower quantile can be dominated by genuine blue underlines lying
        # on rules. Allow the ruling's brightness spread (antialiasing and
        # illumination), but keep a narrow cutoff for uniform-colour rules.
        median, light = np.percentile(samples, [50, 90])
        minimum = max(140, float(median - 3 * (light - median) - 5))
        erase |= bands & faint & (tone >= minimum)
    if not erase.any():
        return rgb
    cleaned = rgb.copy()
    cleaned[erase] = 255
    return cleaned
