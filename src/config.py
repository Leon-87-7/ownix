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

    # Slice #4 — Gemini enrichment
    GEMINI_FREE_API_KEY: str = ""
    GEMINI_PAID_API_KEY: str = ""

    # Slice #5 — Second Brain
    GOOGLE_DRIVE_FOLDER_BRAIN: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    BRAIN_REFRESH_BATCH: int = 50
    BRAIN_MIN_SCORE: float = 0.5

    # Web dashboard (issue #84)
    SESSION_COOKIE_SECURE: bool = True  # set False only for local HTTP dev

    # Slices #6/#7 — Mini-PRD
    GOOGLE_DRIVE_FOLDER_PRD: str = ""
    PRD_MAX_TRANSCRIPT_CHARS: int = 60_000
    PRD_INTENT_COOLDOWN_SECONDS: int = 15
    PRD_INCLUDE_FRAMES: bool = False
    PRD_AUTO_MODEL: str = "gemini-2.5-flash"
    PRD_INTENT_MODEL: str = "gemini-2.5-pro"


settings = Settings()
