"""Direct Telegram Bot API calls via httpx — no wrapper library (PRD §D1)."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


_API_BASE = "https://api.telegram.org"
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _endpoint(method: str) -> str:
    return f"{_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


async def send_message(
    chat_id: int,
    text: str,
    *,
    reply_to_message_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a plain Telegram message. Returns the parsed `result` field on success."""
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    response = await _http().post(_endpoint("sendMessage"), json=payload)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        log.error("telegram_send_failed", chat_id=chat_id, response=body)
        raise RuntimeError(f"Telegram sendMessage failed: {body!r}")
    log.info("telegram_message_sent", chat_id=chat_id)
    return body.get("result", {})
