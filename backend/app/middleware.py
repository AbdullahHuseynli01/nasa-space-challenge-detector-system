"""Application middleware used to protect the public API."""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a small in-memory, per-client sliding-window API limit.

    This is suitable for a single backend process. A shared Redis limiter should
    be used when the service is scaled to multiple processes or instances.
    """

    def __init__(self, app: Callable, requests: int = 3, window_seconds: int = 300) -> None:
        super().__init__(app)
        self.requests = max(1, requests)
        self.window_seconds = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _client_key(request: Request) -> str:
        # Only trust X-Forwarded-For when explicitly enabled by the deployment.
        if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Keep health checks and documentation available to monitoring/tools.
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        now = time.monotonic()
        key = self._client_key(request)
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.requests:
                retry_after = max(1, int(hits[0] + self.window_seconds - now + 0.999))
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
                    },
                )
            hits.append(now)
            remaining = self.requests - len(hits)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.window_seconds))
        return response


def get_rate_limit_settings() -> tuple[int, int]:
    """Read rate-limit settings from environment with safe defaults."""

    return (
        int(os.getenv("RATE_LIMIT_REQUESTS", "3")),
        int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300")),
    )
