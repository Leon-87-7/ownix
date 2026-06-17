"""Unit tests for the unified Gemini generate() path — no real API calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.gemini import GeminiClient, GeminiUnavailableError, gemini_client


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.text = text
    return r


# ---------------------------------------------------------------------------
# Test 1: Single key success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_single_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _call_sync returns a canned response, generate() returns its text."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch("src.services.gemini._call_sync", return_value=_make_response('{"result": "ok"}')):
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

    with patch("src.services.gemini._call_sync", side_effect=RuntimeError("network error")):
        with pytest.raises(GeminiUnavailableError):
            await gemini_client.generate("Hello", model="gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Test 3: First key fails, second succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_first_key_fails_second_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """When first key fails and second succeeds, the successful result is returned."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    call_count = 0

    def _fake(parts, *, api_key: str, model: str, schema=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("free key quota exceeded")
        return _make_response('{"result": "paid key success"}')

    with patch("src.services.gemini._call_sync", side_effect=_fake):
        result = await gemini_client.generate("Hello", model="gemini-2.5-flash")

    assert result == '{"result": "paid key success"}'
    assert call_count == 2


# ---------------------------------------------------------------------------
# Test 4: Schema is forwarded to _call_sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_passes_schema_to_call_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """When schema is provided, _call_sync receives it as the schema keyword arg."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    received: list[dict] = []

    def _spy(parts, *, api_key: str, model: str, schema=None):
        received.append({"schema": schema})
        return _make_response('{"ok": true}')

    my_schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    with patch("src.services.gemini._call_sync", side_effect=_spy):
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

    with patch("src.services.gemini._call_sync", side_effect=AssertionError("should not be called")):
        with pytest.raises(GeminiUnavailableError):
            await gemini_client.generate("Hello", model="gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Test 6: call_gemini_vision — both keys fail → GeminiUnavailableError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vision_both_keys_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """call_gemini_vision raises GeminiUnavailableError when _call_sync always raises."""
    from src.services.gemini import call_gemini_vision, GeminiUnavailableError as GUE

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    with patch("src.services.gemini._call_sync", side_effect=RuntimeError("quota")):
        with pytest.raises(GUE):
            await call_gemini_vision([{"base64": "eA==", "mime_type": "image/jpeg"}])


# ---------------------------------------------------------------------------
# Test 7: call_gemini_photo_links — both keys fail → GeminiUnavailableError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_photo_both_keys_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """call_gemini_photo_links raises GeminiUnavailableError when _call_sync always raises."""
    from src.services.gemini import call_gemini_photo_links, GeminiUnavailableError as GUE

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    with patch("src.services.gemini._call_sync", side_effect=RuntimeError("quota")):
        with pytest.raises(GUE):
            await call_gemini_photo_links([{"bytes": b"x", "mime_type": "image/jpeg"}])
