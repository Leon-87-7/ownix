"""The ops bot: POST /webhook/ops and its invite-approval callbacks (ADR-0036).

Transport and policy helpers live in `src/services/ops_bot.py`; this module is
the webhook and the handlers that drive them. It shares no state with the user
bot beyond the invite copy in `context`.
"""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

from contextlib import suppress

import httpx
from secrets import compare_digest

from fastapi import Header, HTTPException, Request


from src import database
from src.config import settings
from src.services import ops_bot
from src.services.email import send_welcome_email
from src.services.jobs import (
    flush_held_jobs,
)
from src.telegram import sender
from src.telegram.context import (
    _INVITE_APPROVED_MESSAGE,
    _INVITE_BLOCKED_MESSAGE,
    _int_or_none,
    log,
    router,
)



async def _settle_ops_invite_card(
    chat_id: int | None, message_id: int | None, status: str, target_chat_id: int
) -> None:
    if chat_id is None or message_id is None:
        return
    label = "✅ Approved" if status == "approved" else "🚫 Blocked"
    try:
        await ops_bot.edit_ops_reply_markup(
            int(chat_id),
            int(message_id),
            [
                [
                    {
                        "text": label,
                        "callback_data": f"ops_invite_status:{status}:{target_chat_id}",
                    }
                ]
            ],
        )
    except Exception:
        log.exception(
            "ops_invite.card_settle_failed",
            chat_id=chat_id,
            message_id=message_id,
            status=status,
            target_chat_id=target_chat_id,
        )



_OPS_MUTATING_PREFIXES = {
    "ops_invite_approve",
    "ops_invite_block",
    "ops_dev_invite_approve",
    "ops_dev_invite_block",
    "ops_approve_pending",
    "ops_approve_pending_cancel",
}


_OPS_INVITE_DECISION_PREFIXES = {
    "ops_invite_approve",
    "ops_invite_block",
    "ops_dev_invite_approve",
    "ops_dev_invite_block",
}



def _ops_callback_can_mutate(prefix: str, sender_chat_id: int) -> bool:
    if prefix.startswith("ops_dev_invite_"):
        return ops_bot.can_admin(sender_chat_id) or ops_bot.can_dev_invite(sender_chat_id)
    return ops_bot.can_admin(sender_chat_id)



async def _ops_cb_invite_decision(
    cq_id: str, chat_id: int | None, message_id: int | None, prefix: str, payload: str
) -> None:
    try:
        target_chat_id = int(payload)
    except ValueError:
        await ops_bot.answer_ops_callback(cq_id, "Invalid invite action.")
        return
    status = "approved" if prefix.endswith("_approve") else "blocked"
    async with database.connection() as conn:
        cur = await conn.execute(
            """
            UPDATE users
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tg_id = ?
              AND status = 'pending'
            """,
            (status, target_chat_id),
        )
        await conn.commit()
    if cur.rowcount != 1:
        current_user = await database.get_user(target_chat_id)
        current_status = str(current_user.get("status")) if current_user is not None else "missing"
        if current_status in {"approved", "blocked"}:
            await _settle_ops_invite_card(chat_id, message_id, current_status, target_chat_id)
            await ops_bot.answer_ops_callback(cq_id, f"Already {current_status}.")
        elif current_user is None:
            await ops_bot.answer_ops_callback(cq_id, "Invite not found on this backend.")
        else:
            await ops_bot.answer_ops_callback(cq_id, "Invite is still pending. Try again.")
        return
    await ops_bot.answer_ops_callback(cq_id, status.capitalize())
    await _settle_ops_invite_card(chat_id, message_id, status, target_chat_id)
    if status == "approved":
        try:
            await flush_held_jobs(target_chat_id)
        except Exception:
            log.exception("ops_invite.held_job_flush_failed", target_chat_id=target_chat_id)
        try:
            approved_user = await database.get_user(target_chat_id)
            if approved_user is not None:
                await send_welcome_email(approved_user)
        except Exception:
            log.exception("ops_invite.welcome_email_failed", target_chat_id=target_chat_id)
    if prefix.startswith("ops_dev_invite_"):
        log.info(
            "ops_invite.dev_user_outcome_notification_skipped",
            target_chat_id=target_chat_id,
            status=status,
        )
        return
    try:
        await sender.send_message(
            target_chat_id,
            _INVITE_APPROVED_MESSAGE if status == "approved" else _INVITE_BLOCKED_MESSAGE,
        )
    except httpx.HTTPStatusError as exc:
        description = ""
        with suppress(Exception):
            description = str(exc.response.json().get("description") or "")
        if "chat not found" in description.lower():
            log.warning(
                "ops_invite.user_outcome_chat_not_found",
                target_chat_id=target_chat_id,
                status=status,
            )
            return
        log.exception(
            "ops_invite.user_outcome_notification_failed",
            target_chat_id=target_chat_id,
            status=status,
        )
    except Exception:
        log.exception(
            "ops_invite.user_outcome_notification_failed",
            target_chat_id=target_chat_id,
            status=status,
        )



async def _ops_cb_approve_pending(
    cq_id: str, chat_id: int | None, message_id: int | None, payload: str
) -> None:
    count = await ops_bot.approve_pending_batch(payload)
    await ops_bot.answer_ops_callback(cq_id, f"Approved {count}")
    if message_id and chat_id:
        await ops_bot.edit_ops_reply_markup(
            int(chat_id),
            int(message_id),
            [[{"text": f"✅ Approved {count}", "callback_data": f"ops_batch_status:{payload}"}]],
        )



async def _ops_cb_approve_pending_cancel(
    cq_id: str, chat_id: int | None, message_id: int | None
) -> None:
    await ops_bot.answer_ops_callback(cq_id, "Canceled")
    if message_id and chat_id:
        await ops_bot.edit_ops_reply_markup(int(chat_id), int(message_id), [])



async def _handle_ops_callback(callback: dict) -> None:
    cq_id = callback.get("id", "")
    data = callback.get("data", "")
    msg = callback.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    prefix, _, payload = data.partition(":")

    if prefix in _OPS_MUTATING_PREFIXES:
        sender_id = (callback.get("from") or {}).get("id")
        sender_chat_id = _int_or_none(sender_id)
        if sender_chat_id is None or not _ops_callback_can_mutate(prefix, sender_chat_id):
            log.warning(
                "ops_callback.unauthorized",
                sender_id=sender_id,
                chat_id=chat_id,
                data=data,
            )
            await ops_bot.answer_ops_callback(cq_id, "Not authorized.")
            return

    if prefix in _OPS_INVITE_DECISION_PREFIXES:
        await _ops_cb_invite_decision(cq_id, chat_id, message_id, prefix, payload)
    elif prefix == "ops_invite_status":
        await ops_bot.answer_ops_callback(cq_id, "Already decided.")
    elif prefix == "ops_approve_pending":
        await _ops_cb_approve_pending(cq_id, chat_id, message_id, payload)
    elif prefix == "ops_approve_pending_cancel":
        await _ops_cb_approve_pending_cancel(cq_id, chat_id, message_id)
    else:
        await ops_bot.answer_ops_callback(cq_id)



@router.post("/webhook/ops")
async def ops_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if not settings.OPS_WEBHOOK_SECRET:
        log.warning("ops_webhook_secret_unset")
        raise HTTPException(status_code=403, detail="invalid secret")
    if not compare_digest(x_telegram_bot_api_secret_token or "", settings.OPS_WEBHOOK_SECRET):
        log.warning("ops_webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret")
    update = await request.json()
    callback = update.get("callback_query")
    if callback:
        try:
            await _handle_ops_callback(callback)
        except Exception:
            log.exception("ops_webhook_callback_error")
            with suppress(Exception):
                await ops_bot.answer_ops_callback(callback.get("id", ""))
        return {"ok": True}
    message = update.get("message") or update.get("edited_message") or {}
    chat_id = _int_or_none((message.get("chat") or {}).get("id"))
    sender_id = _int_or_none((message.get("from") or {}).get("id"))
    message_id = _int_or_none(message.get("message_id"))
    text: str = (message.get("text") or "").strip()
    if chat_id and sender_id and text.startswith("/"):
        parts: list[str] = text.split()
        await ops_bot.handle_command(ops_bot.OpsCtx(chat_id, sender_id, parts, message_id))
    return {"ok": True}

