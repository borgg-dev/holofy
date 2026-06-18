"""Request/response contract for the stack/batch scan endpoint (P4.1).

Stack mode: the user flips through a pile of cards while the client samples frames and
uploads a bundle per detected card. This endpoint identifies + prices each — **ID + value
only**; grade and authenticity stay single-card guided (master plan §7, architecture §3.1) —
and folds near-identical detections into one result so flipping past the same card twice
doesn't double-count it.

The response models three per-item outcomes the confirm-at-end UI renders differently:

- ``resolved`` — a confident identity, priced; ``count`` is how many captures collapsed onto it.
- ``needs_confirmation`` — the top-2 same-art candidates with their € delta, to confirm at the
  end of the stack rather than mid-flip.
- ``unrecognized`` — no card read; surfaced so the user can re-capture that one.
- ``quota_exceeded`` — captures the day's remaining budget couldn't cover; they were skipped
  *before* recognition (no COGS), so the user knows they were skipped, not lost. ``count`` is
  how many captures hit the wall.

COGS is bounded by quota, not by batch size: each capture consumes one daily scan unit *before*
it is recognized (recognition is the credit), so recognition calls can never exceed the day's
remaining budget. ``MAX_BATCH_ITEMS`` only caps the request to a sane size. Dedupe collapses
the recognized captures so a card never *banks* twice, but it does not refund the per-capture
charge — flipping one card twice spends two units, the same as scanning it twice singly.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.scan import CaptureBundleRef, ConfirmationChoice, ScannedCard

# A stack is a handful-to-a-binder-page of flips, not an unbounded firehose. The cap bounds
# the worst-case number of recognition calls one request can trigger (a COGS guard that works
# alongside the per-card daily quota) and keeps the response a sane size.
MAX_BATCH_ITEMS = 50


class BatchScanRequest(BaseModel):
    """A batch of capture bundle refs sampled from one stack-scanning session."""

    items: list[CaptureBundleRef] = Field(min_length=1, max_length=MAX_BATCH_ITEMS)


class BatchItemOutcome(StrEnum):
    RESOLVED = "resolved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNRECOGNIZED = "unrecognized"
    # Captures past the day's remaining scan budget — skipped before recognition (no COGS).
    QUOTA_EXCEEDED = "quota_exceeded"


class BatchScanItem(BaseModel):
    """One deduped entry in a stack result.

    ``count`` is how many captures in the batch collapsed onto this card (≥1); the client
    pre-fills that quantity at confirm-at-end. ``capture_refs`` lists the bundles that merged
    here, in arrival order, so the UI can show which flips produced it. The payload fields
    mirror the single-scan response, populated per ``outcome``.
    """

    outcome: BatchItemOutcome
    # How many captures this item covers (≥1): the flips that deduped onto a card, or — for the
    # single quota_exceeded item — every capture that hit the daily wall.
    count: int = Field(ge=1)
    capture_refs: list[str]

    # outcome == resolved
    card: ScannedCard | None = None
    # outcome == needs_confirmation: top-2 ordered by confidence + the € gap that justifies asking.
    choices: list[ConfirmationChoice] | None = None
    price_delta: Decimal | None = None


class BatchScanQuota(BaseModel):
    """How the day's scan budget was applied to this batch.

    ``charged`` is the number of captures that consumed a unit — i.e. that were recognized, one
    credit each (the honest COGS of this batch). ``remaining`` is what's left after this batch;
    ``rejected`` is how many captures the budget couldn't cover and were skipped before
    recognition (the ``quota_exceeded`` item's ``count``).
    """

    limit: int
    charged: int
    remaining: int
    rejected: int


class BatchScanResponse(BaseModel):
    """Per-card results for confirm-at-end, plus how the batch spent its quota."""

    items: list[BatchScanItem]
    quota: BatchScanQuota
