"""Full account deletion — the self-serve "Delete my account" action.

Reuses the exact same per-job / per-link delete paths as the dashboard's
individual delete buttons, so cleanup coverage (Drive, GCS, Sheets — best
effort via src/processors/purge.py) is identical, just looped over every
row chat_id owns.
"""
from __future__ import annotations

from src import database
from src.auth import extension_tokens
from src.services.google_auth import disconnect_google
from src.services.jobs import build_job_purge_task
from src.utils.logger import get_logger

log = get_logger(__name__)


async def delete_account(chat_id: int) -> None:
    """Hard-delete every job, link, credential, and setting chat_id owns."""
    job_rows = await database._fetch_dicts("SELECT id FROM jobs WHERE chat_id = ?", (chat_id,))
    for row in job_rows:
        job = await database.get_job(row["id"])
        if job is None:
            continue
        purge_task = await build_job_purge_task(job)
        await database.delete_job(job["id"], purge_payload=purge_task, with_links=True)

    # Standalone links (e.g. bookmark imports) not tied to a job deleted above.
    link_rows = await database._fetch_dicts("SELECT id FROM links WHERE chat_id = ?", (chat_id,))
    for row in link_rows:
        await database.delete_link(row["id"], chat_id)

    for token in await extension_tokens.list_extension_tokens(chat_id):
        await extension_tokens.revoke_extension_token(chat_id, token["id"])

    await disconnect_google(chat_id)
    await database.delete_account_settings(chat_id)
    await database.clear_chat_state(chat_id)
    await database.delete_user(chat_id)
    log.info("account_deleted", chat_id=chat_id)
