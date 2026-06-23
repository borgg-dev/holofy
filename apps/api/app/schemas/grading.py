"""Pre-grade request/response contract — honest, probabilistic, never an absolute grade.

The deliberate honesty rules (charter §3.1) are encoded in the *types* here, not left to
prose:

- The output is a ``GradeProbabilityRange`` — a likely grade band plus ``p_at_least``, a
  P(grade ≥ floor) — never a single number. There is no field that holds "the grade".
- Every result carries ``disclaimer`` semantics: it is a pre-screen, decision support, not
  an official PSA/CGC/BGS grade.
- A capture too poor to grade honestly does not get a confident wrong answer: the outcome
  is ``retake`` with the reasons, which the endpoint returns as a typed 200 body (a clear
  signal, not a 500).

The four PSA sub-grades each surface as a ``SubScore`` (score + confidence). Centering is
measured in-house (``app.grading.centering``); corners/edges/surface are bought behind the
``GradingProvider`` seam and mocked for now.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import CardCondition

# Pre-grade is framed against the PSA 1–10 scale because that is the scale collectors price
# and reason against — but always as a *range over* it, never a point on it.
PREGRADE_DISCLAIMER = (
    "Pre-screen estimate, not an official grade. This is decision support to help you "
    "decide whether a card is worth submitting — it is not a PSA, CGC or BGS grade."
)


class GradingAxis(StrEnum):
    """The four PSA sub-grades. Centering is measured in-house; the rest are bought."""

    CENTERING = "centering"
    CORNERS = "corners"
    EDGES = "edges"
    SURFACE = "surface"


class PregradeStatus(StrEnum):
    """Terminal state of a pre-grade.

    ``estimated`` — a probability range was produced (possibly with low confidence).
    ``retake`` — the capture was too poor to estimate honestly; the client must re-capture.
    """

    ESTIMATED = "estimated"
    RETAKE = "retake"


class SubScore(BaseModel):
    """One axis of the pre-grade: an estimated 1–10 score with its own measurement confidence.

    ``confidence`` rates how trustworthy *this measurement* is (capture quality, model
    certainty), independent of how good the score is — a confidently-read poor surface is
    high-confidence and low-score. The two are kept separate so the composite can down-weight
    an axis we couldn't read well rather than letting it drag the range on false precision.
    """

    model_config = ConfigDict(frozen=True)

    axis: GradingAxis
    score: float = Field(ge=1.0, le=10.0)
    confidence: float = Field(ge=0.0, le=1.0)


class GradeProbabilityRange(BaseModel):
    """The honest headline: a likely grade *band*, plus P(grade ≥ floor) — never one number.

    ``likely_low``/``likely_high`` bound the band the evidence supports (e.g. "8–9"); a
    poorly-read card widens it. ``p_at_least`` is the probability the true grade is at least
    ``at_least`` — the number a collector actually decides on ("70% chance it's a 9 or
    better, so worth the submission fee"). There is intentionally no ``grade`` field.
    """

    model_config = ConfigDict(frozen=True)

    likely_low: int = Field(ge=1, le=10)
    likely_high: int = Field(ge=1, le=10)
    at_least: int = Field(ge=1, le=10)
    p_at_least: float = Field(ge=0.0, le=1.0)


class PregradeRequest(BaseModel):
    """Reference to an already-uploaded capture to pre-grade, mirroring the scan contract.

    ``capture_ref`` points at the stills in object storage; the bytes are resolved by the
    service, not carried in the request (data minimization, §6). ``card_id`` optionally ties
    the result to a catalog card the user already resolved via a scan, so the pre-grade is
    persisted against it.
    """

    capture_ref: str = Field(min_length=1, max_length=512)
    card_id: str | None = Field(default=None, description="Catalog card id this capture is of, if known.")
    # The Vault holding being graded, if the pre-grade was launched from one. When set, the detected
    # condition is written back onto that holding so the Vault reflects what the app assessed.
    collection_item_id: uuid.UUID | None = Field(
        default=None, description="Vault holding to write the detected condition back to, if any."
    )

    # How many angles the capture bundle holds, mirroring the scan contract's ``image_count``.
    # The grading provider reasons about it (surface/holo defects need multiple angles), so a
    # single-frame capture caps what corners/edges/surface can claim. Defaults to one.
    image_count: int = Field(default=1, ge=1)

    # An at-capture opt-in — the first-capture prompt's "yes". Defaults off (GDPR, §3.5) and
    # carries no per-record meaning on its own: when set, the server grants the *account*, and
    # this pre-grade (and every future capture) then inherits that standing consent. The
    # record's eligibility is always the account's preference, never this flag in isolation.
    # ``consent_note`` records which copy version the opt-in was given under.
    training_consent: bool = False
    consent_note: str | None = Field(default=None, max_length=255)


class PregradeResponse(BaseModel):
    """The pre-grade result the UI renders.

    On ``estimated``: the probability range, the four sub-scores, an overall confidence, and
    the disclaimer. On ``retake``: ``reasons`` lists why the capture couldn't be graded so
    the UI can coach the next shot. Exactly one of (``probability``, ``reasons``) is the
    load-bearing payload, keyed by ``status``.
    """

    status: PregradeStatus
    disclaimer: str = PREGRADE_DISCLAIMER
    # Centering-based pre-grade is an in-house beta: it only emits a range for a clean, flat,
    # straight-on capture and refuses otherwise (it does not yet handle angled real-card art
    # robustly). The UI surfaces this as a "Beta" label so the estimate is never read as
    # authoritative. A flag, not baked into copy, so it flips off in one place once the
    # measurement is rebuilt.
    experimental: bool = True

    # Present when status == estimated.
    probability: GradeProbabilityRange | None = None
    sub_scores: list[SubScore] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # The card's estimated condition (from the grade band) and what that implies for value: the
    # near-mint guide price, and "your copy" — the guide scaled to the estimated condition. The
    # adjusted value is an estimate (standard condition discounts), shown alongside the guide so the
    # number is never opaque. ``baseline_value_eur``/``condition_adjusted_value_eur`` are present only
    # when the card was priceable (a value comp exists).
    estimated_condition: CardCondition | None = None
    baseline_value_eur: Decimal | None = None
    condition_adjusted_value_eur: Decimal | None = None

    # Present when status == retake: human-facing reasons to re-capture (e.g. glare, skew,
    # full-bleed card with no measurable border).
    reasons: list[str] | None = None
