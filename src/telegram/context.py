"""Shared Telegram plumbing: the router, the handler contexts, the invite copy.

The bottom of the telegram package — every other module here imports from it
and it imports from none of them.
"""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

import html

from dataclasses import dataclass

from fastapi import APIRouter


from src.config import settings
from src.telegram import sender
from src.utils.logger import get_logger


log = get_logger(__name__)

router = APIRouter()



def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None



def _admin_label() -> str:
    return settings.ADMIN_CONTACT_NAME or "the operator"



_INVITE_EMAIL_PROMPT_TEMPLATE = (
    "Ownix is invite-only — send your email so {admin} can review your request next."
)

_INVITE_WAITING_MESSAGE_TEMPLATE = (
    "You're in the queue with {admin}. Links you send meanwhile are saved and process on approval."
)

_INVITE_APPROVED_MESSAGE = "You're in, send a link."

_INVITE_BLOCKED_MESSAGE = "Access blocked. There is no next step for this account."



@dataclass
class CallbackCtx:
    chat_id: int
    job_id: str  # payload after ":" in callback data
    cq_id: str
    data: str  # full raw data string
    message_id: int | None = None  # message_id of the message containing the inline keyboard



@dataclass
class SlashCtx:
    chat_id: int
    parts: list[str]  # split command + args
    message_id: int | None



async def _reply_cached_job(chat_id: int, job: dict) -> None:
    """Send a dedup notice. Caller should not enqueue."""
    job_tag = f"job_{job['id'][-4:]}"
    status = job.get("status", "")
    if status in ("done", "transcript_done"):
        sheet_id = settings.GOOGLE_SHEETS_ID
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else None
        drive_line = f'\n📊 <a href="{sheet_url}">Open in Sheets</a>' if sheet_url else ""
        title_line = f"\n🎬 {html.escape(job['title'])}" if job.get("title") else ""
        body = f"⚡ Already processed ({job_tag}){title_line}{drive_line}\n\nUse /force &lt;url&gt; to reprocess."
        if job.get("bot_message_id"):
            await sender.send_inline_keyboard(
                chat_id,
                body,
                buttons=[
                    [
                        {
                            "text": "Show job done",
                            "callback_data": f"show_done:{job['id']}",
                        }
                    ]
                ],
                parse_mode="HTML",
            )
        else:
            await sender.send_message(chat_id, body, parse_mode="HTML")
    else:
        body = f"⏳ Already in queue ({job_tag}, {status}) — hang tight.\n\nUse /force &lt;url&gt; to start a second run."
        await sender.send_message(chat_id, body, parse_mode="HTML")



def _tagged_ack(resp, *, prefix: str = "📥 Received!") -> str:
    """Render an intake tag outcome without Telegram markup injection."""
    lines = [prefix, f"job_{resp.job_id[-4:]}"]
    labels = {
        "attached": "Attached", "unknown": "Unknown", "ambiguous": "Ambiguous",
        "invalid": "Invalid", "failed": "Failed",
    }
    for key, label in labels.items():
        values = (resp.tag_outcome or {}).get(key, [])
        if values:
            lines.append(f"{label}: " + ", ".join(f"#{value}" for value in values))
    return "\n".join(lines)



def _extract_message_identity(from_user: dict, chat: dict) -> dict:
    return {
        "first_name": from_user.get("first_name") or chat.get("first_name") or "",
        "last_name": from_user.get("last_name") or chat.get("last_name"),
        "username": from_user.get("username") or chat.get("username"),
    }

