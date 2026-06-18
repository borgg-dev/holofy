"""Authenticity request/response contract — a private risk flag, never a "FAKE" verdict.

The defamation guardrail (charter §3.5, architecture §3.3) is encoded in the *types* here,
not left to prose or UI copy:

- The headline is a ``RiskBand`` — ``strong_signals`` / ``inconclusive`` / ``elevated_risk``
  — deliberately *not* a boolean. There is no ``is_fake`` / ``is_genuine`` field anywhere
  in this module, and no value an "authentic ✓ certificate" could be rendered from. The most
  adverse band the service can emit is "elevated risk, seek professional authentication".
- Every result carries ``disclaimer`` semantics: this is a private screening signal for the
  card's owner to decide whether to pay for expert authentication — not an accusation, a
  determination, or a public claim about a card or a seller.
- A capture too poor to read, or a card too cheap to be worth faking, does not get a
  fake-precise score: the outcome is ``retake`` (re-capture) or ``not_assessed`` (below the
  value threshold) — typed states, not a confident wrong answer.

Per-signal reads (print pattern, holo signature, font/layout, cardstock) surface as
``AuthenticitySignal`` (an observation band + confidence), bought/built behind the
``AuthenticityProvider`` seam and mocked for now.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Framed as decision support for the owner, never as a verdict about the card or a seller.
AUTHENTICITY_DISCLAIMER = (
    "Private authenticity screening, not a verdict. This is a risk signal to help you "
    "decide whether to pay for professional authentication — it is not a determination "
    "that a card is genuine or counterfeit, and it is not an assessment of any seller."
)


class SignalKind(StrEnum):
    """The per-signal authenticity reads, mirroring architecture §3.3.

    Each is an independent visual cue; the service composes them with the catalog
    cross-check into a risk band. No single signal is a verdict on its own.
    """

    PRINT_PATTERN = "print_pattern"  # CMYK rosette / dot pattern at magnification
    HOLO_SIGNATURE = "holo_signature"  # foil reflectance across tilt angles
    FONT_LAYOUT = "font_layout"  # typography / layout deviation vs reference
    CARDSTOCK = "cardstock"  # texture / stock / edge cues
    CATALOG_EXISTENCE = "catalog_existence"  # was this (set, number, variant, era) ever printed


class SignalObservation(StrEnum):
    """What a single signal read says about authenticity — never a verdict, a *consistency*.

    ``consistent`` — the read matches a genuine reference. ``deviation`` — it diverges from
    the reference in a way fakes characteristically do. ``unreadable`` — the capture couldn't
    support this signal (so it widens uncertainty rather than counting as either).
    """

    CONSISTENT = "consistent"
    INCONCLUSIVE = "inconclusive"
    DEVIATION = "deviation"
    UNREADABLE = "unreadable"


class RiskBand(StrEnum):
    """The composite authenticity read — a band, deliberately never a boolean.

    ``strong_signals`` — the evidence is consistent with a genuine card (the most reassuring
    we will say; *not* "genuine"). ``inconclusive`` — mixed or insufficient evidence.
    ``elevated_risk`` — signals diverge from a genuine reference; recommend professional
    authentication. There is intentionally no "counterfeit" / "fake" band (charter §3.5).
    """

    STRONG_SIGNALS = "strong_signals"
    INCONCLUSIVE = "inconclusive"
    ELEVATED_RISK = "elevated_risk"


class AuthenticityStatus(StrEnum):
    """Terminal state of an authenticity assessment.

    ``assessed`` — a risk band was produced. ``retake`` — the capture was too poor to read
    the signals honestly. ``not_assessed`` — the card's value is below the threshold where
    authenticity screening is meaningful (cheap commons aren't faked), so no score is offered.
    """

    ASSESSED = "assessed"
    RETAKE = "retake"
    NOT_ASSESSED = "not_assessed"


class AuthenticitySignal(BaseModel):
    """One authenticity signal: an observation band plus how confidently it was read.

    ``confidence`` rates how trustworthy *this read* is (capture quality, model certainty),
    kept separate from the observation so an ``unreadable`` or low-confidence signal widens
    the composite's uncertainty rather than being scored as evidence either way.
    """

    model_config = ConfigDict(frozen=True)

    kind: SignalKind
    observation: SignalObservation
    confidence: float = Field(ge=0.0, le=1.0)
    # Human-facing note for the owner — what was looked at, never an accusation.
    detail: str


class AuthenticityRequest(BaseModel):
    """Reference to an already-uploaded capture to screen, plus the card it is of.

    ``capture_ref`` points at the stills in object storage; the bytes are resolved by the
    service, not carried in the request (data minimization, §6). ``card_id`` is the catalog
    card the capture was resolved to — required, because the catalog-existence cross-check and
    the value-threshold gate both need a resolved identity to be meaningful.
    """

    capture_ref: str = Field(min_length=1, max_length=512)
    card_id: str = Field(min_length=1, description="Catalog card id this capture was resolved to.")


class AuthenticityAssessment(BaseModel):
    """The composite read on the assessed path: a band, the signals behind it, confidence.

    ``recommend_authentication`` is the actionable output above the value threshold — a
    prompt to seek a professional, never a claim about the card. ``reference_value_eur`` is
    the value that put the card over the screening threshold, surfaced so the recommendation
    is legible ("worth £X — worth authenticating").
    """

    model_config = ConfigDict(frozen=True)

    risk_band: RiskBand
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[AuthenticitySignal]
    recommend_authentication: bool
    reference_value_eur: float | None = None


class AuthenticityResponse(BaseModel):
    """The authenticity result the UI renders.

    Exactly one of (``assessment``, ``reasons``) is the load-bearing payload, keyed by
    ``status``: an ``assessed`` carries the band and signals; a ``retake`` carries why to
    re-capture; a ``not_assessed`` carries why screening was skipped (value below threshold).
    There is no field anywhere that asserts a card is fake or genuine.
    """

    status: AuthenticityStatus
    disclaimer: str = AUTHENTICITY_DISCLAIMER

    # Present when status == assessed.
    assessment: AuthenticityAssessment | None = None

    # Present when status == retake (capture too poor) or not_assessed (below value threshold).
    reasons: list[str] | None = None
