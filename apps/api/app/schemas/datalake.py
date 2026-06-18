"""The training-example contract — what a consented capture becomes in the data lake.

The moat (master plan §2, architecture §6) is the compounding proprietary dataset: every
*consented* scan, pre-grade and authenticity screen is a labelled example that later trains
the in-house models which drive per-scan COGS toward zero. This module is the shape that
example takes the moment it crosses from the live DB into the lake.

Three example kinds, one envelope. Each carries:

- the record it derives from (``record_id``) and its owner (``user_id``) — so a later
  erasure can target a user's examples precisely (architecture §6, ``app/db/erasure.py``);
- the capture reference (``capture_ref``) — the object-storage key for the stills, never the
  bytes (data minimization, §6);
- the labels for that example kind — recognition candidates + resolved card for a scan, the
  grade range + sub-scores for a pre-grade, the risk band + signals for an authenticity
  screen. These are the supervision signal the model trains against.

There is deliberately no consent flag on the example: a non-consented record never produces
one. The consent gate lives upstream, at emission (the scan service / the pre-grade and
authenticity endpoints), so an example existing at all *is* the proof consent was held — the
sink can't be handed an unconsented example by construction.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrainingExampleKind(StrEnum):
    """Which pipeline a training example feeds — they label differently."""

    SCAN = "scan"
    PREGRADE = "pregrade"
    AUTHENTICITY = "authenticity"


class TrainingExample(BaseModel):
    """One consented capture, labelled, on its way into the data lake.

    ``labels`` holds the example-kind-specific supervision payload as plain JSON (the ranked
    candidates and resolved card for a scan; the range and sub-scores for a pre-grade; the
    risk band and signals for an authenticity screen) — the same JSON already persisted on
    the source record, so the lake row and the audit trail can't drift. ``resolved_card_id``
    is lifted out of the labels because it is the join key the labelling pipeline groups on.
    """

    model_config = ConfigDict(frozen=True)

    kind: TrainingExampleKind
    # The source record and its owner — the precise targets an erasure purge enumerates.
    record_id: uuid.UUID
    user_id: uuid.UUID
    # Object-storage key for the capture stills; never the bytes (data minimization, §6).
    capture_ref: str
    # The canonical card this capture resolved to, when one was — the labelling join key.
    resolved_card_id: uuid.UUID | None = None
    labels: dict[str, Any] = Field(default_factory=dict)
