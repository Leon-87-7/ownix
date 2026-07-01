"""Telegram Mini App initData verifier.

Telegram Mini Apps send a URL-encoded ``initData`` string. It must be verified
server-side before trusting embedded user/chat fields.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl

_MAX_AGE_SECONDS = 3600


def verify_init_data(init_data: str, bot_token: str, *, now: float | None = None) -> dict[str, Any] | None:
    """Return parsed Mini App data when signature and auth_date are valid."""
    if not init_data or not bot_token:
        return None

    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash or "auth_date" not in pairs or "user" not in pairs:
        return None

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    try:
        auth_date = int(pairs["auth_date"])
    except (TypeError, ValueError):
        return None
    clock = time.time() if now is None else now
    if clock - auth_date > _MAX_AGE_SECONDS or auth_date - clock > 60:
        return None

    try:
        user = json.loads(pairs["user"])
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None

    parsed: dict[str, Any] = {**pairs, "user": user}
    if "chat" in pairs:
        try:
            chat = json.loads(pairs["chat"])
        except json.JSONDecodeError:
            return None
        if not isinstance(chat, dict):
            return None
        parsed["chat"] = chat
    return parsed


def trusted_chat_id(verified: dict[str, Any]) -> int:
    """Resolve the Telegram identity used to scope stored tokens.

    Private-chat Mini Apps often omit ``chat``; in that case user.id is the
    trusted one-to-one chat id used by the existing web/session model.
    """
    chat = verified.get("chat")
    if isinstance(chat, dict) and isinstance(chat.get("id"), int):
        return int(chat["id"])
    return int(verified["user"]["id"])
