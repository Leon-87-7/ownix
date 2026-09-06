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
    "EMAIL_WEBHOOK_SECRET": "test-email-secret",
    "REDIS_URL": "redis://localhost:6379/0",
    "DB_PATH": ":memory:",
    "LOG_LEVEL": "WARNING",
}

for key, value in _TEST_ENV.items():
    os.environ[key] = value

_FIXTURE_DOCS = Path(__file__).parent / "fixtures" / "docs"

# Minimal one-page PDF whose content stream draws the text "Hello Vig". Shared by
# the liteparse wrapper tests and the format-router tests so the tiny-PDF constant
# lives in exactly one place.
TINY_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 24 Tf 20 100 Td (Hello Vig) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R/Size 6>>
%%EOF"""


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """`src.intake.rate_limit` is a shared in-process dict keyed by caller id.

    `create_and_enqueue_job` (src/services/jobs.py) now enforces it on every
    job creation, so without a reset here, unrelated tests that create several
    jobs for the same chat_id in a fast test run could trip each other's
    window and start seeing spurious 429s."""
    from src.intake import rate_limit

    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def tiny_pdf() -> bytes:
    """A minimal valid one-page PDF containing the text 'Hello Vig'."""
    return TINY_PDF


@pytest.fixture
def office_samples() -> dict[str, bytes]:
    """Real (tiny) office/CSV documents for multi-format parse/intake tests
    (ADR-0023). Committed as binary fixtures so no office-generator dev dep is
    needed. Keyed by filename, e.g. office_samples['report.docx']."""
    return {p.name: p.read_bytes() for p in sorted(_FIXTURE_DOCS.iterdir()) if p.is_file()}
