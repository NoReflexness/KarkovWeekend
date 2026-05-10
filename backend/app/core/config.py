from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "KarkovWeekend"
    environment: str = "development"
    debug: bool = True

    # Default to local SQLite for fast dev/test; override with DATABASE_URL in compose.
    database_url: str = "sqlite:///./karkov.db"

    secret_key: str = Field(default="dev-only-change-me-please-32chars-min!!", min_length=32)
    access_token_ttl_minutes: int = 60 * 24 * 7
    refresh_token_ttl_minutes: int = 60 * 24 * 30
    cookie_domain: str | None = None
    cookie_secure: bool = False  # set true in prod
    cookie_samesite: str = "lax"

    admin_email: str = "admin@karkov.example.com"
    admin_password: str = "admin1234"
    admin_name: str = "Administrator"

    cors_origins: list[str] = ["http://localhost:3000"]

    uploads_dir: Path = Path("uploads")
    public_base_url: str = "http://localhost:8000"

    # Email delivery. When SMTP host is set, the SMTP sender is used; otherwise
    # we fall back to the dev outbox sender (writes to DB + stdout).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_starttls: bool = True
    smtp_from_address: str = "no-reply@karkov.example.com"
    smtp_from_name: str = "Karkov Weekend"

    # Notifications coalescing window. Repeat actions by the same user on the
    # same event (sign up for several days, take several chors, etc.) merge
    # into one chat message after this many seconds of quiet. Tests can set
    # this to 0 to flush immediately.
    notification_debounce_seconds: int = 60

    # Chat live-update stream (SSE). The endpoint polls the database every
    # `chat_stream_poll_seconds`, emits keepalives every ~25s, and auto-closes
    # after `chat_stream_max_seconds` so the client reconnects on a fresh DB
    # session. Tests may set the poll interval to 0 to drain immediately.
    chat_stream_poll_seconds: float = 1.5
    chat_stream_max_seconds: float = 300.0
    chat_stream_keepalive_seconds: float = 25.0

    # Web Push (VAPID). When set, /push endpoints use these keys to send
    # notifications to opted-in users. If unset, the backend auto-generates an
    # ephemeral keypair on startup *for development only* — these keys do not
    # survive restarts, so production deployments must set them explicitly.
    # `vapid_private_key` is a PEM-encoded EC private key (P-256). The matching
    # `vapid_public_key` is a base64url-encoded uncompressed point.
    vapid_private_key: str | None = None
    vapid_public_key: str | None = None
    vapid_subject: str = "mailto:no-reply@karkov.example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
