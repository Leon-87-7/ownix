"""POST /webhook — receives Telegram updates and fans them out.

Route registration and update fan-out only. The handlers live in
`callbacks.py`, `commands.py`, `routing.py` and `ops.py`.
"""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

from contextlib import suppress

from secrets import compare_digest

from fastapi import Header, HTTPException, Request


from src.config import settings
from src.telegram import sender
from src.telegram import callbacks, routing
from src.telegram import ops as _ops  # noqa: F401  -- registers POST /webhook/ops
from src.telegram.context import _extract_message_identity, log, router


async def _webhook_route_callback(callback: dict) -> None:
    try:
        await callbacks._handle_callback(callback)
    except HTTPException as exc:
        if exc.status_code == 429:
            chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
            if chat_id is not None:
                with suppress(Exception):
                    await sender.send_message(chat_id, _RATE_LIMIT_MSG)
        else:
            log.exception("webhook_callback_error")
        with suppress(Exception):
            await sender.answer_callback_query(callback.get("id", ""))
    except Exception:
        log.exception("webhook_callback_error")
        # Acknowledge so the client's inline button stops spinning even on failure.
        with suppress(Exception):
            await sender.answer_callback_query(callback.get("id", ""))


_RATE_LIMIT_MSG = (
    "🐢 Slow down — too many jobs from this chat in the last minute. "
    "Try again shortly."
)


async def _webhook_route_photo(chat_id: int, message: dict, photo: list, identity: dict) -> None:
    try:
        if await routing.admit_or_park(chat_id, "", identity):
            await routing._handle_photo_update(chat_id, message, photo)
    except HTTPException as exc:
        if exc.status_code == 429:
            await sender.send_message(chat_id, _RATE_LIMIT_MSG)
        else:
            log.exception("webhook_photo_error", chat_id=chat_id)
    except Exception:
        log.exception("webhook_photo_error", chat_id=chat_id)


async def _webhook_route_document(
    chat_id: int, message: dict, document: dict, identity: dict
) -> None:
    try:
        if await routing.admit_or_park(chat_id, "", identity):
            await routing._handle_document_update(chat_id, message, document)
    except HTTPException as exc:
        if exc.status_code == 429:
            await sender.send_message(chat_id, _RATE_LIMIT_MSG)
        else:
            log.exception("webhook_document_error", chat_id=chat_id)
    except Exception:
        log.exception("webhook_document_error", chat_id=chat_id)


async def _webhook_route_text(
    chat_id: int, text: str, message_id: int | None, identity: dict
) -> None:
    try:
        await routing._route_text(chat_id, text, message_id, identity)
    except HTTPException as exc:
        if exc.status_code == 429:
            await sender.send_message(chat_id, _RATE_LIMIT_MSG)
        else:
            log.exception("webhook_handler_error", chat_id=chat_id)
    except Exception:
        log.exception("webhook_handler_error", chat_id=chat_id)
        try:
            await sender.send_message(
                chat_id,
                "⚠️ Something went wrong processing your message. Please try again.",
            )
        except Exception:
            log.exception("webhook_error_notification_failed", chat_id=chat_id)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if not compare_digest(x_telegram_bot_api_secret_token or "", settings.TELEGRAM_WEBHOOK_SECRET):
        log.warning("webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret")

    update = await request.json()

    # Handle callback queries (inline keyboard button presses)
    callback = update.get("callback_query")
    if callback:
        await _webhook_route_callback(callback)
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id")
    identity = _extract_message_identity(message.get("from") or {}, chat)

    log.info("webhook_received", chat_id=chat_id, message_id=message_id, text_len=len(text))

    # Photo path
    photo = message.get("photo")
    if photo and chat_id:
        await _webhook_route_photo(chat_id, message, photo, identity)
        return {"ok": True}

    # Document upload path (#151) — a file message has no `.text`, so this must
    # run before the text guard below.
    document = message.get("document")
    if document and chat_id:
        await _webhook_route_document(chat_id, message, document, identity)
        return {"ok": True}

    if not chat_id or not text:
        return {"ok": True}

    await _webhook_route_text(chat_id, text, message_id, identity)
    return {"ok": True}

