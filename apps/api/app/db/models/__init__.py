"""ORM models for the Holofy domain.

Importing this package registers every mapper on ``Base.metadata`` — which is what
Alembic autogenerate and the test schema bootstrap both rely on, so they must all be
re-exported here.
"""

from __future__ import annotations

from app.db.models.card import Card
from app.db.models.collection import CollectionItem
from app.db.models.enums import (
    CardCondition,
    PriceBasis,
    PriceSource,
    ScanOutcome,
    Variant,
)
from app.db.models.portfolio import PortfolioSnapshot
from app.db.models.price import PriceObservation
from app.db.models.scan import ScanRecord
from app.db.models.user import User

__all__ = [
    "Card",
    "CardCondition",
    "CollectionItem",
    "PortfolioSnapshot",
    "PriceBasis",
    "PriceObservation",
    "PriceSource",
    "ScanOutcome",
    "ScanRecord",
    "User",
    "Variant",
]
