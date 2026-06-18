"""The rate-limiter Protocol and its result type.

``check_and_consume`` is the whole contract: it atomically records one unit against a
per-key daily window and reports whether the call is within quota, how much remains, and
when the window resets. Keeping it atomic in the interface is what lets a Redis backend be a
correct drop-in — a check-then-increment split would race across instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class QuotaWindow:
    """The outcome of consuming one unit of quota.

    ``allowed`` is the decision; ``remaining`` is how many units are left *after* this call
    (zero when denied); ``reset_seconds`` is the whole seconds until the window rolls over,
    surfaced to the client so it can show "resets in …".
    """

    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


@runtime_checkable
class RateLimiter(Protocol):
    async def check_and_consume(self, key: str, *, limit: int) -> QuotaWindow:
        """Record one unit against ``key``'s current daily window and report the verdict.

        When over quota the unit is *not* consumed (so a denied call doesn't push the reset
        further out) and ``allowed`` is ``False``.
        """
        ...
