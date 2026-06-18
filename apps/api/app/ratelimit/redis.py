"""Redis-backed daily rate limiter — the cross-instance drop-in for the fleet.

Same Protocol and semantics as the in-process limiter, but the counter lives in Redis so
every API instance shares one quota. ``check_and_consume`` is a single Lua script so the
read, the limit test, and the increment are atomic under concurrency across instances — a
GET-then-INCR split would race and let a user slip past the limit. The per-``(key, UTC day)``
counter is given a TTL to the window boundary, so it expires on its own with no sweep.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from redis.asyncio import Redis

from app.ratelimit.base import QuotaWindow

_DAY = timedelta(days=1)

# Increments only while within the limit; a denied call consumes nothing. Sets the TTL on the
# first hit of a new window. Returns {allowed (0/1), count_after_this_call}.
_CONSUME_SCRIPT = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
if used >= tonumber(ARGV[1]) then
  return {0, used}
end
local now = redis.call('INCR', KEYS[1])
if now == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return {1, now}
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seconds_until_next_utc_day(now: datetime) -> int:
    next_midnight = datetime.combine(now.date() + _DAY, time.min, tzinfo=timezone.utc)
    return int((next_midnight - now).total_seconds())


class RedisRateLimiter:
    def __init__(self, client: Redis, *, namespace: str = "ratelimit") -> None:
        self._redis = client
        self._namespace = namespace
        self._consume = client.register_script(_CONSUME_SCRIPT)

    async def check_and_consume(self, key: str, *, limit: int) -> QuotaWindow:
        now = _now()
        reset_seconds = _seconds_until_next_utc_day(now)
        # Key includes the UTC-day ordinal so a new window starts at the boundary; the TTL
        # then garbage-collects the previous day's counter.
        redis_key = f"{self._namespace}:{key}:{now.toordinal()}"
        allowed_flag, used = await self._consume(keys=[redis_key], args=[limit, reset_seconds])
        allowed = bool(allowed_flag)
        remaining = limit - int(used) if allowed else 0
        return QuotaWindow(
            allowed=allowed,
            limit=limit,
            remaining=max(remaining, 0),
            reset_seconds=reset_seconds,
        )

    async def aclose(self) -> None:
        await self._redis.aclose()
