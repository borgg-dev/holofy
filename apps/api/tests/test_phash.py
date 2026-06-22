"""Perceptual hash: identity, robustness to phone-photo degradation, and separation.

These three properties are what make the artwork matcher work — the same card survives resize /
noise / brightness shifts (small Hamming distance), while different artwork stays far apart.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.identify.vision.phash import hamming_distance, phash, similarity


def _smooth_art(seed: int, h: int = 419, w: int = 300) -> np.ndarray:
    # Real card art is dominated by low-frequency structure (large coloured regions), which is
    # what a DCT hash keys on — model that with heavily-blurred noise, not white noise.
    rng = np.random.default_rng(seed)
    return cv2.GaussianBlur(rng.integers(0, 255, (h, w, 3)).astype(np.uint8), (0, 0), sigmaX=25)


def _phone_degrade(art: np.ndarray) -> np.ndarray:
    # What a phone capture does to the art: a resize round-trip, JPEG compression, and a
    # brightness shift. (pHash excludes the DC term, so brightness must not move the hash much.)
    small = cv2.resize(art, (int(art.shape[1] * 0.7), int(art.shape[0] * 0.7)))
    up = cv2.resize(small, (art.shape[1], art.shape[0]))
    bright = np.clip(up.astype(int) + 20, 0, 255).astype(np.uint8)
    _, enc = cv2.imencode(".jpg", bright[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 82])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1]


def test_identical_image_hashes_equal() -> None:
    art = _smooth_art(1)
    assert hamming_distance(phash(art), phash(art)) == 0


def test_degraded_same_card_stays_within_match_cutoff() -> None:
    # The degraded card must stay within the production match cutoff (14 bits) of its catalog
    # art, so the real artwork is still recognized from a phone photo. (Real catalog art is more
    # robust still — a staged Charizard photo measured ~6 — this synthetic models the worst case.)
    art = _smooth_art(2)
    assert hamming_distance(phash(art), phash(_phone_degrade(art))) <= 14


def test_different_artwork_is_far() -> None:
    a, b = _smooth_art(3), _smooth_art(4)
    assert hamming_distance(phash(a), phash(b)) >= 20


def test_separation_margin_holds() -> None:
    # The matcher relies on "same-degraded" being decisively closer than "different artwork".
    for seed in (2, 5, 7, 11):
        art = _smooth_art(seed)
        same_d = hamming_distance(phash(art), phash(_phone_degrade(art)))
        diff_d = hamming_distance(phash(art), phash(_smooth_art(seed + 100)))
        assert diff_d - same_d >= 8, f"seed {seed}: same={same_d} diff={diff_d}"
        assert similarity(phash(art), phash(_phone_degrade(art))) > 0.7


def test_empty_image_hashes_to_zero() -> None:
    assert phash(np.zeros((0, 0, 3), np.uint8)) == 0
