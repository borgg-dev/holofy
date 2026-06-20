"""Domain DTOs shared across providers and the API layer.

These are the canonical shapes the scan pipeline passes between stages. The deliberate
split: ``CardIdentity`` is what recognition *resolves to* (set, number, language, variant
— the disambiguation tuple), and ``canonical_id`` is the single string key the pricing
provider consumes. Keeping pricing keyed on one id keeps recognition swappable without
the pricing side caring how identity was determined.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Variant(StrEnum):
    """Printing variants that move price independently for the same artwork."""

    NORMAL = "normal"
    HOLO = "holo"
    REVERSE_HOLO = "reverse_holo"
    FIRST_EDITION = "first_edition"
    PROMO = "promo"


class CardGame(BaseModel):
    """The game/category a card belongs to — an *open* category, deliberately not an enum.

    ``id`` is a stable slug recognition emits (``pokemon``, ``lorcana``, ``one_piece``);
    ``name`` is its nominative label (``Pokémon``). The client groups the Vault on ``id`` and
    never consults a fixed list, so adding a game later is a *data* change, not a code change.
    Holofy launches Pokémon-only, so identity defaults this to Pokémon until the recognizer
    resolves other games behind the same field.
    """

    model_config = ConfigDict(frozen=True)

    id: str = "pokemon"
    name: str = "Pokémon"


# The launch game. A shared frozen instance is safe to reuse as a default — it is immutable.
POKEMON = CardGame(id="pokemon", name="Pokémon")


class CardIdentity(BaseModel):
    """A resolved card identity — the ``(set, collector number, variant)`` tuple plus the
    language that, together, disambiguate same-art reprints (see ADR 0002).
    """

    model_config = ConfigDict(frozen=True)

    # The pricing key. For the TCGdex-backed catalog this is the ``<set>-<localId>`` id,
    # e.g. ``origins-12``. Providers must agree on this scheme; recognition emits it.
    canonical_id: str
    # The game this card belongs to — the Vault groups on it. Defaults to Pokémon (the launch
    # game); a multi-game recognizer sets it per card with no change to any call site.
    game: CardGame = Field(default_factory=lambda: POKEMON)
    name: str
    set_name: str
    collector_number: str
    language: str
    variant: Variant
    # Absolute URL of the card's catalog artwork (TCGdex), for the client to render the real
    # card face. ``None`` when the catalog has no image for the printing (the client falls back
    # to the foil placeholder), so it never blocks recognition.
    image_url: str | None = None


class RecognitionCandidate(BaseModel):
    """One hypothesis from recognition, with the confidence that drives the confirm step."""

    model_config = ConfigDict(frozen=True)

    identity: CardIdentity
    confidence: float = Field(ge=0.0, le=1.0)


class RecognitionResult(BaseModel):
    """The ordered candidate set for one capture bundle.

    ``candidates`` is sorted by descending confidence. When the top candidate clears the
    configured threshold the flow may commit it; otherwise the UI must surface the top-2
    with their price delta and let the user confirm — never silently guess a high-value
    variant.
    """

    candidates: list[RecognitionCandidate]

    @property
    def top(self) -> RecognitionCandidate:
        return self.candidates[0]

    def needs_confirmation(self, threshold: float) -> bool:
        return self.top.confidence < threshold


class PriceQuote(BaseModel):
    """A priced reading for a canonical card, with provenance and freshness.

    Honest framing (charter §3.1): we expose the source and the data's age so the client
    can show how fresh and from where the value came, rather than implying a live quote.
    """

    model_config = ConfigDict(frozen=True)

    canonical_id: str
    currency: str = "EUR"
    value: Decimal | None
    basis: str
    low: Decimal | None = None
    avg30: Decimal | None = None
    source: str
    as_of: datetime
    age_hours: float
    listing_url: str | None = None
