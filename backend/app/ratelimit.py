"""Small in-memory sliding-window rate limiter (one backend instance).

If we ever run several instances, move this to Postgres or Redis (ask first: new service).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.audit import client_ip
from app.logging_setup import get_logger

log = get_logger("pr_summary.ratelimit")


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, max_hits: int, window_s: float, now: float | None = None) -> bool:
        """Record a hit; return False if the key is over its limit."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            if len(q) >= max_hits:
                return False
            q.append(now)
            return True

    def count(self, key: str, window_s: float, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            return len(q)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


TOO_MANY = "Too many attempts. Wait a few minutes and try again."


def limit(request: Request, bucket: str, max_hits: int, window_s: float, extra: str = "") -> None:
    limiter: RateLimiter = request.app.state.limiter
    key = f"{bucket}:{client_ip(request)}:{extra}"
    if not limiter.hit(key, max_hits, window_s):
        log.warning("rate_limited", bucket=bucket)
        raise HTTPException(status_code=429, detail=TOO_MANY)
