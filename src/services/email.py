"""Best-effort transactional email helpers.

Two emails bracket the invite lifecycle:

- ``send_welcome_email`` — an onboarding tour, sent the moment a user's email
  lands in the DB (they've requested access but aren't approved yet). It
  introduces the day-to-day features and carries a personal note; it makes no
  promise of Feed access, since that comes later.
- ``send_feed_ready_email`` — the original bare "your Feed is live" notice,
  sent on approval. Unchanged from its pre-onboarding-email behavior.
"""

from __future__ import annotations

import asyncio
import html
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

# Personal note from the developer (see the welcome email). Kept here rather
# than in config since it's a fixed authorial signature, not a deployment knob.
DEVELOPER_NAME = "Leon Eidelman"
DEVELOPER_ROLE = "Frontend developer · creator of Ownix"
DEVELOPER_GITHUB_URL = "https://github.com/leon-87-7"
DEVELOPER_LINKEDIN_URL = "https://www.linkedin.com/in/leon-eidelman-frontend"

# Brand tokens (DESIGN.md): dark plate + one rationed signal orange.
_PLATE = "#0d0e10"
_SIGNAL = "#f6921e"
_INK = "#20242a"
_BODY = "#3a3f46"
_MUTED = "#6b7178"
_LINE = "#e6e8ea"
_CANVAS = "#f6f7f8"
_SURFACE = "#ffffff"


def _feed_url() -> str | None:
    base = settings.DASHBOARD_URL.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/feed"


def _display_name(user: dict) -> str:
    return (
        " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x).strip()
        or "there"
    )


def _first_name(user: dict) -> str:
    return (user.get("first_name") or "").strip()


def _welcome_subject(user: dict) -> str:
    first = _first_name(user)
    if first:
        return f"Welcome to Ownix, {first} — here's the quick tour"
    return "Welcome to Ownix — here's the quick tour"


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def _send_email_sync(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


# --- Welcome email body builders ------------------------------------------
#
# The four day-to-day features a new user meets first (kept in sync between the
# HTML and plain-text bodies): in-app ingest (desktop keys + mobile OwnixAdd),
# the Link Table, tagging, and the Settings page.

_FEATURES: list[tuple[str, str]] = [
    (
        "Add from anywhere, in seconds",
        "On desktop, single keys do the work: press N to drop in a URL "
        "(Ownix figures out whether it's a video, article, repo, or doc), "
        "U to save a link as-is, D to upload a document, L to jump to your "
        "links, and / to search — or hit ⌘/Ctrl+Shift+K for the full "
        "command launcher. On mobile, tap OwnixAdd in the Feed tab bar for the "
        "same quick-add menu. (Prefer Telegram? Send any link to the Ownix bot "
        "and it lands in your Feed too.)",
    ),
    (
        "Your Link Table",
        "Every link Ownix pulls out of what you save lands in one sortable, "
        "searchable table — favicon, title, tags, and when you last saw it, "
        "with a live preview panel beside it. It's the fastest way back to that "
        "one link you know you saved.",
    ),
    (
        "Tags that mean something",
        "Label any item or link with your own tags — each with a name and a "
        "meaning — then filter your whole library down to exactly what "
        "you're after. Your taxonomy, your rules.",
    ),
    (
        "Settings, your way",
        "The Settings page is home base for your account and connected services, "
        "so you can tune Ownix to fit how you actually work.",
    ),
]

_STATUS_LINE = (
    "I'll approve your account shortly — you'll get a follow-up email with "
    "your Feed link the moment it's live."
)

_NOTE_PARAGRAPHS: list[str] = [
    "A quick hello — I'm Leon, the developer behind Ownix. I built it "
    "because I was tired of losing good links, videos, and docs across a dozen "
    "different apps, so Ownix is my attempt at a single place that actually "
    "remembers your internet for you.",
    "I care a lot about the small details — the keyboard shortcuts, the way "
    "a table sorts, the copy in this email — so if something feels off or you "
    "have an idea, I genuinely want to hear it. Thanks for giving it a try.",
]


def _build_welcome_text(name: str) -> str:
    lines: list[str] = [
        f"Hi {name},",
        "",
        "Welcome to Ownix! It's one place to save the links, videos, and docs "
        "you care about, and actually find them again. Here's what you'll reach "
        "for every day:",
        "",
    ]
    for i, (title, body) in enumerate(_FEATURES, start=1):
        lines.append(f"{i}. {title}")
        lines.append(f"   {body}")
        lines.append("")

    lines.append(_STATUS_LINE)
    lines.append("")
    lines.append("— A note from the developer —")
    lines.append("")
    lines.extend(_NOTE_PARAGRAPHS)
    lines.append("")
    lines.append(DEVELOPER_NAME)
    lines.append(DEVELOPER_ROLE)
    lines.append(f"GitHub:   {DEVELOPER_GITHUB_URL}")
    lines.append(f"LinkedIn: {DEVELOPER_LINKEDIN_URL}")
    return "\n".join(lines)


def _feature_rows_html() -> str:
    rows: list[str] = []
    for title, body in _FEATURES:
        rows.append(
            f'<tr><td style="padding:0 0 18px 0;">'
            f'<div style="font-size:15px;font-weight:700;color:{_INK};'
            f'line-height:1.35;">{html.escape(title)}</div>'
            f'<div style="margin-top:4px;font-size:14px;color:{_BODY};'
            f'line-height:1.6;">{html.escape(body)}</div>'
            f"</td></tr>"
        )
    return "".join(rows)


def _note_paragraphs_html() -> str:
    return "".join(
        f'<p style="margin:0 0 14px 0;font-size:14px;color:{_BODY};'
        f'line-height:1.65;">{html.escape(p)}</p>'
        for p in _NOTE_PARAGRAPHS
    )


def _build_welcome_html(name: str) -> str:
    safe_name = html.escape(name)
    preheader = "Welcome to Ownix — I'll approve your account shortly. A quick tour while you wait."
    font = (
        "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,"
        "Arial,sans-serif"
    )
    return f"""\
<!-- preheader --><div style="display:none;max-height:0;overflow:hidden;opacity:0;">\
{html.escape(preheader)}</div>
<div style="margin:0;padding:0;background-color:{_CANVAS};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" \
style="background-color:{_CANVAS};">
    <tr>
      <td align="center" style="padding:28px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" \
style="width:600px;max-width:100%;font-family:{font};">
          <!-- header band -->
          <tr>
            <td style="background-color:{_PLATE};border-radius:10px 10px 0 0;padding:26px 32px;">
              <div style="font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#ffffff;">\
Own<span style="color:{_SIGNAL};">ix</span></div>
              <div style="margin-top:4px;font-size:12px;letter-spacing:0.04em;color:#9aa0a6;">\
Your internet. Own it.</div>
            </td>
          </tr>
          <!-- body -->
          <tr>
            <td style="background-color:{_SURFACE};padding:32px;border-left:1px solid {_LINE};\
border-right:1px solid {_LINE};">
              <p style="margin:0 0 12px 0;font-size:16px;color:{_INK};">Hi {safe_name},</p>
              <p style="margin:0 0 20px 0;font-size:15px;color:{_BODY};line-height:1.6;">
                Welcome to Ownix! It's one place to save the links, videos, and docs you care
                about, and actually find them again. Here's what you'll reach for every day:
              </p>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                {_feature_rows_html()}
              </table>

              <!-- status callout (no action yet — access is still pending) -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" \
style="margin:6px 0 4px 0;">
                <tr>
                  <td style="background-color:{_CANVAS};border:1px solid {_LINE};\
border-left:3px solid {_SIGNAL};border-radius:6px;padding:14px 16px;font-size:14px;\
color:{_BODY};line-height:1.55;">
                    {html.escape(_STATUS_LINE)}
                  </td>
                </tr>
              </table>

              <!-- divider -->
              <div style="border-top:1px solid {_LINE};margin:28px 0 22px 0;"></div>

              <!-- personal note -->
              <div style="font-size:11px;font-weight:700;letter-spacing:0.09em;\
text-transform:uppercase;color:{_MUTED};margin-bottom:12px;">A note from the developer</div>
              {_note_paragraphs_html()}
              <p style="margin:18px 0 0 0;font-size:14px;color:{_INK};line-height:1.5;">
                <span style="font-weight:700;">{html.escape(DEVELOPER_NAME)}</span><br>
                <span style="color:{_MUTED};">{html.escape(DEVELOPER_ROLE)}</span><br>
                <a href="{html.escape(DEVELOPER_GITHUB_URL, quote=True)}" target="_blank" \
style="color:{_SIGNAL};text-decoration:none;">GitHub</a>
                <span style="color:{_LINE};">&nbsp;&middot;&nbsp;</span>
                <a href="{html.escape(DEVELOPER_LINKEDIN_URL, quote=True)}" target="_blank" \
style="color:{_SIGNAL};text-decoration:none;">LinkedIn</a>
              </p>
            </td>
          </tr>
          <!-- footer -->
          <tr>
            <td style="background-color:{_SURFACE};border-radius:0 0 10px 10px;\
border:1px solid {_LINE};border-top:none;padding:20px 32px;">
              <p style="margin:0;font-size:12px;color:{_MUTED};line-height:1.5;">
                You're receiving this because you requested access to Ownix.
                <br>Reply to this email if you need anything — it reaches a real person.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>"""


async def send_welcome_email(user: dict) -> bool:
    """Send the onboarding tour when a user's email first lands in the DB.

    Introduces the four day-to-day features (in-app ingest, the Link Table,
    tagging, and Settings) and closes with a personal note from the developer.
    The user is still pending approval here, so the email promises no Feed
    access — the approval email does that. Delivered as multipart HTML +
    plain-text; best-effort and a no-op when the user has no email or SMTP is
    unconfigured.
    """
    email = (user.get("email") or "").strip()
    if not email:
        log.info("welcome_email_skipped", tg_id=user.get("tg_id"), has_email=False)
        return False
    if not _smtp_configured():
        log.info("welcome_email_smtp_unconfigured", tg_id=user.get("tg_id"))
        return False

    name = _display_name(user)
    message = EmailMessage()
    message["Subject"] = _welcome_subject(user)
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(_build_welcome_text(name))
    message.add_alternative(_build_welcome_html(name), subtype="html")
    await asyncio.to_thread(_send_email_sync, message)
    log.info("welcome_email_sent", tg_id=user.get("tg_id"), email=email)
    return True


async def send_feed_ready_email(user: dict) -> bool:
    """Send the "your Feed is live" approval notice with the user's Feed URL.

    Fired on approval; the original bare notice, unchanged from before the
    onboarding email existed. Best-effort and a no-op when the user has no
    email, the dashboard URL is unset, or SMTP is unconfigured.
    """
    email = (user.get("email") or "").strip()
    feed_url = _feed_url()
    if not email or not feed_url:
        log.info(
            "feed_ready_email_skipped",
            tg_id=user.get("tg_id"),
            has_email=bool(email),
            has_dashboard_url=bool(feed_url),
        )
        return False
    if not _smtp_configured():
        log.info("feed_ready_email_smtp_unconfigured", tg_id=user.get("tg_id"))
        return False

    name = _display_name(user)
    message = EmailMessage()
    message["Subject"] = "You're in - your Ownix Feed is live"
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Hi {name},",
                "",
                "You're in - welcome to Ownix.",
                "",
                "Your Feed is live here:",
                feed_url,
                "",
                (
                    "Send the Ownix Telegram bot any link you want to save. "
                    "We'll process it and add it to your Feed."
                ),
                "",
                "Leon",
            ]
        )
    )
    await asyncio.to_thread(_send_email_sync, message)
    log.info("feed_ready_email_sent", tg_id=user.get("tg_id"), email=email)
    return True
