"""The OCR engine seam — pixels in, located text tokens out.

Isolated behind a Protocol so the reader's parsing logic is unit-testable with a fake engine
(no model load), while the real engine runs on-device-class CPU inference. We use RapidOCR
(PaddleOCR models exported to ONNX) deliberately: it is pure-pip, CPU-only, ships its own
models, and needs no system Tesseract — so it runs the same in CI, in dev, and in the EU
inference container, with no per-scan vendor fee (the whole reason we build this in-house).

The model is loaded lazily on first read: importing this module — or running the app on the
mock backend — must not pay the ONNX load cost or even require onnxruntime to be installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class OcrToken:
    """One recognized text span: its text, where its centre sits, and how tall its box is.

    ``height`` (the text box's pixel height) is a proxy for font size — the card *name* is set
    larger than the "Basic Pokémon" type label above it, so height is what separates the name
    from the surrounding small print when both sit in the top band.
    """

    text: str
    confidence: float
    cx: float
    cy: float
    height: float = 0.0


class OcrEngine(Protocol):
    def read_text(self, image: np.ndarray) -> list[OcrToken]:
        """Recognize all text in an RGB image. Empty when nothing is legible."""
        ...


class RapidOcrEngine:
    """RapidOCR-backed engine. Thread-safe enough for our use: one lazily-built model reused
    across reads (model load is ~1–2s, so it must not happen per scan).
    """

    def __init__(self) -> None:
        self._engine = None

    def read_text(self, image: np.ndarray) -> list[OcrToken]:
        engine = self._ensure_engine()
        result, _elapse = engine(image)
        tokens: list[OcrToken] = []
        for box, text, confidence in result or []:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            tokens.append(
                OcrToken(
                    text=text,
                    confidence=float(confidence),
                    cx=float(sum(xs) / len(xs)),
                    cy=float(sum(ys) / len(ys)),
                    height=float(max(ys) - min(ys)),
                )
            )
        return tokens

    def _ensure_engine(self):
        if self._engine is None:
            # Imported here so the dependency is only required when the in-house backend runs.
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine
