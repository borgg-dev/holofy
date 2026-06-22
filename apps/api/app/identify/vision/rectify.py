"""Card localization & rectification — find the card's quad and flatten it upright.

A phone photo of a card is rarely axis-aligned: it's tilted, rotated, off-centre, shot at an
angle, with the table around it. Matching a perspective-distorted card against upright catalog
artwork fails, and so does OCR on slanted text. This stage finds the card's four corners (the
largest card-shaped quadrilateral in the frame) and applies a perspective warp that produces a
fixed-size, upright image — the clean, canonical input both the artwork matcher and the OCR
reader need. It is the single biggest accuracy lever in recognition: everything downstream is
only as good as the crop it reads.

OpenCV does the geometry (edge/contour finding, the perspective transform). When no convincing
card quad is found — a busy background, a card bleeding off-frame, a blurred miss — we fall back
to the existing brightness-box crop so the pipeline *degrades* to the old behaviour rather than
blinding itself. The returned quality is honest: a confidently rectified quad scores high; a
fallback crop scores low, which caps recognition confidence downstream exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from app.identify.vision.detect import detect_card_crop

# A standard trading card is 63×88mm → short/long ≈ 0.716. We rectify to a fixed portrait so
# every card — and every catalog image — lands in the same canonical frame the matcher hashes.
_CARD_ASPECT = 0.716
# Output is generous (not 64px) so the OCR reader still has resolution for the tiny collector
# number; the perceptual hash downsamples this further on its own.
_OUT_W = 716
_OUT_H = 1000

# Detection runs on a downscaled copy for speed; corners are scaled back to warp the original
# at full resolution, preserving detail for OCR.
_DETECT_MAX_DIM = 1000
# A quad smaller than this share of the frame is noise, not the subject card. Kept low so an
# unguided capture that doesn't fill the frame still localizes; the guided scan-frame fills far
# more than this.
_MIN_AREA_FRACTION = 0.04
# A quad larger than this is the *frame itself*, not a card on a surface: when a low-contrast
# background thresholds into one blob the whole image becomes a near-card-aspect rectangle and
# would otherwise win. A real capture leaves at least a sliver of surround, so cap it out.
_MAX_AREA_FRACTION = 0.92
# A card genuinely fills its own minimum-area rectangle (bar rounded corners); a non-card blob
# (an L-shaped shadow, a hand) fills much less. This gates the rotated-rect fallback so it can't
# latch onto a random rectangle bounding a sprawling contour.
_MIN_RECT_EXTENT = 0.72
# How far a 4-gon's side ratio may stray from the card aspect (in either orientation) and still
# be accepted as a card. Loose enough for perspective foreshortening, tight enough to reject a
# square table edge or a long rectangular object.
_ASPECT_TOLERANCE = 0.35


@dataclass(frozen=True, slots=True)
class RectifiedCard:
    """A localized, upright card crop ready for hashing and OCR.

    ``image`` is RGB HxWx3. ``quality`` is 0–1 confidence the localization is a cleanly-framed
    card (the ceiling on recognition confidence). ``found_quad`` records whether a real
    perspective rectification happened or we fell back to the brightness-box crop.
    """

    image: np.ndarray
    quality: float
    found_quad: bool


def rectify_card(image_bytes: bytes) -> RectifiedCard:
    """Localize the card in a capture and warp it to a canonical upright frame."""
    try:
        rgb = np.asarray(Image.open(BytesIO(image_bytes)).convert("RGB"))
    except Exception:
        return RectifiedCard(image=np.zeros((_OUT_H, _OUT_W, 3), np.uint8), quality=0.0, found_quad=False)

    quad, quad_quality = _find_card_quad(rgb)
    if quad is None:
        # No convincing card outline — degrade to the brightness-box crop rather than blind the
        # pipeline. It keeps a usable image and an honest (lower) quality.
        fallback = detect_card_crop(image_bytes)
        return RectifiedCard(image=fallback.image, quality=round(fallback.quality * 0.85, 4), found_quad=False)

    warped = _warp(rgb, quad)
    return RectifiedCard(image=warped, quality=round(quad_quality, 4), found_quad=True)


def _find_card_quad(rgb: np.ndarray) -> tuple[np.ndarray | None, float]:
    """Return the best card-shaped quadrilateral (4×2 float corners) and its quality, or None."""
    h, w = rgb.shape[:2]
    scale = min(1.0, _DETECT_MAX_DIM / max(h, w))
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    frame_area = small.shape[0] * small.shape[1]
    candidates = _quad_candidates(gray, frame_area)
    if not candidates:
        return None, 0.0

    # Prefer the highest-scoring card-like quad (area + aspect + rectangularity), not merely the
    # biggest contour — a near-full-frame blob that isn't card-shaped must lose to a clean card.
    best_quad, best_score = max(candidates, key=lambda c: c[1])
    # Scale corners back to the original resolution so the warp keeps full detail for OCR.
    return best_quad / scale, best_score


def _quad_candidates(gray: np.ndarray, frame_area: float) -> list[tuple[np.ndarray, float]]:
    # Complementary segmentations so the card's outline survives whether it contrasts light-on-
    # dark or dark-on-light. Canny finds a border that contrasts with the surface; Otsu and its
    # inverse find a card that is, respectively, brighter or *darker* than its background — the
    # dark-card-on-light-table case the old brightness detector got exactly backwards. A small
    # close bridges nicks in the border without merging the card into the background.
    bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edged = cv2.dilate(cv2.Canny(gray, 40, 140), np.ones((3, 3), np.uint8), iterations=1)
    edged = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, bridge)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_inv = cv2.bitwise_not(otsu)

    out: list[tuple[np.ndarray, float]] = []
    for mask in (edged, otsu, otsu_inv):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:6]:
            area = cv2.contourArea(contour)
            if not (_MIN_AREA_FRACTION * frame_area <= area <= _MAX_AREA_FRACTION * frame_area):
                continue  # too small to be the subject, or large enough to be the frame itself
            out.extend(_quads_from_contour(contour, area, frame_area))
    return out


def _quads_from_contour(contour: np.ndarray, area: float, frame_area: float) -> list[tuple[np.ndarray, float]]:
    """Extract card-like quads from one contour: a simplified 4-gon when the outline is clean,
    plus a minimum-area rectangle fallback that survives a ragged or partly-occluded border."""
    found: list[tuple[np.ndarray, float]] = []
    peri = cv2.arcLength(contour, True)
    # A clean border simplifies to four corners; try progressively looser tolerances before
    # giving up on an exact polygon.
    for eps in (0.02, 0.04, 0.06):
        approx = cv2.approxPolyDP(contour, eps * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype(np.float64)
            score = _score_quad(quad, area / frame_area)
            if score > 0.0:
                found.append((quad, score))
            break

    # Rotated-rectangle fallback: robust to a contour that never simplifies to four points
    # (rounded corners, a nick of glare on an edge). Trust it only when the contour genuinely
    # fills the rectangle, so it can't bound an arbitrary non-card blob.
    (_, (rw, rh), _) = rect = cv2.minAreaRect(contour)
    rect_area = rw * rh
    if 0 < rect_area <= _MAX_AREA_FRACTION * frame_area:
        extent = area / rect_area
        if extent >= _MIN_RECT_EXTENT:
            box = cv2.boxPoints(rect).astype(np.float64)
            score = _score_quad(box, rect_area / frame_area) * min(1.0, extent)
            if score > 0.0:
                found.append((box, score))
    return found


def _score_quad(quad: np.ndarray, area_fraction: float) -> float:
    """Confidence that a convex 4-gon is a cleanly-framed card: fills the frame, has card
    proportions, and is genuinely rectangular. Returns 0 to reject a non-card shape outright."""
    ordered = _order_corners(quad)
    (tl, tr, br, bl) = ordered
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    avg_w = (width_top + width_bottom) / 2.0
    avg_h = (height_left + height_right) / 2.0
    if avg_w < 1.0 or avg_h < 1.0:
        return 0.0

    aspect = min(avg_w, avg_h) / max(avg_w, avg_h)
    aspect_err = abs(aspect - _CARD_ASPECT) / _CARD_ASPECT
    if aspect_err > _ASPECT_TOLERANCE:
        return 0.0  # not card-shaped
    aspect_score = max(0.0, 1.0 - aspect_err)

    # Rectangularity: opposite sides should be near-equal for a flat-ish card. Big disparity
    # means a skewed/non-card quad.
    rect_score = min(width_top, width_bottom) / max(width_top, width_bottom)
    rect_score *= min(height_left, height_right) / max(height_left, height_right)

    # Fill: reward a card that occupies the frame, but don't punish one that doesn't quite fill
    # it. Saturates at ~0.6 of the frame.
    area_score = float(np.clip(area_fraction / 0.6, 0.0, 1.0))

    return float(np.clip(0.4 * area_score + 0.4 * aspect_score + 0.2 * rect_score, 0.0, 1.0))


def _order_corners(quad: np.ndarray) -> np.ndarray:
    """Order four corners as (top-left, top-right, bottom-right, bottom-left)."""
    # The classic sum/diff trick: tl has min x+y, br max x+y; tr has min (y-x), bl max (y-x).
    s = quad.sum(axis=1)
    yx = quad[:, 1] - quad[:, 0]
    tl = quad[np.argmin(s)]
    br = quad[np.argmax(s)]
    tr = quad[np.argmin(yx)]
    bl = quad[np.argmax(yx)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _warp(rgb: np.ndarray, quad: np.ndarray) -> np.ndarray:
    ordered = _order_corners(quad)
    (tl, tr, br, bl) = ordered
    avg_w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
    avg_h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0
    # If the card was photographed in landscape, the detected quad is wider than tall; warp it to
    # the same portrait canvas as the catalog so orientation matches before hashing.
    portrait = avg_h >= avg_w
    out_w, out_h = (_OUT_W, _OUT_H) if portrait else (_OUT_H, _OUT_W)
    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(ordered, dst)
    warped = cv2.warpPerspective(rgb, matrix, (out_w, out_h))
    if not portrait:
        # Rotate the landscape warp upright. Direction is a guess (the guided frame keeps cards
        # roughly upright); the matcher additionally tolerates 180° via its own rotation probe.
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)
    return warped
