"""Request/response contract for the scan endpoint.

This is the stable shape P1.4 builds the real capture→portfolio flow on. The response
deliberately models two outcomes the UI must render differently:

- ``resolved`` — one confident identity, priced.
- ``needs_confirmation`` — the top-2 same-name candidates with their € delta, so the user
  picks rather than the system silently committing a high-value variant.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.cards import CardIdentity, PriceQuote


class CaptureBundleRef(BaseModel):
    """Reference to an already-uploaded capture, not the image bytes.

    Stills land in object storage during capture; the scan call passes the bundle id the
    recognizer resolves. ``image_count`` lets the server reason about multi-angle captures
    (single-frame bundles can't support surface/holo grading) without fetching the images.
    """

    bundle_id: str = Field(min_length=1)
    image_count: int = Field(default=1, ge=1)

    # The user's language preference (ISO code from the app locale, e.g. "en"/"fr"). Optional and
    # advisory: the recognizer uses it only to break an EN·FR same-name twin tie (identical art and
    # number, e.g. "Pikachu") toward the user's market — the print the art can't distinguish but
    # their locale can. Absent ⇒ such ties honestly route to confirm.
    preferred_language: str | None = Field(default=None, max_length=8)

    # An at-capture opt-in — the first-capture prompt's "yes". Defaults off (GDPR, §3.5) and
    # carries no per-record meaning on its own: when set, the server grants the *account*, and
    # this scan (and every future one) then inherits that standing consent. The record's
    # eligibility is always the account's preference, never this flag taken in isolation.
    # ``consent_note`` records which copy version the opt-in was given under.
    training_consent: bool = False
    consent_note: str | None = Field(default=None, max_length=255)


class ScanOutcome(StrEnum):
    RESOLVED = "resolved"
    NEEDS_CONFIRMATION = "needs_confirmation"


class ScannedCard(BaseModel):
    identity: CardIdentity
    confidence: float
    price: PriceQuote | None


class ConfirmationChoice(BaseModel):
    """One option in a low-confidence confirm prompt, with the price stakes of the pick."""

    identity: CardIdentity
    confidence: float
    price: PriceQuote | None


class ScanResponse(BaseModel):
    outcome: ScanOutcome
    # Present when outcome == resolved.
    card: ScannedCard | None = None
    # Present when outcome == needs_confirmation: top-2 ordered by confidence.
    choices: list[ConfirmationChoice] | None = None
    # The € gap between the top-2 choices — the number that justifies asking the user.
    price_delta: Decimal | None = None
