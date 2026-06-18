"""In-process daily rate limiter.

Counts per ``(key, UTC day)`` in a dict, guarded by a lock so concurrent requests in the
same event loop can't double-count or skip the limit. Correct for a single process; it is
*not* shared across instances — that is the Redis backend's job (same Protocol). The day
boundary is UTC so the reset is deterministic regardless of the user's timezone.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone

from app.ratelimit.base import QuotaWindow

_DAY = timedelta(days=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_until_next_utc_day(now: datetime) -> int:
    next_midnight = datetime.combine(now.date() + _DAY, time.min, tzinfo=timezone.utc)
    return int((next_midnight - now).total_seconds())


class InMemoryRateLimiter:
    def __init__(self) -> None:
        # (key, ordinal day) -> units consumed. Keying on the day ordinal makes a new window
        # start automatically at the UTC boundary without a sweep.
        self._counts: dict[tuple[str, int], int] = {}
        self._lock = asyncio.Lock()

    async def check_and_consume(self, key: str, *, limit: int) -> QuotaWindow:
        now = _now()
        window_key = (key, now.toordinal())
        reset_seconds = _seconds_until_next_utc_day(now)
        async with self._lock:
            used = self._counts.get(window_key, 0)
            if used >= limit:
                return QuotaWindow(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_seconds=reset_seconds,
                )
            self._counts[window_key] = used + 1
            return QuotaWindow(
                allowed=True,
                limit=limit,
                remaining=limit - used - 1,
                reset_seconds=reset_seconds,
            )
