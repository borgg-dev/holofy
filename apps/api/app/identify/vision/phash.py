"""Perceptual hashing — a compact, robust fingerprint of a card's artwork.

Recognition's primary signal is the *picture*, not the text: a human knows a Charizard at a
glance and reads the tiny collector number only to tell two reprints apart. This is the
machine version of that glance. A DCT perceptual hash (pHash) reduces a rectified card image
to 64 bits that survive the things a phone photo does to a card — resize, JPEG noise, modest
brightness and colour shifts, light blur — while staying far apart for genuinely different
artwork. Matching is then a cheap Hamming distance against a precomputed hash per catalog
card; nearest wins.

Pure numpy, no extra dependency (and no per-call model load): the DCT basis is a small fixed
matrix we build once. This mirrors the codebase's owned-vision stance — the centering and
detection stages are numpy too.
"""

from __future__ import annotations

import numpy as np

# Work size before the DCT. 32×32 keeps enough low-frequency structure to be discriminative
# while staying cheap; the hash is read from the top-left 8×8 of the transform.
_DCT_N = 32
_HASH_N = 8
_HASH_BITS = _HASH_N * _HASH_N  # 64


def _dct_matrix(n: int) -> np.ndarray:
    """The orthonormal DCT-II basis: ``DCT(x) = D @ x``. Built once, reused for every hash."""
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    d = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2.0 / n)
    d[0] *= 1.0 / np.sqrt(2.0)
    return d


_DCT = _dct_matrix(_DCT_N)


def phash(image: np.ndarray) -> int:
    """Compute the 64-bit perceptual hash of an RGB (or grayscale) image as an int.

    Empty/degenerate input hashes to 0; it simply matches nothing useful, which is the honest
    behaviour for a blank crop.
    """
    if image is None or image.size == 0:
        return 0
    gray = _to_gray_32(image)
    coeffs = _DCT @ gray @ _DCT.T
    block = coeffs[:_HASH_N, :_HASH_N]
    # The DC term (mean brightness) carries no texture and would swamp the median, so exclude it
    # from the threshold — the hash should encode the *pattern*, not the overall lightness.
    median = float(np.median(block.flatten()[1:]))
    bits = (block > median).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def _to_gray_32(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 3:
        # Rec. 601 luma; matches how OpenCV/PIL collapse colour to gray.
        arr = arr[..., :3].astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    else:
        arr = arr.astype(np.float64)
    # Resize to a fixed _DCT_N×_DCT_N with simple area-style binning (no cv2 dependency here so
    # the hash is usable on any ndarray). Pad-safe via linear index mapping.
    h, w = arr.shape
    if (h, w) != (_DCT_N, _DCT_N):
        ys = (np.linspace(0, h, _DCT_N + 1)).astype(int)
        xs = (np.linspace(0, w, _DCT_N + 1)).astype(int)
        out = np.empty((_DCT_N, _DCT_N), dtype=np.float64)
        for r in range(_DCT_N):
            y0, y1 = ys[r], max(ys[r] + 1, ys[r + 1])
            for c in range(_DCT_N):
                x0, x1 = xs[c], max(xs[c] + 1, xs[c + 1])
                out[r, c] = arr[y0:y1, x0:x1].mean()
        arr = out
    return arr


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two hashes — the raw distance the matcher ranks on."""
    return int(bin(a ^ b).count("1"))


def similarity(a: int, b: int) -> float:
    """Hash agreement as 0–1 (1.0 = identical). ``1 - distance/64``."""
    return 1.0 - hamming_distance(a, b) / _HASH_BITS
