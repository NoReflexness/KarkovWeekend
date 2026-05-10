"""Web Push (VAPID) sender + dev keypair helpers.

The runtime keys come from `Settings.vapid_private_key` / `vapid_public_key`. If
they are unset (typical for fresh dev installs), we generate an ephemeral
P-256 keypair the first time the service is touched. These dev keys are
intentionally process-local: restarting invalidates every browser
subscription. Production deployments should set both env vars.
"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.push_subscription import PushSubscription

log = logging.getLogger(__name__)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@lru_cache(maxsize=1)
def _vapid_keys() -> tuple[str, str]:
    """Return `(private_pem, public_b64url_uncompressed)`.

    Reads from settings, otherwise generates an ephemeral keypair.
    """
    settings = get_settings()
    if settings.vapid_private_key and settings.vapid_public_key:
        return settings.vapid_private_key, settings.vapid_public_key

    log.warning(
        "VAPID_PRIVATE_KEY/VAPID_PUBLIC_KEY are not set; generating ephemeral "
        "dev keys. Web Push subscriptions will be invalidated on restart."
    )
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_numbers = private_key.public_key().public_numbers()
    x = public_numbers.x.to_bytes(32, "big")
    y = public_numbers.y.to_bytes(32, "big")
    public_b64 = _b64url(b"\x04" + x + y)
    return private_pem, public_b64


def get_public_key() -> str:
    return _vapid_keys()[1]


def get_private_pem() -> str:
    return _vapid_keys()[0]


def reset_vapid_cache() -> None:
    """Clear the cached keypair (used by tests and after settings reloads)."""
    _vapid_keys.cache_clear()


def send_to_subscription(
    sub: PushSubscription, *, payload: dict, ttl: int = 60
) -> bool:
    """Best-effort push. Returns True on accept, False on permanent failure."""
    try:
        # Imported lazily so missing pywebpush at import time does not break boot.
        from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
    except Exception:  # noqa: BLE001
        log.exception("pywebpush not available; cannot send push")
        return False

    settings = get_settings()
    subscription_info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=get_private_pem(),
            vapid_claims={"sub": settings.vapid_subject},
            ttl=ttl,
        )
        return True
    except WebPushException as e:  # type: ignore[misc]
        status = getattr(e.response, "status_code", None)
        # 404/410 mean the subscription is permanently gone; caller should drop it.
        if status in (404, 410):
            return False
        log.warning("Web push transient failure (%s): %s", status, e)
        return True  # keep the subscription alive
    except Exception:  # noqa: BLE001
        log.exception("Web push send failed")
        return True


def fan_out(
    db: Session,
    *,
    user_ids: list[int],
    title: str,
    body: str,
    url: str | None = None,
    icon: str | None = None,
) -> int:
    """Send the same payload to all subscriptions of `user_ids`.

    Returns the number of subscriptions successfully delivered to. Stale
    subscriptions (404/410) are removed from the database.
    """
    if not user_ids:
        return 0
    subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id.in_(user_ids))
        .all()
    )
    if not subs:
        return 0
    payload = {"title": title, "body": body, "url": url, "icon": icon}
    delivered = 0
    drop: list[int] = []
    for sub in subs:
        ok = send_to_subscription(sub, payload=payload)
        if ok:
            delivered += 1
        else:
            drop.append(sub.id)
    if drop:
        db.query(PushSubscription).filter(PushSubscription.id.in_(drop)).delete(
            synchronize_session=False
        )
        db.commit()
    return delivered
