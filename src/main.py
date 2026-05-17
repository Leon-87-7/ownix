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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("api_starting")
    await database.init_db()
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
