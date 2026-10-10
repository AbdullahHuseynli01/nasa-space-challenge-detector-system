"""Shared test configuration."""

import os

# The API rate limiter (3 requests per 5 minutes by default) would block the
# test client after a few calls. app.main reads this setting at import time.
os.environ.setdefault("RATE_LIMIT_REQUESTS", "10000")


import pytest  # noqa: E402

from app.services import explanation  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_explanation_cache() -> None:
    """Each test starts without cached explanations."""

    explanation.clear_cache()
