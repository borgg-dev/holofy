"""Typed async data-access layer.

Every database query the services need lives in one of these repositories; the API and
service layers depend on them and never issue SQL or touch the ORM session's query API
directly. Each repository is constructed with an ``AsyncSession`` and owns the queries for
one aggregate.
"""

from __future__ import annotations

from app.db.repositories.authenticity import AuthenticityRepository
from app.db.repositories.card import CardRepository
from app.db.repositories.collection import CollectionRepository
from app.db.repositories.portfolio import PortfolioRepository
from app.db.repositories.pregrade import PreGradeRepository
from app.db.repositories.price import PriceRepository
from app.db.repositories.scan import ScanRepository
from app.db.repositories.user import UserRepository

__all__ = [
    "AuthenticityRepository",
    "CardRepository",
    "CollectionRepository",
    "PortfolioRepository",
    "PreGradeRepository",
    "PriceRepository",
    "ScanRepository",
    "UserRepository",
]
