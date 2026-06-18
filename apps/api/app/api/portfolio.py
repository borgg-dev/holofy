"""Portfolio endpoints — current total €, a snapshot write, and the value-over-time series.

All scoped to the bearer-resolved user. ``GET /portfolio`` is the live total; ``POST
/portfolio/snapshots`` pins that total into the append-only history; ``GET
/portfolio/snapshots`` reads the series back for the chart.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_portfolio_service
from app.db.models import User
from app.schemas.portfolio import PortfolioHistoryResponse, PortfolioTotal
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioTotal)
async def get_portfolio(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioTotal:
    return await service.total(user.id)


@router.post(
    "/snapshots",
    response_model=PortfolioTotal,
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio_snapshot(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioTotal:
    return await service.snapshot(user.id)


@router.get("/snapshots", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
    limit: int | None = Query(default=None, ge=1, le=365),
) -> PortfolioHistoryResponse:
    return await service.history(user.id, limit=limit)
