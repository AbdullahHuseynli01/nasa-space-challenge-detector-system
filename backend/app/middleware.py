"""Application middleware used to protect the public API."""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import NamedTuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


logger = logging.getLogger(__name__)

DEFAULT_MAX_CLIENTS = 10_000


class RateLimitDecision(NamedTuple):
    """Outcome of registering one request for a client."""

    allowed: bool
    remaining: int
    # Seconds until the oldest request in the window expires and frees a slot.
    reset_after: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a small in-memory, per-client sliding-window API limit.

    This is suitable for a single backend process. A shared Redis limiter should
    be used when the service is scaled to multiple processes or instances.

    Memory stays bounded: clients with no requests inside the window are pruned
    (at most once per window), and the table never holds more than
    ``max_clients`` entries, evicting the earliest-seen clients first.
    """

    def __init__(
        self,
        app: Callable,
        requests: int = 10,
        window_seconds: int = 300,
        max_clients: int = DEFAULT_MAX_CLIENTS,
    ) -> None:
        super().__init__(app)
        self.requests = max(1, requests)
        self.window_seconds = max(1, window_seconds)
        self.max_clients = max(1, max_clients)
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    @staticmethod
    def _client_key(request: Request) -> str:
        # Only trust X-Forwarded-For when explicitly enabled by the deployment.
        if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    def _prune(self, now: float) -> None:
        """Forget clients with no requests inside the window. Call with the lock held."""

        cutoff = now - self.window_seconds
        expired = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in expired:
            del self._hits[key]
        self._last_prune = now

    def _register(self, key: str, now: float) -> RateLimitDecision:
        """Record a request for ``key`` if the client still has budget."""

        with self._lock:
            if key not in self._hits:
                if now - self._last_prune >= self.window_seconds or len(self._hits) >= self.max_clients:
                    self._prune(now)
                # Still full after pruning (many distinct clients inside one
                # window): evict the earliest-seen clients to bound memory.
                while len(self._hits) >= self.max_clients:
                    del self._hits[next(iter(self._hits))]
                self._hits[key] = deque()

            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.requests:
                return RateLimitDecision(False, 0, hits[0] + self.window_seconds - now)

            hits.append(now)
            return RateLimitDecision(True, self.requests - len(hits), hits[0] + self.window_seconds - now)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Keep health checks and documentation available to monitoring/tools,
        # and never count CORS preflights against a visitor's budget.
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        decision = self._register(self._client_key(request), time.monotonic())
        reset_at = str(math.ceil(time.time() + decision.reset_after))

        if not decision.allowed:
            retry_after = max(1, math.ceil(decision.reset_after))
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please wait a moment and try again.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_at,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = reset_at
        return response


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turn unexpected exceptions into a JSON 500.

    Starlette's own error handler sits outside every middleware, so its 500
    response would skip CORS and reach the browser as a misleading CORS error.
    Added inside CORSMiddleware, this keeps the real status visible.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error for %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal server error."})


def get_rate_limit_settings() -> tuple[int, int]:
    """Read rate-limit settings from environment with safe defaults."""

    return (
        int(os.getenv("RATE_LIMIT_REQUESTS", "10")),
        int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300")),
    )
