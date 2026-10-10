"""Unit tests for the in-memory rate limiter."""

import pytest
from starlette.types import Receive, Scope, Send

from app.middleware import RateLimitMiddleware


async def _downstream(scope: Scope, receive: Receive, send: Send) -> None:
    """The limiter's logic is tested directly; this app is never called."""


def _limiter(**kwargs: int) -> RateLimitMiddleware:
    return RateLimitMiddleware(_downstream, **kwargs)


def test_expired_clients_are_pruned() -> None:
    limiter = _limiter(requests=3, window_seconds=60)
    start = limiter._last_prune

    limiter._register("one-time-visitor", start + 1)
    limiter._register("recent-visitor", start + 50)
    limiter._register("new-visitor", start + 70)  # a full window later: prune runs

    assert set(limiter._hits) == {"recent-visitor", "new-visitor"}


def test_client_table_never_exceeds_max_clients() -> None:
    limiter = _limiter(requests=3, window_seconds=300, max_clients=3)
    start = limiter._last_prune

    for index in range(10):
        limiter._register(f"client-{index}", start + index)

    assert list(limiter._hits) == ["client-7", "client-8", "client-9"]


def test_sliding_window_blocks_then_recovers() -> None:
    limiter = _limiter(requests=2, window_seconds=60)
    start = limiter._last_prune

    assert limiter._register("visitor", start).allowed
    assert limiter._register("visitor", start + 1).remaining == 0

    blocked = limiter._register("visitor", start + 2)
    assert not blocked.allowed
    assert blocked.reset_after == pytest.approx(58)

    assert limiter._register("visitor", start + 61).allowed
