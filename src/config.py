from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str
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

    def export_blocked(self, chat_id: int | None) -> bool:
        """True when *chat_id* must NOT write to the operator's shared Drive/Sheets.

        Blocks only an explicit non-operator chat. A None chat_id (system/operator
        aggregate calls like brain rebuild) and an unset OPERATOR_CHAT_ID both pass.
        """
        return (
            self.OPERATOR_CHAT_ID is not None
            and chat_id is not None
            and chat_id != self.OPERATOR_CHAT_ID
        )


settings = Settings()
