"""Enumerations persisted as portable strings.

These mirror the values of the API-layer enums (``app.schemas.cards.Variant``,
``app.schemas.scan.ScanOutcome``) by *value*, deliberately without importing them: the
persistence layer must not depend on the API DTOs, and the on-disk vocabulary needs to
stay stable even if a DTO is reshaped. They are stored as ``String`` rather than a native
DB ``ENUM`` so adding a value is a code change, not a Postgres ``ALTER TYPE`` migration,
and so the column behaves identically on SQLite.
"""

from __future__ import annotations

from enum import StrEnum


class Variant(StrEnum):
    """Printing variants that price independently for the same artwork."""

    NORMAL = "normal"
    HOLO = "holo"
    REVERSE_HOLO = "reverse_holo"
    FIRST_EDITION = "first_edition"
    PROMO = "promo"


class CardCondition(StrEnum):
    """Cardmarket condition grades — the scale EU collectors price against.

    ``NOT_ASSESSED`` is the honest default for a freshly *scanned* card: the scan identifies the
    card, it does not judge its condition. A card is only assigned a real condition once the user
    pre-grades it (a deliberate, multi-angle look). So the Vault shows "not assessed" + the market
    guide until then, never a near-mint claim nothing measured.
    """

    NOT_ASSESSED = "not_assessed"
    MINT = "mint"
    NEAR_MINT = "near_mint"
    EXCELLENT = "excellent"
    GOOD = "good"
    LIGHT_PLAYED = "light_played"
    PLAYED = "played"
    POOR = "poor"


class ScanOutcome(StrEnum):
    """Terminal state of a scan event."""

    RESOLVED = "resolved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNRECOGNIZED = "unrecognized"


class PregradeStatus(StrEnum):
    """Terminal state of a pre-grade event.

    ``estimated`` — a grade probability range was produced. ``retake`` — the capture was too
    poor to estimate honestly and the user was asked to re-capture.
    """

    ESTIMATED = "estimated"
    RETAKE = "retake"


class AuthenticityStatus(StrEnum):
    """Terminal state of an authenticity assessment.

    ``assessed`` — a risk band was produced. ``retake`` — the capture was too poor to read
    the signals honestly. ``not_assessed`` — the card's value was below the screening
    threshold (cheap commons aren't faked), so no score was offered.
    """

    ASSESSED = "assessed"
    RETAKE = "retake"
    NOT_ASSESSED = "not_assessed"


class AuthenticityRiskBand(StrEnum):
    """The composite authenticity read — a band, deliberately never a fake/genuine boolean.

    ``strong_signals`` — evidence consistent with a genuine card. ``inconclusive`` — mixed
    or insufficient. ``elevated_risk`` — diverges from a genuine reference; seek expert
    authentication. There is intentionally no "counterfeit" value (charter §3.5).
    """

    STRONG_SIGNALS = "strong_signals"
    INCONCLUSIVE = "inconclusive"
    ELEVATED_RISK = "elevated_risk"


class PriceSource(StrEnum):
    """Provenance of a price point — which feed it came from."""

    CARDMARKET = "cardmarket"
    TCGPLAYER = "tcgplayer"
    TCGDEX = "tcgdex"
    MOCK = "mock"


class PriceBasis(StrEnum):
    """Which statistic a price value represents, so a low isn't compared to a trend."""

    TREND = "trend"
    AVG_30D = "avg_30d"
    AVG_7D = "avg_7d"
    LOW = "low"
