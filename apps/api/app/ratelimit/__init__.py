"""Per-user quota enforcement.

The scan path is the COGS lever (each cloud scan costs real money), so the free tier is
capped per day. A ``RateLimiter`` is the seam: the in-memory backend here is correct for a
single process, and a Redis backend — sharing counters across instances behind a load
balancer — drops in behind the same Protocol for production.
"""

from __future__ import annotations

from app.ratelimit.base import QuotaWindow, RateLimiter
from app.ratelimit.factory import build_rate_limiter
from app.ratelimit.memory import InMemoryRateLimiter

__all__ = [
    "InMemoryRateLimiter",
    "QuotaWindow",
    "RateLimiter",
    "build_rate_limiter",
]
