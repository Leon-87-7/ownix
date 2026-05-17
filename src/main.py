"""FastAPI entry point — wires up the webhook router, /health, and startup hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src import database, queue
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
    }
    resp = await sender._http().post(tg_url, json=payload)
    data = resp.json()
    if data.get("ok"):
        log.info("webhook_registered", url=payload["url"])
    else:
        log.error("webhook_registration_failed", response=data)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("api_starting")
    await database.init_db()
    await _register_webhook()
    log.info("api_ready")
    yield
    log.info("api_shutting_down")
    await sender.close()
    await queue.close()


app = FastAPI(title="vig — Video Intelligence Bot", lifespan=lifespan)
app.include_router(webhook.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
