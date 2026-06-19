"""Short-window brute-force throttle for the auth endpoints.

The app's main rate limiter is a *daily* COGS quota — useless against online password
guessing, which needs a tight rolling window. This is a small, dependency-free fixed-window
counter for ``/auth/login`` and ``/auth/register``: it caps attempts per key (a client IP, and
the target email) over a short window, so credential-stuffing and account-enumeration probes
are stopped after a handful of tries while a legitimate user who fat-fingers a password is not.

In-memory, so it is **per-instance** — correct for the single-box test deployment. For a
multi-instance fleet this moves behind the shared (Redis) limiter, exactly like the daily
quota; the call sites won't change.
"""

from __future__ import annotations

import time
from collections import defaultdict


class InMemoryAuthThrottle:
    """Fixed-window attempt counter keyed by an opaque string (IP or email)."""

    def __init__(self) -> None:
        # key -> (window_start_epoch, count)
        self._windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Record one attempt against ``key`` and report whether it's within the window's
        budget. A denied attempt is still counted, so hammering can't reset the window."""
        now = time.monotonic()
        start, count = self._windows[key]
        if now - start >= window_seconds:
            # Window rolled over — start a fresh one with this attempt.
            self._windows[key] = (now, 1)
            return True
        if count >= limit:
            return False
        self._windows[key] = (start, count + 1)
        return True

    def reset(self, key: str) -> None:
        """Clear a key's window — e.g. after a *successful* login, so a user isn't penalised
        for earlier typos once they get it right."""
        self._windows.pop(key, None)
