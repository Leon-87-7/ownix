"""Pytest config — sets test env vars BEFORE any src.* module is imported.

The `Settings()` class is instantiated at module load (`src/config.py`), so any test
that imports a `src.*` module triggers env-var validation. Setting test values here
guarantees they're present regardless of what's in the developer's local `.env`.
"""

import os
from pathlib import Path

import pytest

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

_FIXTURE_DOCS = Path(__file__).parent / "fixtures" / "docs"


@pytest.fixture
def office_samples() -> dict[str, bytes]:
    """Real (tiny) office/CSV documents for multi-format parse/intake tests
    (ADR-0023). Committed as binary fixtures so no office-generator dev dep is
    needed. Keyed by filename, e.g. office_samples['report.docx']."""
    return {p.name: p.read_bytes() for p in sorted(_FIXTURE_DOCS.iterdir()) if p.is_file()}
