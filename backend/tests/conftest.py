"""Shared test configuration."""

import os

# The API rate limiter (3 requests per 5 minutes by default) would block the
# test client after a few calls. app.main reads this setting at import time.
os.environ.setdefault("RATE_LIMIT_REQUESTS", "10000")
