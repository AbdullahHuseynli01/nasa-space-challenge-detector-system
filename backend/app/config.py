"""Backend-only loading of local environment configuration."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]


def load_local_environment() -> None:
    """Load the ignored backend/.env without overriding real environment vars."""

    load_dotenv(BACKEND_DIR / ".env", override=False)

