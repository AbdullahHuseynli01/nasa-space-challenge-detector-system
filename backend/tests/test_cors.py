"""CORS behaviour of the full middleware stack, for direct browser access."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, configure_middleware

FRONTEND = "https://environmental-analytics-dashboard.vercel.app"
EXPOSED = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _preflight(client: TestClient, origin: str) -> object:
    return client.options(
        "/api/explain",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("origin", [FRONTEND, "http://localhost:3000"])
def test_preflight_from_frontend_is_allowed(client: TestClient, origin: str) -> None:
    response = _preflight(client, origin)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_preflight_from_unknown_origin_is_rejected(client: TestClient) -> None:
    response = _preflight(client, "https://unknown.example")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_responses_expose_rate_limit_headers(client: TestClient) -> None:
    response = client.get("/api/regions", headers={"Origin": FRONTEND})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    exposed = response.headers["access-control-expose-headers"].lower()
    assert all(header in exposed for header in EXPOSED)


def _small_app(requests: int) -> TestClient:
    small = FastAPI()

    @small.get("/api/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    @small.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("unexpected")

    configure_middleware(small, origins=[FRONTEND], requests=requests, window_seconds=300)
    return TestClient(small)


def test_rate_limited_response_keeps_cors_headers() -> None:
    small = _small_app(requests=1)

    assert small.get("/api/ping", headers={"Origin": FRONTEND}).status_code == 200
    response = small.get("/api/ping", headers={"Origin": FRONTEND})

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert int(response.headers["retry-after"]) > 0


def test_preflights_are_not_rate_limited() -> None:
    small = _small_app(requests=1)
    headers = {"Origin": FRONTEND, "Access-Control-Request-Method": "GET"}

    assert all(small.options("/api/ping", headers=headers).status_code == 200 for _ in range(5))
    assert small.get("/api/ping", headers={"Origin": FRONTEND}).status_code == 200


def test_unhandled_error_is_json_500_with_cors_headers() -> None:
    small = _small_app(requests=100)

    response = small.get("/api/boom", headers={"Origin": FRONTEND})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert response.headers["access-control-allow-origin"] == FRONTEND
