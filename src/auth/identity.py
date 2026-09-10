"""External identity resolution onto the existing integer owner key."""

from __future__ import annotations

import asyncio
import secrets
import sqlite3

from src import database
from src.utils.validators import normalize_email

_resolve_lock = asyncio.Lock()
_PROVIDERS = frozenset({"github", "google", "email", "telegram", "discord"})


async def resolve_owner(
    provider: str,
    subject: str,
    *,
    email: str | None,
    email_verified: bool,
) -> int:
    """Resolve a provider subject, merging only a provider-verified email."""
    if provider not in _PROVIDERS or provider == "discord":
        raise ValueError("provider cannot originate a login")
    normalized = normalize_email(email) if email else None
    async with _resolve_lock:
        existing = await database.get_identity_owner(provider, subject)
        if existing is not None:
            return existing

        if normalized and email_verified:
            matched = await database.get_user_by_email(normalized)
            if matched:
                return await database.link_identity(
                    provider, subject, int(matched["tg_id"]), verified=True
                )

        owner_id = -(secrets.randbelow(2**31 - 1) + 1)
        while await database.get_user(owner_id) is not None:
            owner_id = -(secrets.randbelow(2**31 - 1) + 1)
        await database.upsert_user(tg_id=owner_id, first_name=provider.title())
        if normalized and email_verified:
            try:
                await database.set_user_email(owner_id, normalized)
            except sqlite3.IntegrityError:
                matched = await database.get_user_by_email(normalized)
                if matched is None:
                    raise
                await database.delete_user(owner_id)
                owner_id = int(matched["tg_id"])
        return await database.link_identity(
            provider, subject, owner_id, verified=email_verified
        )
