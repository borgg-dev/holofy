"""Card localization & rectification — recover an upright, card-shaped crop from a skewed photo.

The synthetic scenes stage a coloured card at an angle on a textured background (what the
brightness-threshold detector failed on), and assert the rectifier finds the quad, returns the
card aspect, and recovers orientation. A no-card frame must report no quad and low quality so the
honest ceiling still caps recognition downstream.
"""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from app.identify.vision.rectify import _CARD_ASPECT, rectify_card


def _png(scene: np.ndarray) -> bytes:
    buf = BytesIO()
    Image.fromarray(scene).save(buf, format="PNG")
    return buf.getvalue()


def _staged_card(angle_deg: float = 18.0, card_w: int = 300, card_h: int = 419) -> np.ndarray:
    rng = np.random.default_rng(0)
    bg = rng.integers(40, 90, (900, 900, 3)).astype(np.uint8)
    card = np.full((card_h, card_w, 3), (200, 180, 60), np.uint8)
    card[:40, :] = (230, 40, 40)  # red top band — an orientation marker
    src = np.array([[0, 0], [card_w, 0], [card_w, card_h], [0, card_h]], np.float32)
    rot = cv2.getRotationMatrix2D((card_w / 2, card_h / 2), angle_deg, 1.0)
    corners = cv2.transform(src.reshape(1, -1, 2), rot).reshape(-1, 2) + np.array([450 - card_w / 2, 450 - card_h / 2])
    matrix = cv2.getPerspectiveTransform(src, corners.astype(np.float32))
    warped = cv2.warpPerspective(card, matrix, (900, 900))
    mask = cv2.warpPerspective(np.ones((card_h, card_w), np.uint8) * 255, matrix, (900, 900))
    scene = bg.copy()
    scene[mask > 0] = warped[mask > 0]
    return scene


def test_finds_and_rectifies_an_angled_card() -> None:
    rect = rectify_card(_png(_staged_card(angle_deg=18)))
    assert rect.found_quad
    assert rect.quality > 0.4
    h, w = rect.image.shape[:2]
    assert abs(min(w, h) / max(w, h) - _CARD_ASPECT) < 0.02


def test_recovers_upright_orientation() -> None:
    rect = rectify_card(_png(_staged_card(angle_deg=22)))
    # The red marker band must come back at the TOP of the rectified card.
    top = rect.image[:60].reshape(-1, 3).mean(0)
    bottom = rect.image[-60:].reshape(-1, 3).mean(0)
    assert top[0] > top[1] and top[0] > top[2]  # reddish on top
    assert bottom[0] < top[0]


def test_no_card_frame_reports_low_quality() -> None:
    rng = np.random.default_rng(7)
    noise = rng.integers(0, 255, (600, 600, 3)).astype(np.uint8)
    rect = rectify_card(_png(noise))
    # Either no quad at all, or a weak one — never a confident card on pure noise.
    assert rect.quality < 0.5


def test_undecodable_bytes_do_not_raise() -> None:
    rect = rectify_card(b"not an image")
    assert rect.quality == 0.0
    assert not rect.found_quad
