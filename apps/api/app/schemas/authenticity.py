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


class SignalDetail(StrEnum):
    """The closed vocabulary a per-signal ``detail`` may carry — neutral phrases only.

    The defamation guardrail (§3.5) blocks an accusatory *band* structurally, but a free-text
    ``detail`` could still smuggle an accusatory *sentence* past the type system ("this is a
    counterfeit"). So ``detail`` is not a free string: it is one of these reviewed phrases.
    A real provider (a CV ensemble) can only *select* from this set — it physically cannot
    author an accusation, because there is no value here that asserts a card is fake.

    Each phrase describes what was *observed against the reference* and, where adverse, frames
    the next step as "worth professional authentication" — never a determination. The members
    are grouped by signal so a provider's read maps to one option per (kind, observation).
    """

    # Print pattern (CMYK rosette / dot gain vs the reference print run).
    PRINT_MATCHES_REFERENCE = "Print pattern is consistent with the reference for this card."
    PRINT_DIFFERS_FROM_REFERENCE = (
        "Print pattern differs from the reference — worth a closer look by a professional."
    )
    PRINT_TOO_COARSE_TO_READ = "The capture can't resolve the print pattern closely enough to compare."

    # Holo signature (foil reflectance across tilt angles).
    HOLO_MATCHES_REFERENCE = "Foil behaviour across angles is consistent with the reference."
    HOLO_DIFFERS_FROM_REFERENCE = (
        "Foil behaviour differs from the reference — worth a closer look by a professional."
    )
    HOLO_NEEDS_MORE_ANGLES = "Too few tilt angles were captured to read the foil behaviour."

    # Font / layout (typography weight, kerning, element placement vs the reference).
    LAYOUT_MATCHES_REFERENCE = "Typography and layout are consistent with the reference."
    LAYOUT_DIFFERS_FROM_REFERENCE = (
        "Typography or layout differs from the reference — worth a closer look by a professional."
    )
    LAYOUT_WITHIN_TOLERANCE = "Typography is close to the reference; any differences are within capture tolerance."
    LAYOUT_OBSCURED = "Glare or framing obscures the text, so the layout can't be compared confidently."

    # Cardstock (edge cross-section, surface texture, stock).
    STOCK_MATCHES_REFERENCE = "Edge and surface texture are consistent with the reference stock."
    STOCK_DIFFERS_FROM_REFERENCE = (
        "Edge or surface texture differs from the reference stock — worth a closer look by a professional."
    )
    STOCK_OUT_OF_FRAME = "The card edges are out of frame, so the stock and texture can't be assessed."

    # Catalog cross-check (the resolved set/number/variant tuple vs the reference catalog).
    CATALOG_PRINTING_CONFIRMED = "This set, number and variant matches a printing in the reference catalog."
    CATALOG_PRINTING_NOT_FOUND = (
        "No printing of this set and number was issued in this variant — worth professional authentication."
    )
    CATALOG_NO_COVERAGE = (
        "The reference catalog has no coverage to confirm this printing — a gap in our data, "
        "not a finding about the card."
    )


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
    # Human-facing note for the owner, drawn from a closed, reviewed vocabulary — never a
    # free string a provider could author an accusation in (§3.5). See ``SignalDetail``.
    detail: SignalDetail


class AuthenticityRequest(BaseModel):
    """Reference to an already-uploaded capture to screen, plus the card it is of.

    ``capture_ref`` points at the stills in object storage; the bytes are resolved by the
    service, not carried in the request (data minimization, §6). ``card_id`` is the catalog
    card the capture was resolved to — required, because the catalog-existence cross-check and
    the value-threshold gate both need a resolved identity to be meaningful.
    """

    capture_ref: str = Field(min_length=1, max_length=512)
    card_id: str = Field(min_length=1, description="Catalog card id this capture was resolved to.")

    # How many angles the capture bundle holds, mirroring the scan contract's ``image_count``.
    # The provider reasons about it (the holo signature needs multiple tilt angles), so a
    # single-frame capture caps what that signal can claim. Defaults to one.
    image_count: int = Field(default=1, ge=1)

    # An at-capture opt-in — the first-capture prompt's "yes". Defaults off (GDPR, §3.5) and
    # carries no per-record meaning on its own: when set, the server grants the *account*, and
    # this screen (and every future capture) then inherits that standing consent. The record's
    # eligibility is always the account's preference, never this flag in isolation.
    # ``consent_note`` records which copy version the opt-in was given under.
    training_consent: bool = False
    consent_note: str | None = Field(default=None, max_length=255)


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
