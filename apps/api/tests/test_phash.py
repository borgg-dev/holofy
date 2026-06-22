"""Perceptual hash: identity, robustness to phone-photo degradation, and separation.

These three properties are what make the artwork matcher work — the same card survives resize /
noise / brightness shifts (small Hamming distance), while different artwork stays far apart.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.identify.vision.phash import hamming_distance, phash, similarity


def _smooth_art(seed: int, h: int = 419, w: int = 300) -> np.ndarray:
    # Real card art is large, *saturated* coloured regions (the YCbCr hash keys on luma structure
    # AND chroma), so model it as coarse saturated colour blocks upsampled to card size, softened
    # at the seams — not low-saturation blurred noise, whose weak chroma JPEG would wipe out (an
    # unrepresentative worst case for any colour-aware hash).
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 255, (10, 7, 3)).astype(np.uint8)
    art = cv2.resize(blocks, (w, h), interpolation=cv2.INTER_NEAREST)
    return cv2.GaussianBlur(art, (0, 0), sigmaX=6)


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
    # The degraded card must stay within the production match cutoff (84 bits over the 384-bit
    # YCbCr hash) of its catalog art, so the real artwork is still recognized from a phone photo.
    # Representative saturated art measures well under this (~6–14).
    art = _smooth_art(2)
    assert hamming_distance(phash(art), phash(_phone_degrade(art))) <= 84


def test_different_artwork_is_far() -> None:
    # Different artwork sits far above the match cutoff (observed ~190 over 384 bits).
    a, b = _smooth_art(3), _smooth_art(4)
    assert hamming_distance(phash(a), phash(b)) >= 100


def test_separation_margin_holds() -> None:
    # The matcher relies on "same-degraded" being decisively closer than "different artwork".
    for seed in (2, 5, 7, 11):
        art = _smooth_art(seed)
        same_d = hamming_distance(phash(art), phash(_phone_degrade(art)))
        diff_d = hamming_distance(phash(art), phash(_smooth_art(seed + 100)))
        assert diff_d - same_d >= 40, f"seed {seed}: same={same_d} diff={diff_d}"
        assert similarity(phash(art), phash(_phone_degrade(art))) > 0.7


def test_empty_image_hashes_to_zero() -> None:
    assert phash(np.zeros((0, 0, 3), np.uint8)) == 0
