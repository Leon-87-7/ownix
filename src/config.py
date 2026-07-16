import asyncio
import contextlib
import json
import sqlite3

from cryptography.fernet import InvalidToken

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.utils.google_token_crypto import google_token_fernet


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str = Field(min_length=1)
    TELEGRAM_WEBHOOK_SECRET: str = Field(min_length=1)
    REDIS_URL: str = "redis://redis:6379/0"
    DB_PATH: str = "/app/data/jobs.db"
    LOG_LEVEL: str = "INFO"

    # --- Optional at startup; downstream slices validate at use-time ---
    WEBHOOK_URL: str = ""
    TELEGRAM_STICKER_GEMINI_FAIL: str = ""
    TELEGRAM_STICKER_DRIVE_FAIL: str = ""
    GITHUB_TOKEN: str = ""

    # Slices #2/#3 — sidecar
    FRAME_SERVICE_URL: str = "http://10.0.0.4:5151"
    TRANSCRIPT_SERVICE_URL: str = "http://host.docker.internal:5151"

    # Slice #2 — Brave
    BRAVE_API_KEY: str = ""
    ENABLE_BRAVE_SEARCH: bool = True

    # Article pipeline — Jina Reader
    JINA_API_KEY: str = ""

    # Slices #2/#3 — Google
    GOOGLE_SERVICE_ACCOUNT_JSON: str = "/app/credentials/service_account.json"
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REFRESH_TOKEN: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    GOOGLE_TOKEN_ENCRYPTION_KEY: str = ""
    GOOGLE_DRIVE_FOLDER_SHORT: str = ""
    GOOGLE_DRIVE_FOLDER_LONG: str = ""
    # Single consolidated workbook holding all per-domain tabs (ADR-0013).
    # Tabs: 'YouTube Transcript Index', 'Short Video Analysis',
    # 'Article Analysis', 'mini PRD'. Tab routing lives in src/services/sheets.py.
    GOOGLE_SHEETS_ID: str = ""
    # Document pipeline (#150) — GCS content-addressed store for PDFs + parsed
    # text. See docs/handoff/gcs-setup.md. Non-required: the hot path mocks it
    # in tests and only needs it when a real PDF is processed end-to-end.
    GOOGLE_STORAGE_BUCKET: str = ""

    # Slice #4 — Gemini enrichment
    GEMINI_FREE_API_KEY: str = ""
    GEMINI_PAID_API_KEY: str = ""

    # Slice #5 — Second Brain
    GOOGLE_DRIVE_FOLDER_BRAIN: str = ""
    # Space exports (issue #95 / S8)
    GOOGLE_DRIVE_FOLDER_EXPORTS: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    BRAIN_REFRESH_BATCH: int = 50
    BRAIN_MIN_SCORE: float = 0.5

    # Web dashboard (issue #84)
    SESSION_COOKIE_SECURE: bool = True  # set False only for local HTTP dev
    SESSION_BACKEND: str = "redis"  # "redis" in prod; "memory" for local browser auth loops
    MINI_APP_URL: str = ""
    DEV_LOGIN_ENABLED: bool = False

    # Slices #6/#7 — Mini-PRD
    GOOGLE_DRIVE_FOLDER_PRD: str = ""
    PRD_MAX_TRANSCRIPT_CHARS: int = 60_000
    PRD_INTENT_COOLDOWN_SECONDS: int = 15
    PRD_AUTO_MODEL: str = "gemini-2.5-flash"
    PRD_INTENT_MODEL: str = "gemini-2.5-pro"

    # Per-user export isolation (#202, ADR-0027). When set, only this chat's jobs
    # write to the operator's shared Drive/Sheets; everyone else's results stay in
    # Platform storage (GCS+DB) + Telegram + dashboard. Unset = export for all
    # (single-operator backward compat).
    OPERATOR_CHAT_ID: int | None = None

    # User-facing copy — the name shown in invite-gate messages ("ask X for access").
    # Falls back to generic phrasing when unset so a fresh deploy is not stuck with a specific name.
    ADMIN_CONTACT_NAME: str = ""

    # Comma-separated proxy peer CIDRs whose forwarded client-IP headers may be
    # trusted for anonymous preview rate limiting. Keep narrow unless the API is
    # only reachable through that proxy network.
    PREVIEW_TRUSTED_PROXY_CIDRS: str = "127.0.0.1/32,::1/128"

    def _google_token_readable(self, encrypted_token: str) -> bool:
        try:
            payload = (
                google_token_fernet(self.GOOGLE_TOKEN_ENCRYPTION_KEY)
                .decrypt(encrypted_token.encode())
                .decode()
            )
            json.loads(payload)
            return True
        except (RuntimeError, InvalidToken, json.JSONDecodeError, UnicodeDecodeError):
            return False

    async def export_blocked(self, chat_id: int | None) -> bool:
        """True when *chat_id* must NOT write to the operator's shared Drive/Sheets.

        Blocks only an explicit non-operator chat. A None chat_id (system/operator
        aggregate calls like brain rebuild) and an unset OPERATOR_CHAT_ID both pass.
        """
        if chat_id is not None:
            try:
                if await asyncio.to_thread(self._has_readable_google_token, chat_id):
                    return False
            except sqlite3.Error:
                return (
                    False
                    if self.OPERATOR_CHAT_ID is None
                    else chat_id != self.OPERATOR_CHAT_ID
                )
        return (
            self.OPERATOR_CHAT_ID is not None
            and chat_id is not None
            and chat_id != self.OPERATOR_CHAT_ID
        )

    def _has_readable_google_token(self, chat_id: int) -> bool:
        """Sync helper — runs inside asyncio.to_thread by export_blocked."""
        # closing() because sqlite3's context manager only wraps the transaction,
        # not the connection lifetime.
        with contextlib.closing(sqlite3.connect(self.DB_PATH)) as conn:
            cur = conn.execute(
                "SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1",
                (chat_id,),
            )
            row = cur.fetchone()
            return row is not None and self._google_token_readable(str(row[0]))


settings = (
    Settings()
)  # pyright: ignore[reportCallIssue] — required fields are populated from env, not literal args
