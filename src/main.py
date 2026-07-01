"""FastAPI entry point — wires up the webhook router, /health, and startup hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src import database, queue
from src.auth.middleware import SessionMiddleware
from src.telegram import sender, webhook
from src.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


async def _register_webhook() -> None:
    from src.config import settings

    if not settings.WEBHOOK_URL:
        log.warning("webhook_url_not_set", msg="Set WEBHOOK_URL in .env to auto-register")
        return
    tg_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": f"{settings.WEBHOOK_URL.rstrip('/')}/webhook",
        "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
        "allowed_updates": ["message", "callback_query"],
    }
    resp = await sender._http().post(tg_url, json=payload)
    data = resp.json()
    if data.get("ok"):
        log.info("webhook_registered", url=payload["url"])
    else:
        log.error("webhook_registration_failed", response=data)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from src.config import settings

    log.info("api_starting")
    await database.init_db()
    from src import brain

    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(brain.refresh_stale_links, "cron", hour=9, day_of_week="sun,wed")
        scheduler.start()
        log.info("brain_scheduler_started")
    await _register_webhook()
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
from src.api.auth import auth_router
from src.api.brain import brain_router
from src.api.controls import controls_router
from src.api.jobs import jobs_router
from src.api.google_oauth import google_oauth_router
from src.api.parsed import parsed_router
from src.api.spaces import spaces_router
from src.api.templates import templates_router

app.include_router(auth_router)
app.include_router(brain_router)
app.include_router(controls_router)
app.include_router(jobs_router)
app.include_router(google_oauth_router)
app.include_router(parsed_router)
app.include_router(spaces_router)
app.include_router(templates_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
