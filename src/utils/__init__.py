def job_tag(job_id: str) -> str:
    return f"job_{job_id[-4:]}:"


def days_ago(iso_str: str | None, *, now=None) -> int:
    """Days between an ISO 8601 timestamp (``Z`` or offset-aware) and now. 0 on empty/unparseable input."""
    if not iso_str:
        return 0
    from datetime import datetime, timezone
    try:
        parsed = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return ((now or datetime.now(timezone.utc)) - parsed).days
    except Exception:
        return 0


def job_dashboard_url(job_id: str) -> str | None:
    """Absolute dashboard link for a job, or None if DASHBOARD_URL isn't configured."""
    from src.config import settings
    if not settings.DASHBOARD_URL:
        return None
    return f"{settings.DASHBOARD_URL.rstrip('/')}/jobs/{job_id}"


async def dashboard_button_row(job_id: str, chat_id: int) -> list[list[dict]]:
    """Inline-keyboard row that logs chat_id straight into the job's dashboard page,
    or [] if unconfigured or the handoff mint fails.

    Skips the Telegram Login Widget on purpose: the widget can't complete inside
    Telegram's own in-app browser (opening it there prompts a confusing full
    Telegram login), so the link carries a single-use handoff token instead —
    same mechanism as the Mini App -> Google connect handoff (src/api/auth.py).
    Best-effort like the rest of this module's buttons: a Redis/DB hiccup should
    drop the button, not the whole completion message.
    """
    from urllib.parse import urlencode

    from src.config import settings
    if not settings.DASHBOARD_URL:
        return []

    from src.auth import session as session_store
    from src.utils.logger import get_logger

    try:
        token = await session_store.mint_dashboard_handoff(chat_id, ttl=5 * 60)
    except Exception:
        get_logger(__name__).warning("dashboard_button.handoff_mint_failed", job_id=job_id, exc_info=True)
        return []

    base = settings.DASHBOARD_URL.rstrip("/")
    query = urlencode({"token": token, "job_id": job_id})
    url = f"{base}/api/auth/handoff?{query}"
    return [[{"text": "🔗 Open in Dashboard", "url": url}]]
