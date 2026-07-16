"""Direct Telegram Bot API calls via httpx — no wrapper library (PRD §D1)."""

from __future__ import annotations

import mimetypes
from pathlib import PurePath
from typing import Any

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


_UTF8_BOM = b"\xef\xbb\xbf"
_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
_GEMINI_DASH_TRANSLATION = str.maketrans({"—": "-", "–": "-"})


def _telegram_document_payload(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """Return bytes and MIME type for a Telegram document upload.

    Telegram clients preview extensionless text-like document payloads more
    reliably when Markdown is explicitly marked as UTF-8. Gemini also tends to
    emit typographic dashes, which have shown up as CP1252 mojibake in Telegram
    .md previews, so normalize them only for Markdown documents.
    """
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if PurePath(filename).suffix.lower() not in _MARKDOWN_EXTENSIONS:
        return file_bytes, mime

    text = file_bytes.decode("utf-8", errors="replace").translate(_GEMINI_DASH_TRANSLATION)
    normalized = text.encode("utf-8")
    if not normalized.startswith(_UTF8_BOM):
        normalized = _UTF8_BOM + normalized
    return normalized, "text/markdown; charset=utf-8"


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


def _raise_for_status(
    response: httpx.Response,
    *,
    method: str,
    chat_id: int | None = None,
    parse_mode: str | None = None,
) -> None:
    """Like ``response.raise_for_status()`` but first logs Telegram's error body.

    Telegram puts the real reason for a 4xx in the JSON body — e.g.
    ``"description": "Bad Request: can't parse entities: ..."``. The bare
    ``raise_for_status()`` raised before that body was ever read, so failures
    only logged a useless ``400 Bad Request``. Capture and log it here, then
    raise exactly as before so callers' behaviour is unchanged.
    """
    if response.status_code < 400:
        return
    try:
        detail: Any = response.json()
    except Exception:
        detail = response.text
    log.error(
        "telegram_http_error",
        method=method,
        chat_id=chat_id,
        status=response.status_code,
        parse_mode=parse_mode,
        response=detail,
    )
    response.raise_for_status()


async def _post_and_parse(
    method: str,
    *,
    json_payload: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    error_event: str,
    success_event: str,
    error_label: str | None = None,
    chat_id: int | None = None,
    parse_mode: str | None = None,
    **log_fields: Any,
) -> dict[str, Any]:
    """POST to the Bot API, validate the response, log, and return the parsed ``result``."""
    kwargs: dict[str, Any] = {}
    if json_payload is not None:
        kwargs["json"] = json_payload
    if data is not None:
        kwargs["data"] = data
    if files is not None:
        kwargs["files"] = files
    response = await _http().post(_endpoint(method), **kwargs)
    _raise_for_status(response, method=method, chat_id=chat_id, parse_mode=parse_mode)
    body = response.json()
    if not body.get("ok"):
        log.error(error_event, chat_id=chat_id, response=body, **log_fields)
        raise RuntimeError(f"Telegram {error_label or method} failed: {body!r}")
    log.info(success_event, chat_id=chat_id, **log_fields)
    return body.get("result", {})


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
    return await _post_and_parse(
        "sendMessage", json_payload=payload, chat_id=chat_id, parse_mode=parse_mode,
        error_event="telegram_send_failed", success_event="telegram_message_sent",
    )


async def send_photo(
    chat_id: int,
    photo_bytes: bytes,
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send a photo via multipart/form-data."""
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    files = {"photo": ("photo.jpg", photo_bytes, "image/jpeg")}
    return await _post_and_parse(
        "sendPhoto", data=data, files=files, chat_id=chat_id,
        error_event="telegram_photo_failed", success_event="telegram_photo_sent",
    )


async def send_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    *,
    caption: str | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a document via multipart/form-data."""
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
    if parse_mode:
        data["parse_mode"] = parse_mode
    document_bytes, mime = _telegram_document_payload(file_bytes, filename)
    files = {"document": (filename, document_bytes, mime)}
    return await _post_and_parse(
        "sendDocument", data=data, files=files, chat_id=chat_id,
        error_event="telegram_document_failed", success_event="telegram_document_sent",
        filename=filename,
    )


async def send_inline_keyboard(
    chat_id: int,
    text: str,
    buttons: list[list[dict]],
    *,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a message with an inline keyboard. buttons is the inline_keyboard array."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": buttons},
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return await _post_and_parse(
        "sendMessage", json_payload=payload, chat_id=chat_id,
        error_event="telegram_keyboard_failed", success_event="telegram_keyboard_sent",
        error_label="sendMessage (keyboard)",
    )


async def send_force_reply(
    chat_id: int,
    text: str,
    *,
    input_field_placeholder: str = "Your project direction...",
) -> dict[str, Any]:
    """Send a message that forces the user's next reply to address the bot."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "force_reply": True,
            "input_field_placeholder": input_field_placeholder,
        },
    }
    return await _post_and_parse(
        "sendMessage", json_payload=payload, chat_id=chat_id,
        error_event="telegram_force_reply_failed", success_event="telegram_force_reply_sent",
        error_label="sendMessage (ForceReply)",
    )


async def forward_message(chat_id: int, from_chat_id: int, message_id: int) -> dict[str, Any]:
    """Forward a message from from_chat_id to chat_id."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id,
    }
    return await _post_and_parse(
        "forwardMessage", json_payload=payload, chat_id=chat_id,
        error_event="telegram_forward_failed", success_event="telegram_message_forwarded",
        message_id=message_id,
    )


async def edit_message_text(chat_id: int, message_id: int, text: str) -> None:
    """Edit the text of a message and remove any inline keyboard."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "reply_markup": {"inline_keyboard": []},
    }
    await _post_and_parse(
        "editMessageText", json_payload=payload, chat_id=chat_id,
        error_event="telegram_edit_failed", success_event="telegram_message_edited",
        message_id=message_id,
    )


async def edit_message_reply_markup(
    chat_id: int, message_id: int, buttons: list[list[dict]]
) -> None:
    """Replace a message's inline keyboard without changing its text."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": {"inline_keyboard": buttons},
    }
    await _post_and_parse(
        "editMessageReplyMarkup",
        json_payload=payload,
        chat_id=chat_id,
        error_event="telegram_edit_reply_markup_failed",
        success_event="telegram_message_reply_markup_edited",
        message_id=message_id,
    )


async def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
    """Acknowledge a Telegram callback query to dismiss the loading state."""
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    response = await _http().post(_endpoint("answerCallbackQuery"), json=payload)
    _raise_for_status(response, method="answerCallbackQuery")


async def download_photo(file_id: str) -> tuple[bytes, str]:
    """Download a Telegram photo by file_id. Returns (raw_bytes, mime_type)."""
    resp = await _http().get(
        _endpoint("getFile"), params={"file_id": file_id}
    )
    _raise_for_status(resp, method="getFile")
    file_path: str = resp.json()["result"]["file_path"]
    dl_url = f"{_API_BASE}/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
    file_resp = await _http().get(dl_url)
    _raise_for_status(file_resp, method="getFile.download")
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else "jpg"
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    return file_resp.content, mime_map.get(ext, "image/jpeg")


async def download_file(file_id: str) -> bytes:
    """Download any Telegram file by file_id. Returns the raw bytes.

    Same getFile → /file/bot{token}/{path} two-step as download_photo, but
    format-agnostic (no mime map) — used for document uploads (#151).
    """
    resp = await _http().get(_endpoint("getFile"), params={"file_id": file_id})
    _raise_for_status(resp, method="getFile")
    file_path: str = resp.json()["result"]["file_path"]
    dl_url = f"{_API_BASE}/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
    file_resp = await _http().get(dl_url)
    _raise_for_status(file_resp, method="getFile.download")
    return file_resp.content
