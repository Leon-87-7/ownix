"""Unit tests for src/services/gemini_client.py — no real API calls."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.gemini_client import GeminiClient, GeminiUnavailableError, gemini_client


# ---------------------------------------------------------------------------
# Test 1: Single key success — generate() returns the canned string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_single_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _call_sync returns a canned string, generate() returns it."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch.object(GeminiClient, "_call_sync", return_value='{"result": "ok"}'):
        result = await gemini_client.generate("Hello", model="gemini-2.5-flash")

    assert result == '{"result": "ok"}'


# ---------------------------------------------------------------------------
# Test 2: Both keys fail → GeminiUnavailableError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_both_keys_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _call_sync always raises, generate() raises GeminiUnavailableError."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    with patch.object(GeminiClient, "_call_sync", side_effect=RuntimeError("network error")):
        with pytest.raises(GeminiUnavailableError):
            await gemini_client.generate("Hello", model="gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Test 3: First key fails, second succeeds — result from second key returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_first_key_fails_second_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """When first key fails and second succeeds, the successful result is returned."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    call_count = 0

    def _fake_call_sync(
        prompt: str, api_key: str, model: str, schema: type | dict | None
    ) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("free key quota exceeded")
        return '{"result": "paid key success"}'

    with patch.object(GeminiClient, "_call_sync", side_effect=_fake_call_sync):
        result = await gemini_client.generate("Hello", model="gemini-2.5-flash")

    assert result == '{"result": "paid key success"}'
    assert call_count == 2


# ---------------------------------------------------------------------------
# Test 4: Schema is passed to _call_sync when provided
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_passes_schema_to_call_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """When schema is provided, _call_sync receives it as the schema argument."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    received: list[dict] = []

    def _spy(prompt: str, api_key: str, model: str, schema: type | dict | None) -> str:
        received.append({"schema": schema})
        return '{"ok": true}'

    my_schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    with patch.object(GeminiClient, "_call_sync", side_effect=_spy):
        result = await gemini_client.generate(
            "Hello", model="gemini-2.5-flash", schema=my_schema
        )

    assert result == '{"ok": true}'
    assert len(received) == 1
    assert received[0]["schema"] == my_schema


# ---------------------------------------------------------------------------
# Test 5: No keys configured → GeminiUnavailableError (no calls attempted)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_no_keys_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both keys are empty strings, generate() raises GeminiUnavailableError."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch.object(GeminiClient, "_call_sync", side_effect=AssertionError("should not be called")):
        with pytest.raises(GeminiUnavailableError):
            await gemini_client.generate("Hello", model="gemini-2.5-flash")
