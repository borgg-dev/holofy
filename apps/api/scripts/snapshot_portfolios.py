"""Daily portfolio snapshot job — pin every holder's value into the value-over-time series.

The Vault's trend chart is only as real as the points behind it, and a point only exists when a
snapshot is taken. The app records one on demand (POST /portfolio/snapshots), but a trend needs a
point a day whether or not anyone opened the app — so a scheduler runs this once daily. It values
every account that holds a card and appends today's total, idempotently: an account snapshotted
within the interval is skipped, so a re-run (or an off-schedule run) can't double-count a day.

Run inside the API container (it shares the app's DB + config):

    docker exec deploy-api-1 python scripts/snapshot_portfolios.py

Wire it to cron on the host (see deploy/README) to run nightly. Exit code is 0 on success; the
count written is logged.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.db.repositories import CardRepository, CollectionRepository, PortfolioRepository  # noqa: E402
from app.providers.factory import build_pricing_provider  # noqa: E402
from app.services.collection import CollectionService  # noqa: E402
from app.services.portfolio import PortfolioService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("snapshot_portfolios")


async def run() -> int:
    settings = Settings()
    pricing, pricing_closer = build_pricing_provider(settings)
    engine = create_engine(settings.database_url, echo=False)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            collection = CollectionService(
                cards=CardRepository(session),
                collection=CollectionRepository(session),
                pricing=pricing,
            )
            portfolio = PortfolioService(collection=collection, portfolio=PortfolioRepository(session))
            written = await portfolio.snapshot_all_due()
            await session.commit()
        log.info("portfolio snapshots written: %d", written)
        return written
    finally:
        if pricing_closer is not None and hasattr(pricing_closer, "aclose"):
            await pricing_closer.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
