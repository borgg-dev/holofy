"""Rate-limiter selection by configuration.

The limiter is built once per process (the in-memory backend *is* its own store), so the
lifespan keeps the singleton and hands it to every request via the dependency.
"""

from __future__ import annotations

from app.config import RateLimitBackend, Settings
from app.ratelimit.base import RateLimiter
from app.ratelimit.memory import InMemoryRateLimiter


def build_rate_limiter(settings: Settings) -> RateLimiter:
    match settings.rate_limit_provider:
        case RateLimitBackend.MEMORY:
            return InMemoryRateLimiter()
        case RateLimitBackend.REDIS:
            # Imported lazily so the in-memory default never requires the redis client.
            from redis.asyncio import Redis

            from app.ratelimit.redis import RedisRateLimiter

            return RedisRateLimiter(Redis.from_url(settings.redis_url))
        case _:
            raise ValueError(f"unsupported rate_limit_provider: {settings.rate_limit_provider}")
