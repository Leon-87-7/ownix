"""Pytest config — sets test env vars BEFORE any src.* module is imported.

The `Settings()` class is instantiated at module load (`src/config.py`), so any test
that imports a `src.*` module triggers env-var validation. Setting test values here
guarantees they're present regardless of what's in the developer's local `.env`.
"""

import os

# Force the test environment; ignore any real `.env` values that might leak in.
_TEST_ENV = {
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "REDIS_URL": "redis://localhost:6379/0",
    "DB_PATH": ":memory:",
    "LOG_LEVEL": "WARNING",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value
