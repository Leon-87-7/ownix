"""Telegram Login Widget HMAC verifier (pure, no I/O).

See https://core.telegram.org/widgets/login#checking-authorization
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

_MAX_AGE_SECONDS = 86_400  # 24 hours


def verify_telegram_auth(payload: dict[str, Any], bot_token: str) -> dict[str, Any] | None:
    """Verify a Telegram Login Widget payload against bot_token.

    Returns user fields (without 'hash') on success, None on any failure:
    tampered hash, stale auth_date, missing required fields.
    """
    if "hash" not in payload or "auth_date" not in payload:
        return None

    received_hash = str(payload["hash"])

    # data-check string: sorted key=value (exclude 'hash'), newline-separated
    data_check_string = "\n".join(
        f"{k}={v}"
        for k, v in sorted(
            (k, str(v)) for k, v in payload.items() if k != "hash" and v is not None
        )
    )

    # key = SHA-256 of the bot token (raw bytes, not hex)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    try:
        auth_date = int(payload["auth_date"])
    except (ValueError, TypeError):
        return None

    if time.time() - auth_date > _MAX_AGE_SECONDS:
        return None

    return {k: v for k, v in payload.items() if k != "hash"}
