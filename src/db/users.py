"""Users, their identities, per-chat settings and per-chat domain lists.
"""

from __future__ import annotations

import json
from typing import cast

import aiosqlite

from src.config import settings
from src.db import core
from src.db.core import (
    log,
    UserStatus,
    _execute,
    _execute_rowcount,
    _fetch_all,
    _fetch_dicts,
    _fetch_one,
)

async def get_ignored_domains(chat_id: int) -> set[str]:
    rows = await _fetch_all("SELECT domain FROM ignored_domains WHERE chat_id = ?", (chat_id,))
    return {row[0] for row in rows}


async def add_ignored_domain(chat_id: int, domain: str) -> bool:
    return (
        await _execute_rowcount(
            "INSERT OR IGNORE INTO ignored_domains (chat_id, domain) VALUES (?, ?)",
            (chat_id, domain),
        )
        > 0
    )


async def remove_ignored_domain(chat_id: int, domain: str) -> bool:
    return (
        await _execute_rowcount(
            "DELETE FROM ignored_domains WHERE chat_id = ? AND domain = ?",
            (chat_id, domain),
        )
        > 0
    )


async def get_user_setting(chat_id: int, key: str) -> str | None:
    row = await _fetch_one(
        "SELECT value FROM user_settings WHERE chat_id = ? AND key = ?",
        (chat_id, key),
    )
    return str(row["value"]) if row else None


async def set_user_setting(chat_id: int, key: str, value: str) -> None:
    await _execute(
        """
        INSERT INTO user_settings (chat_id, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (chat_id, key, value),
    )


_BRAIN_LINKS_VIEW_KEY = "brain_links_view"
_DEFAULT_BRAIN_LINKS_VIEW = {"order": "desc", "size": 25}
_BRAIN_LINKS_VIEW_ORDERS = {"asc", "desc"}
_BRAIN_LINKS_VIEW_SIZES = {25, 50, 100}


def _normalize_brain_links_view(value: object) -> dict[str, int | str]:
    view = dict(_DEFAULT_BRAIN_LINKS_VIEW)
    if isinstance(value, dict):
        order = value.get("order")
        size = value.get("size")
        if order in _BRAIN_LINKS_VIEW_ORDERS:
            view["order"] = str(order)
        if size in _BRAIN_LINKS_VIEW_SIZES:
            view["size"] = int(size)
    return view


async def get_brain_links_view(chat_id: int) -> dict[str, int | str]:
    value = await get_user_setting(chat_id, _BRAIN_LINKS_VIEW_KEY)
    if value is None:
        return dict(_DEFAULT_BRAIN_LINKS_VIEW)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return dict(_DEFAULT_BRAIN_LINKS_VIEW)
    return _normalize_brain_links_view(parsed)


async def set_brain_links_view(
    chat_id: int, *, order: str, size: int
) -> dict[str, int | str]:
    view = _normalize_brain_links_view({"order": order, "size": size})
    await set_user_setting(chat_id, _BRAIN_LINKS_VIEW_KEY, json.dumps(view, separators=(",", ":")))
    return view


_ACCESSIBILITY_SETTINGS_KEY = "dashboard_accessibility_settings"
_DEFAULT_ACCESSIBILITY_SETTINGS: dict[str, bool | str | None] = {
    "visual_motion": True,
    "haptic_motion": True,
    "voice_uri": None,
}


def _normalize_accessibility_settings(value: object) -> dict[str, bool | str | None]:
    if not isinstance(value, dict):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    visual_motion = value.get("visual_motion")
    haptic_motion = value.get("haptic_motion")
    voice_uri = value.get("voice_uri", None)
    if not isinstance(visual_motion, bool) or not isinstance(haptic_motion, bool):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    if voice_uri is not None and not isinstance(voice_uri, str):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    return {
        "visual_motion": visual_motion,
        "haptic_motion": haptic_motion,
        "voice_uri": voice_uri,
    }


async def get_accessibility_settings(chat_id: int) -> dict[str, bool | str | None]:
    value = await get_user_setting(chat_id, _ACCESSIBILITY_SETTINGS_KEY)
    if value is None:
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    return _normalize_accessibility_settings(parsed)


# voice_uri's length isn't re-validated here — this module trusts its only
# caller (the /api/controls PUT route, Task 2) to have already applied
# AccessibilitySettingsIn's max_length=512 bound. Route any other future
# write of this setting through that same API rather than duplicating the
# bound at this layer.
async def set_accessibility_settings(
    chat_id: int, *, visual_motion: bool, haptic_motion: bool, voice_uri: str | None
) -> dict[str, bool | str | None]:
    settings_value: dict[str, bool | str | None] = {
        "visual_motion": visual_motion,
        "haptic_motion": haptic_motion,
        "voice_uri": voice_uri,
    }
    await set_user_setting(
        chat_id, _ACCESSIBILITY_SETTINGS_KEY, json.dumps(settings_value, separators=(",", ":"))
    )
    return settings_value


_RECOVERY_TELEGRAM_NOTIFICATIONS_KEY = "dashboard_recovery_telegram_notifications"


async def get_recovery_telegram_notifications_enabled(chat_id: int) -> bool:
    value = await get_user_setting(chat_id, _RECOVERY_TELEGRAM_NOTIFICATIONS_KEY)
    return value != "0"


async def set_recovery_telegram_notifications_enabled(chat_id: int, enabled: bool) -> None:
    await set_user_setting(chat_id, _RECOVERY_TELEGRAM_NOTIFICATIONS_KEY, "1" if enabled else "0")


async def add_allowed_domain(chat_id: int, domain: str) -> bool:
    """Insert (chat_id, domain) into allowed_domains. Returns True if inserted, False if already present."""
    return (
        await _execute_rowcount(
            "INSERT OR IGNORE INTO allowed_domains (chat_id, domain) VALUES (?, ?)",
            (chat_id, domain),
        )
        > 0
    )


async def list_allowed_domains(chat_id: int) -> set[str]:
    """Return the set of domains allowed for this chat."""
    rows = await _fetch_all("SELECT domain FROM allowed_domains WHERE chat_id = ?", (chat_id,))
    return {row[0] for row in rows}


async def remove_allowed_domain(chat_id: int, domain: str) -> bool:
    """Delete (chat_id, domain). Returns True if removed, False if not found."""
    return (
        await _execute_rowcount(
            "DELETE FROM allowed_domains WHERE chat_id = ? AND domain = ?",
            (chat_id, domain),
        )
        > 0
    )
def _validate_user_status(status: str) -> UserStatus:
    if status not in ("pending", "approved", "blocked", "deleting"):
        raise ValueError(f"Invalid user status: {status}")
    return cast(UserStatus, status)
async def _upsert_minimal_user(
    conn: aiosqlite.Connection,
    *,
    tg_id: int,
    email: str | None = None,
    status: UserStatus | None = None,
    update_email: bool = False,
) -> None:
    await conn.execute(
        """
        INSERT INTO users (tg_id, first_name, email, status, updated_at)
        VALUES (?, '', ?, COALESCE(?, 'pending'), CURRENT_TIMESTAMP)
        ON CONFLICT(tg_id) DO UPDATE SET
            email = CASE WHEN ? THEN excluded.email ELSE users.email END,
            status = CASE WHEN ? IS NULL THEN users.status ELSE excluded.status END,
            updated_at = excluded.updated_at
        """,
        (tg_id, email, status, update_email, status),
    )


# ---------------------------------------------------------------------------
# Users (web dashboard auth — issue #84)
# ---------------------------------------------------------------------------


async def upsert_user(
    *,
    tg_id: int,
    first_name: str,
    username: str | None = None,
    last_name: str | None = None,
    photo_url: str | None = None,
) -> None:
    """Insert or update a Telegram user row (keyed by tg_id)."""
    async with core.connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name, last_name, photo_url, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tg_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                photo_url  = excluded.photo_url,
                updated_at = excluded.updated_at
            """,
            (tg_id, username, first_name, last_name, photo_url),
        )
        await conn.commit()
    log.info("user_upserted", tg_id=tg_id)


async def get_user_status(tg_id: int) -> UserStatus:
    """Return the invite-gate status for tg_id; unknown users default to pending."""
    if settings.OPERATOR_CHAT_ID is not None and tg_id == settings.OPERATOR_CHAT_ID:
        return "approved"
    row = await _fetch_one("SELECT status FROM users WHERE tg_id = ?", (tg_id,))
    if row is None:
        return "pending"
    return _validate_user_status(str(row["status"]))


async def get_user(tg_id: int) -> dict | None:
    """Return a dashboard/invite user row keyed by Telegram id."""
    row = await _fetch_one(
        """
        SELECT tg_id, username, first_name, last_name, photo_url, email, status, created_at, updated_at
        FROM users
        WHERE tg_id = ?
        """,
        (tg_id,),
    )
    return dict(row) if row else None


async def set_user_status(tg_id: int, status: UserStatus) -> None:
    """Set a user's invite-gate status, creating a minimal row if needed."""
    status = _validate_user_status(status)
    if settings.OPERATOR_CHAT_ID is not None and tg_id == settings.OPERATOR_CHAT_ID:
        if status != "approved":
            log.warning("operator_status_override_ignored", tg_id=tg_id, requested=status)
        status = "approved"
    async with core.connection() as conn:
        await _upsert_minimal_user(conn, tg_id=tg_id, status=status)
        await conn.commit()
    log.info("user_status_set", tg_id=tg_id, status=status)


async def begin_account_deletion(tg_id: int) -> bool:
    """Atomically flip status to "deleting" unless a deletion is already in
    progress. Returns True if this call acquired the lock, False if another
    concurrent call (a second device/tab, or a login-resume race) already
    holds it — the caller should treat False as "nothing left to do here"
    rather than running delete_account() a second time.
    """
    rowcount = await _execute_rowcount(
        "UPDATE users SET status = 'deleting', updated_at = CURRENT_TIMESTAMP "
        "WHERE tg_id = ? AND status != 'deleting'",
        (tg_id,),
    )
    log.info("account_deletion_lock_attempted", tg_id=tg_id, acquired=rowcount > 0)
    return rowcount > 0


async def set_user_email(tg_id: int, email: str | None) -> None:
    """Set a user's email address, creating a pending minimal row if needed."""
    async with core.connection() as conn:
        await _upsert_minimal_user(conn, tg_id=tg_id, email=email, update_email=True)
        await conn.commit()
    log.info("user_email_set", tg_id=tg_id, has_email=email is not None)


async def get_user_by_email(email: str) -> dict | None:
    row = await _fetch_one("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,))
    return dict(row) if row else None


async def get_identity_owner(provider: str, subject: str) -> int | None:
    row = await _fetch_one(
        "SELECT owner_id FROM identity_links WHERE provider = ? AND subject = ?",
        (provider, subject),
    )
    return int(row["owner_id"]) if row else None


async def link_identity(
    provider: str, subject: str, owner_id: int, *, verified: bool
) -> int:
    """Attach an external identity, returning the winner of a concurrent insert."""
    async with core.connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO identity_links "
            "(provider, subject, owner_id, verified) VALUES (?, ?, ?, ?)",
            (provider, subject, owner_id, int(verified)),
        )
        cursor = await conn.execute(
            "SELECT owner_id FROM identity_links WHERE provider = ? AND subject = ?",
            (provider, subject),
        )
        row = await cursor.fetchone()
        await conn.commit()
    return int(row[0])


async def relink_identity(provider: str, subject: str, owner_id: int) -> None:
    """Re-point an existing identity link at another owner (verified-email merge)."""
    await _execute_rowcount(
        "UPDATE identity_links SET owner_id = ?, verified = 1 "
        "WHERE provider = ? AND subject = ?",
        (owner_id, provider, subject),
    )
    log.info("identity_relinked", provider=provider, owner_id=owner_id)


async def delete_user(tg_id: int) -> bool:
    """Hard-delete the invite-gate row for tg_id (account deletion's last step)."""
    deleted = await _execute_rowcount("DELETE FROM users WHERE tg_id = ?", (tg_id,)) > 0
    log.info("user_deleted", tg_id=tg_id, deleted=deleted)
    return deleted


_ACCOUNT_SETTINGS_DELETE_QUERIES = (
    "DELETE FROM tags WHERE chat_id = ?",
    "DELETE FROM allowed_domains WHERE chat_id = ?",
    "DELETE FROM ignored_domains WHERE chat_id = ?",
    "DELETE FROM templates WHERE chat_id = ?",
    "DELETE FROM user_settings WHERE chat_id = ?",
    # spaces cascades (ON DELETE CASCADE, FK enforcement is on for this
    # connection) to space_urls and context_blobs — delete_job() only cascades
    # space_urls for jobs it removes, so the space itself would otherwise survive.
    "DELETE FROM spaces WHERE chat_id = ?",
    # Short-lived Google OAuth CSRF state (has its own expires_at), but still
    # chat_id-scoped account data — clean it up rather than let it expire.
    "DELETE FROM google_oauth_states WHERE chat_id = ?",
)


async def delete_account_settings(chat_id: int) -> None:
    """Wipe chat_id's rows from every per-account table account deletion doesn't
    already cover via delete_job()/delete_link() (Controls settings, Spaces,
    pending OAuth state)."""
    async with core.connection() as conn:
        for query in _ACCOUNT_SETTINGS_DELETE_QUERIES:
            await conn.execute(query, (chat_id,))
        await conn.commit()


async def list_pending_users() -> list[dict]:
    """Return users waiting for approval, oldest first."""
    return await _fetch_dicts(
        """
        SELECT tg_id, username, first_name, last_name, photo_url, email, status, created_at, updated_at
        FROM users
        WHERE status = 'pending'
        ORDER BY created_at ASC, tg_id ASC
        """
    )
