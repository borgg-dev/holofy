"""Perceptual hashing — a compact, robust fingerprint of a card's artwork.

Recognition's primary signal is the *picture*, not the text: a human knows a Charizard at a
glance and reads the tiny collector number only to tell two reprints apart. This is the
machine version of that glance. A DCT perceptual hash reduces a rectified card image to a bit
string that survives what a phone photo does to a card — resize, JPEG noise, modest brightness
and light blur — while staying far apart for genuinely different artwork. Matching is then a
cheap Hamming distance against a precomputed hash per catalog card; nearest wins.

The fingerprint is **YCbCr**, not grayscale. A 64-bit grayscale hash is dominated by the card's
shared *frame* (border, text boxes, HP bar) and discards colour, so two different cards with the
same layout collide: measured over a 12k-card sample, a grayscale hash put an unrelated card
inside the match zone 19% of the time — the systemic cause of "found a card, wrong one". Encoding
luma at higher resolution **and the two chroma planes** (the art's colour, which a shared frame
does not share) cut that collision rate to ~3%. The hash is therefore three concatenated DCT
sub-hashes: luma 16×16 (256 bits) + Cb 8×8 (64) + Cr 8×8 (64) = 384 bits.

Pure numpy, no extra dependency (and no per-call model load): the DCT basis is a small fixed
matrix we build once. This mirrors the codebase's owned-vision stance — the centering and
detection stages are numpy too.
"""

from __future__ import annotations

import numpy as np

# Work size before the DCT. 32×32 keeps enough low-frequency structure to be discriminative
# while staying cheap; each plane's hash is read from the top-left of its transform.
_DCT_N = 32
# Per-plane hash sizes: luma carries the structure (16×16 = 256 bits); the chroma planes carry
# colour, which needs less spatial detail to separate cards (8×8 = 64 bits each).
_LUMA_N = 16
_CHROMA_N = 8
_HASH_BITS = _LUMA_N * _LUMA_N + 2 * _CHROMA_N * _CHROMA_N  # 256 + 64 + 64 = 384

# Rec. 601 YCbCr. Luma is the existing grayscale; Cb/Cr add the colour the old hash threw away.
_RGB_TO_Y = np.array([0.299, 0.587, 0.114])


def _dct_matrix(n: int) -> np.ndarray:
    """The orthonormal DCT-II basis: ``DCT(x) = D @ x``. Built once, reused for every hash."""
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    d = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2.0 / n)
    d[0] *= 1.0 / np.sqrt(2.0)
    return d


_DCT = _dct_matrix(_DCT_N)


def phash(image: np.ndarray) -> int:
    """Compute the 384-bit YCbCr perceptual hash of an RGB (or grayscale) image as an int.

    Empty/degenerate input hashes to 0; it simply matches nothing useful, which is the honest
    behaviour for a blank crop.
    """
    if image is None or image.size == 0:
        return 0
    y, cb, cr = _to_ycbcr_planes(image)
    bits = np.concatenate(
        [
            _plane_bits(y, _LUMA_N),
            _plane_bits(cb, _CHROMA_N),
            _plane_bits(cr, _CHROMA_N),
        ]
    )
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def _plane_bits(plane32: np.ndarray, hash_n: int) -> np.ndarray:
    """The DCT median-threshold bits for one 32×32 plane, read from its top-left ``hash_n`` block."""
    coeffs = _DCT @ plane32 @ _DCT.T
    block = coeffs[:hash_n, :hash_n]
    # The DC term (the plane's mean level) carries no texture and would swamp the median, so
    # exclude it from the threshold — the hash should encode the *pattern*, not the overall level.
    median = float(np.median(block.flatten()[1:]))
    return (block > median).flatten()


def _to_ycbcr_planes(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the (Y, Cb, Cr) planes, each resized to ``_DCT_N``×``_DCT_N``."""
    arr = np.asarray(image)
    if arr.ndim == 3:
        rgb = arr[..., :3].astype(np.float64)
        y = rgb @ _RGB_TO_Y
        cb = 128.0 - 0.168736 * rgb[..., 0] - 0.331264 * rgb[..., 1] + 0.5 * rgb[..., 2]
        cr = 128.0 + 0.5 * rgb[..., 0] - 0.418688 * rgb[..., 1] - 0.081312 * rgb[..., 2]
    else:
        # Grayscale input: no colour to encode, so the chroma planes are flat (mid-level). The
        # luma hash still carries the structure, and a flat chroma hash simply contributes no
        # discrimination rather than failing.
        y = arr.astype(np.float64)
        cb = np.full_like(y, 128.0)
        cr = np.full_like(y, 128.0)
    return _resize(y), _resize(cb), _resize(cr)


def _resize(plane: np.ndarray) -> np.ndarray:
    # Resize to a fixed _DCT_N×_DCT_N with simple area-style binning (no cv2 dependency here so
    # the hash is usable on any ndarray). Pad-safe via linear index mapping.
    h, w = plane.shape
    if (h, w) == (_DCT_N, _DCT_N):
        return plane
    ys = (np.linspace(0, h, _DCT_N + 1)).astype(int)
    xs = (np.linspace(0, w, _DCT_N + 1)).astype(int)
    out = np.empty((_DCT_N, _DCT_N), dtype=np.float64)
    for r in range(_DCT_N):
        y0, y1 = ys[r], max(ys[r] + 1, ys[r + 1])
        for c in range(_DCT_N):
            x0, x1 = xs[c], max(xs[c] + 1, xs[c + 1])
            out[r, c] = plane[y0:y1, x0:x1].mean()
    return out


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two hashes — the raw distance the matcher ranks on."""
    return int(bin(a ^ b).count("1"))


def similarity(a: int, b: int) -> float:
    """Hash agreement as 0–1 (1.0 = identical). ``1 - distance/bits``."""
    return 1.0 - hamming_distance(a, b) / _HASH_BITS
