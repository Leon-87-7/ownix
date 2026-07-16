"""Ops Telegram bot helpers and ADR-0036 command handlers."""

from __future__ import annotations

import csv
import io
import json
import secrets
from dataclasses import dataclass

from src import database, queue
from src.config import settings
from src.telegram import sender
from src.utils.logger import get_logger

log = get_logger(__name__)

MAX_CHAT_ROWS = 20
BATCH_TTL_SECONDS = 15 * 60
HELP_TEXT = """Ops commands:
/pending
/users [pending|approved|blocked|email <domain|all>]
/approve_pending <domain> (admins only)"""


@dataclass
class OpsCtx:
    chat_id: int
    sender_id: int
    parts: list[str]
    message_id: int | None = None


def read_chat_ids() -> set[int]:
    return set(settings.ops_chat_ids) | set(settings.ops_admin_chat_ids)


def admin_chat_ids() -> tuple[int, ...]:
    return settings.ops_admin_chat_ids


def dev_notification_chat_ids() -> tuple[int, ...]:
    return settings.ops_dev_chat_ids or settings.ops_admin_chat_ids


def can_read(chat_id: int) -> bool:
    return chat_id in read_chat_ids()


def can_admin(chat_id: int) -> bool:
    return chat_id in set(settings.ops_admin_chat_ids)


def can_deliver_to(ctx: OpsCtx) -> bool:
    return ctx.chat_id == ctx.sender_id or can_read(ctx.chat_id)


async def send_ops_message(chat_id: int, text: str, *, parse_mode: str | None = None) -> dict:
    return await sender.send_message(
        chat_id, text, parse_mode=parse_mode, bot_token=settings.OPS_BOT_TOKEN
    )


async def send_ops_keyboard(
    chat_id: int, text: str, buttons: list[list[dict]], *, parse_mode: str | None = None
) -> dict:
    return await sender.send_inline_keyboard(
        chat_id, text, buttons, parse_mode=parse_mode, bot_token=settings.OPS_BOT_TOKEN
    )


async def send_ops_document(
    chat_id: int, content: bytes, filename: str, *, caption: str | None = None
) -> dict:
    return await sender.send_document(
        chat_id, content, filename, caption=caption, bot_token=settings.OPS_BOT_TOKEN
    )


async def answer_ops_callback(cq_id: str, text: str | None = None) -> None:
    await sender.answer_callback_query(cq_id, text=text, bot_token=settings.OPS_BOT_TOKEN)


async def edit_ops_reply_markup(chat_id: int, message_id: int, buttons: list[list[dict]]) -> None:
    await sender.edit_message_reply_markup(
        chat_id, message_id, buttons, bot_token=settings.OPS_BOT_TOKEN
    )


def _name(row: dict) -> str:
    return " ".join(x for x in [row.get("first_name"), row.get("last_name")] if x).strip() or str(
        row.get("tg_id")
    )


def invite_card_text(row: dict, email: str, *, dev: bool = False) -> str:
    prefix = "🧪 LOCAL/DEV INVITE\n" if dev else "👤 Invite approval\n"
    username = (row.get("username") or "unknown").lstrip("@")
    return f"{prefix}{_name(row)}\n{email}\n@{username}\nchat {row.get('tg_id')}"


async def notify_invite(chat_id: int, email: str, *, dev: bool = False) -> bool:
    targets = dev_notification_chat_ids() if dev else admin_chat_ids()
    if not targets:
        log.warning("ops_invite.no_admin_chat_ids", chat_id=chat_id, dev=dev)
        return False
    user = await database.get_user(chat_id) or {"tg_id": chat_id}
    text = invite_card_text(user, email, dev=dev)
    for target in targets:
        await send_ops_keyboard(
            target,
            text,
            [
                [
                    {"text": "✅ Approve", "callback_data": f"ops_invite_approve:{chat_id}"},
                    {"text": "🚫 Block", "callback_data": f"ops_invite_block:{chat_id}"},
                ]
            ],
        )
    return True


def normalize_email_domain(value: str) -> str | None:
    domain = value.strip().lower().lstrip("@")
    if not domain or domain == "all":
        return None
    if "@" in domain or "." not in domain:
        return None
    labels = domain.split(".")
    if any(
        not label
        or label.startswith("-")
        or label.endswith("-")
        or any(not (char.isalnum() or char == "-") for char in label)
        for label in labels
    ):
        return None
    return domain


def _csv_cell(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def format_rows(rows: list[dict]) -> str:
    if not rows:
        return "No users found."
    lines = []
    for r in rows:
        email = r.get("email") or "no-email"
        username = (r.get("username") or "").lstrip("@")
        lines.append(
            f"• {r['tg_id']} · {r['status']} · {email} · {_name(r)}"
            + (f" · @{username}" if username else "")
        )
    return "\n".join(lines)


def rows_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "tg_id",
            "status",
            "email",
            "username",
            "first_name",
            "last_name",
            "created_at",
            "updated_at",
        ],
    )
    writer.writeheader()
    for r in rows:
        writer.writerow({k: _csv_cell(r.get(k)) for k in writer.fieldnames or []})
    return buf.getvalue().encode("utf-8")


async def deliver_rows(chat_id: int, title: str, rows: list[dict]) -> None:
    if len(rows) <= MAX_CHAT_ROWS:
        await send_ops_message(chat_id, f"{title} ({len(rows)})\n" + format_rows(rows))
        return
    await send_ops_document(
        chat_id, rows_csv(rows), "ops-users.csv", caption=f"{title}: {len(rows)} rows"
    )


def _batch_key(batch_id: str) -> str:
    return f"ops_approve_pending:{batch_id}"


async def create_approval_batch(domain: str, rows: list[dict]) -> str:
    batch_id = secrets.token_urlsafe(8)
    payload = {
        "domain": domain,
        "ids": [int(row["tg_id"]) for row in rows],
    }
    await queue._client().set(_batch_key(batch_id), json.dumps(payload), ex=BATCH_TTL_SECONDS)
    return batch_id


async def list_users(
    status: str | None = None, *, email_domain: str | None = None, limit: int | None = 20
) -> list[dict]:
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if email_domain and email_domain != "all":
        clauses.append("lower(coalesce(email, '')) LIKE ?")
        params.append("%@" + email_domain.lower().lstrip("@"))
    sql_parts = [
        "SELECT tg_id, username, first_name, last_name, email, status, created_at, updated_at",
        "FROM users",
    ]
    if clauses:
        sql_parts.append("WHERE " + " AND ".join(clauses))
    sql_parts.append("ORDER BY created_at DESC, tg_id DESC")
    if limit is not None:
        sql_parts.append("LIMIT ?")
        params.append(limit)
    sql = " ".join(sql_parts)
    return await database._fetch_dicts(sql, tuple(params))


async def _approve_pending_ids(target_ids: list[int]) -> int:
    if not target_ids:
        return 0

    approved_rows: list[dict] = []
    async with database.connection() as conn:
        for tg_id in target_ids:
            cur = await conn.execute(
                """
                SELECT tg_id, username, first_name, last_name, email, status, created_at, updated_at
                FROM users
                WHERE tg_id = ?
                  AND status = 'pending'
                """,
                (tg_id,),
            )
            row = await cur.fetchone()
            if row is None:
                continue
            cur = await conn.execute(
                """
                UPDATE users
                SET status = 'approved', updated_at = CURRENT_TIMESTAMP
                WHERE tg_id = ?
                  AND status = 'pending'
                """,
                (tg_id,),
            )
            if cur.rowcount == 1:
                approved_rows.append(dict(row))
        await conn.commit()
    for row in approved_rows:
        try:
            await sender.send_message(int(row["tg_id"]), "You're in, send a link.")
        except Exception:
            log.exception("ops_batch_approval_notification_failed", tg_id=row.get("tg_id"))
    return len(approved_rows)


async def approve_pending_batch(batch_id: str) -> int:
    raw = await queue._client().get(_batch_key(batch_id))
    await queue._client().delete(_batch_key(batch_id))
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
        target_ids = [int(value) for value in payload.get("ids", [])]
    except (TypeError, ValueError, json.JSONDecodeError):
        log.warning("ops_batch_approval_invalid_payload", batch_id=batch_id)
        return 0
    return await _approve_pending_ids(target_ids)


async def approve_pending_domain(domain: str) -> int:
    domain = normalize_email_domain(domain)
    if not domain:
        return 0
    rows = await list_users("pending", email_domain=domain, limit=None)
    return await _approve_pending_ids([int(row["tg_id"]) for row in rows])


async def handle_command(ctx: OpsCtx) -> None:
    if not can_read(ctx.sender_id) or not can_deliver_to(ctx):
        await send_ops_message(ctx.chat_id, "Not authorized.")
        return
    cmd = ctx.parts[0].lower()
    if cmd in {"/start", "/help"}:
        await send_ops_message(ctx.chat_id, HELP_TEXT)
        return
    if cmd == "/pending":
        await deliver_rows(ctx.chat_id, "Pending users", await list_users("pending", limit=None))
        return
    if cmd == "/users":
        if len(ctx.parts) == 1:
            await deliver_rows(ctx.chat_id, "Recent users", await list_users(limit=20))
            return
        arg = ctx.parts[1].lower()
        if arg in {"pending", "approved", "blocked"}:
            await deliver_rows(ctx.chat_id, f"Users: {arg}", await list_users(arg, limit=None))
            return
        if arg == "email" and len(ctx.parts) >= 3:
            domain = ctx.parts[2].lower()
            rows = await list_users(email_domain=None if domain == "all" else domain, limit=None)
            rows = [r for r in rows if r.get("email")] if domain == "all" else rows
            await deliver_rows(ctx.chat_id, f"Emails: {domain}", rows)
            return
        await send_ops_message(
            ctx.chat_id, "Usage: /users [pending|approved|blocked|email <domain|all>]"
        )
        return
    if cmd == "/approve_pending":
        if not can_admin(ctx.sender_id):
            await send_ops_message(ctx.chat_id, "Not authorized.")
            return
        if len(ctx.parts) != 2:
            await send_ops_message(ctx.chat_id, "Usage: /approve_pending <email-domain>")
            return
        domain = normalize_email_domain(ctx.parts[1])
        if not domain:
            await send_ops_message(ctx.chat_id, "Usage: /approve_pending <email-domain>")
            return
        rows = await list_users("pending", email_domain=domain, limit=None)
        if not rows:
            await send_ops_message(ctx.chat_id, f"No pending users for @{domain}.")
            return
        text = f"Approve {len(rows)} pending @{domain}?\n" + format_rows(rows[:MAX_CHAT_ROWS])
        if len(rows) > MAX_CHAT_ROWS:
            text += (
                f"\nShowing first {MAX_CHAT_ROWS} of {len(rows)}. "
                f"Confirm approves all {len(rows)} pending @{domain}."
            )
        batch_id = await create_approval_batch(domain, rows)
        await send_ops_keyboard(
            ctx.chat_id,
            text,
            [
                [
                    {
                        "text": f"✅ Confirm @{domain}",
                        "callback_data": f"ops_approve_pending:{batch_id}",
                    },
                    {"text": "Cancel", "callback_data": "ops_approve_pending_cancel:0"},
                ]
            ],
        )
        return
    await send_ops_message(ctx.chat_id, HELP_TEXT)
