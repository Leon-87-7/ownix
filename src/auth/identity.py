"""External identity resolution onto the existing integer owner key."""

from __future__ import annotations

import asyncio
import secrets
import sqlite3

from src import database
from src.utils.validators import normalize_email

_resolve_lock = asyncio.Lock()
_PROVIDERS = frozenset({"github", "google", "email", "telegram", "discord"})

# Telegram bounds every id (including negative group/supergroup chat ids) to
# at most 52 significant bits, specifically so it stays safe in a
# double-precision float — see the Bot API's `User`/`Chat` id docs. Starting
# synthetic owner ids at -(2**53) keeps them permanently disjoint from any
# real Telegram-issued id: a later group-chat tenant can never collide with
# one, regardless of how Telegram's own id space shifts within that bound.
_SYNTHETIC_OWNER_ID_FLOOR = -(2**53)


def _mint_synthetic_owner_id() -> int:
    return _SYNTHETIC_OWNER_ID_FLOOR - secrets.randbelow(2**31)


async def _reconcile_late_email(
    provider: str, subject: str, existing: int, normalized: str
) -> int:
    """Apply the verified-email merge to an identity linked before it had an email.

    A provider can withhold a verified email on first login (a private GitHub
    address) and hand it over later. Returning `existing` unconditionally would
    strand that identity on its own account even though ADR-0061 says a
    provider-verified email merges cross-provider accounts.
    """
    owner = await database.get_user(existing)
    if owner is not None and owner["email"]:
        return existing  # already has an email — nothing arrived that's new
    matched = await database.get_user_by_email(normalized)
    if matched is None:
        try:
            await database.set_user_email(existing, normalized)
        except sqlite3.IntegrityError:
            # Lost a race to another signup claiming this address; fall through
            # to the owner it landed on.
            matched = await database.get_user_by_email(normalized)
            if matched is None:
                raise
        else:
            return existing
    winner = int(matched["tg_id"])
    if winner == existing:
        return existing
    # ponytail: re-points the link only — jobs already filed under the
    # abandoned owner stay there rather than being migrated. Move them here if
    # this stops being a rare, early-account case.
    await database.relink_identity(provider, subject, winner)
    return winner


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
            if normalized and email_verified:
                return await _reconcile_late_email(provider, subject, existing, normalized)
            return existing

        if normalized and email_verified:
            matched = await database.get_user_by_email(normalized)
            if matched:
                return await database.link_identity(
                    provider, subject, int(matched["tg_id"]), verified=True
                )

        owner_id = _mint_synthetic_owner_id()
        while await database.get_user(owner_id) is not None:
            owner_id = _mint_synthetic_owner_id()
        await database.upsert_user(tg_id=owner_id, first_name=provider.title())
        # Tracks the fresh row just created above — cleared once that row is
        # itself already reconciled away (the email-collision branch below),
        # so the final orphan check never deletes a real, pre-existing account.
        minted_id: int | None = owner_id
        if normalized and email_verified:
            try:
                await database.set_user_email(owner_id, normalized)
            except sqlite3.IntegrityError:
                matched = await database.get_user_by_email(normalized)
                if matched is None:
                    raise
                await database.delete_user(owner_id)
                owner_id = int(matched["tg_id"])
                minted_id = None
        winner = await database.link_identity(
            provider, subject, owner_id, verified=email_verified
        )
        if minted_id is not None and winner != minted_id:
            # A concurrent resolve_owner call for this exact (provider,
            # subject) won identity_links' INSERT OR IGNORE race — the row
            # minted above never got linked to anything and must not survive
            # as an orphan.
            await database.delete_user(minted_id)
        return winner
