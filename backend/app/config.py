"""Backend-only loading of local environment configuration."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]


def load_local_environment() -> None:
    """Load the ignored backend/.env without overriding real environment vars."""

    load_dotenv(BACKEND_DIR / ".env", override=False)


def configure_logging() -> None:
    """Print the app's log records, from INFO up, to stdout (Render's log viewer).

    Uvicorn configures only its own loggers. Without this, the app's warnings
    reach stderr with no timestamp or level, and its info lines are dropped.
    """

    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
