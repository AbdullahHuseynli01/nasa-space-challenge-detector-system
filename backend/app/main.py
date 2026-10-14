"""FastAPI application entry point."""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import configure_logging, load_local_environment
from app.middleware import (
    RateLimitMiddleware,
    UnhandledErrorMiddleware,
    get_rate_limit_settings,
)

load_local_environment()
configure_logging()

from app.models.schemas import HealthResponse
from app.routes.analysis import router as analysis_router
from app.routes.explain import router as explain_router
from app.routes.regions import router as regions_router
from app.routes.series import router as series_router
from app.routes.trend import router as trend_router
from app.routes.trends import router as trends_router
from app.routes.variables import router as variables_router


# The project's own frontends: always allowed, and added to any CORS_ORIGINS.
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "https://environmental-analytics-dashboard.vercel.app",
)

CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
CORS_ALLOW_HEADERS = ["Accept", "Accept-Language", "Content-Language", "Content-Type"]
# Let a browser on another origin read the rate-limit state and retry delay.
CORS_EXPOSE_HEADERS = [
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
]
CORS_PREFLIGHT_MAX_AGE_SECONDS = 3600


def get_cors_origins() -> list[str]:
    """Return the default origins plus any extra ones from the environment.

    CORS_ORIGINS is a comma-separated list of exact origins (scheme + host, no
    path) to allow in addition to DEFAULT_CORS_ORIGINS, e.g. a custom domain.
    """

    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        environment = os.getenv("APP_ENV", "development").strip().lower()
        if environment in {"production", "prod"}:
            raise RuntimeError(
                "CORS_ORIGINS must be configured explicitly in production."
            )
        return list(DEFAULT_CORS_ORIGINS)

    origins = [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]

    if "*" in origins:
        raise ValueError("CORS_ORIGINS must contain explicit origins, not '*'")

    return list(dict.fromkeys([*DEFAULT_CORS_ORIGINS, *origins]))


def configure_middleware(
    app: FastAPI,
    *,
    origins: list[str],
    requests: int,
    window_seconds: int,
) -> None:
    """Install the middleware stack. The last one added runs first (outermost).

    CORS is outermost, so preflights are answered before rate limiting, and
    429 and 500 responses still carry CORS headers. The frontend sends no
    cookies or auth headers, so credentials stay disabled.
    """

    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        requests=requests,
        window_seconds=window_seconds,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
        expose_headers=CORS_EXPOSE_HEADERS,
        max_age=CORS_PREFLIGHT_MAX_AGE_SECONDS,
    )


app = FastAPI(
    title="NASA Sea-Ice Trend API",
    description="Backend API for NASA sea-ice time-series data.",
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 details without echoing submitted values (e.g. a stray API key)."""

    errors = [
        {key: value for key, value in error.items() if key not in {"input", "ctx"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


rate_limit_requests, rate_limit_window = get_rate_limit_settings()
configure_middleware(
    app,
    origins=get_cors_origins(),
    requests=rate_limit_requests,
    window_seconds=rate_limit_window,
)


@app.get("/", response_model=HealthResponse, tags=["health"])
def root() -> HealthResponse:
    """Return a minimal service status response."""

    return HealthResponse(status="ok", service="nasa-sea-ice-backend")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Provide a health-check endpoint for local development and deployment."""

    return HealthResponse(status="ok", service="nasa-sea-ice-backend")


app.include_router(trends_router, prefix="/api")
app.include_router(regions_router, prefix="/api")
app.include_router(variables_router, prefix="/api")
app.include_router(series_router, prefix="/api")
app.include_router(trend_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(explain_router, prefix="/api")
