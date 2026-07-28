"""FastAPI entry point — wires up the webhook router, /health, and startup hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src import database, queue
from src.api.auth import auth_router
from src.api.brain import brain_router
from src.api.controls import controls_router
from src.api.google_oauth import google_oauth_router
from src.api.jobs import jobs_router
from src.api.parsed import parsed_router
from src.api.preview import preview_router
from src.api.spaces import spaces_router
from src.api.templates import templates_router
from src.auth.middleware import SessionMiddleware
from src.telegram import sender, webhook
from src.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


async def register_webhook(
    token: str, secret: str, url: str, *, ok_event: str, fail_event: str
) -> None:
    tg_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {
        "url": url,
        "secret_token": secret,
        "allowed_updates": ["message", "callback_query"],
    }
    try:
        resp = await sender._http().post(tg_url, json=payload)
        data = resp.json()
    except Exception:
        log.exception(fail_event, url=payload["url"])
        return
    if data.get("ok"):
        log.info(ok_event, url=payload["url"])
    else:
        log.error(fail_event, response=data)


async def _register_webhook() -> None:
    from src.config import settings

    if not settings.WEBHOOK_URL:
        log.warning("webhook_url_not_set", msg="Set WEBHOOK_URL in .env to auto-register")
        return
    await register_webhook(
        settings.TELEGRAM_BOT_TOKEN,
        settings.TELEGRAM_WEBHOOK_SECRET,
        f"{settings.WEBHOOK_URL.rstrip('/')}/webhook",
        ok_event="webhook_registered",
        fail_event="webhook_registration_failed",
    )


async def _register_ops_webhook() -> None:
    from src.config import settings

    missing = [
        name
        for name, value in {
            "OPS_BOT_TOKEN": settings.OPS_BOT_TOKEN,
            "OPS_WEBHOOK_SECRET": settings.OPS_WEBHOOK_SECRET,
            "OPS_WEBHOOK_URL": settings.OPS_WEBHOOK_URL,
        }.items()
        if not value
    ]
    if missing:
        log.warning("ops_webhook_missing_config", missing=missing)
        return
    await register_webhook(
        settings.OPS_BOT_TOKEN,
        settings.OPS_WEBHOOK_SECRET,
        settings.OPS_WEBHOOK_URL,
        ok_event="ops_webhook_registered",
        fail_event="ops_webhook_registration_failed",
    )


async def _drain_purge_outbox() -> None:
    """Drain pending purge tasks from the outbox to Redis.

    Runs every 30 seconds. Tasks are written to the outbox atomically with job deletion,
    and this drainer moves them to Redis, ensuring purge tasks cannot be lost even when
    Redis is temporarily unavailable.
    """
    pending = await database.list_pending_purge_tasks()
    if not pending:
        return
    for record in pending:
        task_id = record["id"]
        task_payload = record["task_payload"]
        try:
            await queue.enqueue(task_payload)
            await database.mark_purge_task_enqueued(task_id)
            log.info("purge_task_drained", job_id=task_payload["job_id"], task_id=task_id)
        except Exception:
            # Retry on next drain cycle. Do not mark as enqueued.
            log.exception("purge_task_drain_failed", job_id=task_payload["job_id"], task_id=task_id)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from src.config import settings

    log.info("api_starting")
    await database.init_db()
    from src import brain

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    # Drain purge_tasks outbox to Redis every 30 seconds.
    scheduler.add_job(_drain_purge_outbox, "interval", seconds=30)
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        scheduler.add_job(brain.refresh_stale_links, "cron", hour=9, day_of_week="sun,wed")
    scheduler.start()
    log.info("scheduler_started")
    await _register_webhook()
    await _register_ops_webhook()
    log.info("api_ready")
    yield
    log.info("api_shutting_down")
    await sender.close()
    await queue.close()
    from src.auth import session as session_store

    await session_store.close()


app = FastAPI(title="vig — Video Intelligence Gateway", lifespan=lifespan)
app.add_middleware(SessionMiddleware)
app.include_router(webhook.router)
app.include_router(auth_router)
app.include_router(brain_router)
app.include_router(controls_router)
app.include_router(jobs_router)
app.include_router(google_oauth_router)
app.include_router(parsed_router)
app.include_router(spaces_router)
app.include_router(templates_router)
app.include_router(preview_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
