"""The visual stage seam — capture pixels in, a best-effort ``CardRead`` out.

This is the one part of identification that looks at the image: detect and deskew the card,
locate and OCR the collector number, classify the set symbol, read the name. It is isolated
behind a Protocol so the owned pipeline (detection/crop → read → resolve) is testable with a
deterministic fake, and the real reader — on-device ML Kit OCR on the phone, or a server-side
engine — drops in here without the resolver or provider knowing how the read was produced.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.identify.catalog import CardRead


class CardReader(Protocol):
    async def read(self, images: Sequence[bytes]) -> CardRead:
        """Read identity cues from a capture's stills (primary still first)."""
        ...
