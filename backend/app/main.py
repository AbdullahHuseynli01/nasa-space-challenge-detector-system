"""FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_local_environment
from app.middleware import RateLimitMiddleware, get_rate_limit_settings

load_local_environment()

from app.models.schemas import HealthResponse
from app.routes.analysis import router as analysis_router
from app.routes.explain import router as explain_router
from app.routes.regions import router as regions_router
from app.routes.series import router as series_router
from app.routes.trend import router as trend_router
from app.routes.trends import router as trends_router
from app.routes.variables import router as variables_router


DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
)


def get_cors_origins() -> list[str]:
    """Return explicit CORS origins from the environment or local defaults."""

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

    return origins


app = FastAPI(
    title="NASA Sea-Ice Trend API",
    description="Backend API for NASA sea-ice time-series data.",
    version="0.1.0",
)

rate_limit_requests, rate_limit_window = get_rate_limit_settings()
app.add_middleware(
    RateLimitMiddleware,
    requests=rate_limit_requests,
    window_seconds=rate_limit_window,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
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
