"""Print a browser-console snippet that logs in as a brand-new Telegram user.

Signs a Telegram Login Widget payload with the local TELEGRAM_BOT_TOKEN for a
tg id that has never hit the DB, bypassing the widget/domain-registration
requirement entirely. Paste the printed fetch() into devtools while on the
dev site (localhost:3000) — the real /api/auth/telegram endpoint runs, a real
session cookie gets set, and the actual pending/email-gate UI renders on your
next navigation, no mock, no BotFather domain needed.

Usage: python -m scripts.dev_new_user_login [tg_id]
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import sys
import time

from src.config import settings


def _sign(data: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def main() -> None:
    tg_id = sys.argv[1] if len(sys.argv) > 1 else str(random.randint(10**8, 10**9 - 1))

    payload = {
        "id": tg_id,
        "first_name": "New Guy",
        "auth_date": str(int(time.time())),
    }
    payload["hash"] = _sign(payload, settings.TELEGRAM_BOT_TOKEN)

    print(f"# tg id {tg_id} — must not already exist in the DB to see the new-user flow")
    print(
        "fetch('/api/auth/telegram', {method:'POST', headers:{'Content-Type':'application/json'}, "
        f"body: {json.dumps(json.dumps(payload))}}}).then(r => location.href = '/feed');"
    )


if __name__ == "__main__":
    main()
