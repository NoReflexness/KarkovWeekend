import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

JWT_ALG = "HS256"


def now_utc() -> datetime:
    """Return tz-aware UTC datetime."""
    return datetime.now(UTC)


def is_past(dt: datetime | None) -> bool:
    """Compare against now-UTC, normalising naive datetimes (SQLite) to UTC."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt < now_utc()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | int, ttl_minutes: int | None = None) -> str:
    settings = get_settings()
    ttl = ttl_minutes or settings.access_token_ttl_minutes
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALG)  # noqa: DTZ005


def create_refresh_token(subject: str | int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.refresh_token_ttl_minutes)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALG])
    except JWTError as e:
        raise ValueError(str(e)) from e


def random_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)
