"""Web Push (VAPID) subscription endpoints.

The frontend hits these to:
- discover the public VAPID key (used by the service worker `subscribe()` call),
- store a new subscription against the current user,
- delete a subscription on logout / user toggle.
"""

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbDep
from app.core.security import now_utc
from app.models.push_subscription import PushSubscription
from app.schemas.push import (
    PushSubscriptionIn,
    PushSubscriptionOut,
    PushUnsubscribeIn,
    VapidPublicKeyOut,
)
from app.services.push import get_public_key
from app.core.config import get_settings

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyOut)
def vapid_public_key() -> VapidPublicKeyOut:
    settings = get_settings()
    return VapidPublicKeyOut(public_key=get_public_key(), subject=settings.vapid_subject)


@router.get("/subscriptions", response_model=list[PushSubscriptionOut])
def list_subscriptions(db: DbDep, user: CurrentUser) -> list[PushSubscriptionOut]:
    rows = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user.id)
        .order_by(PushSubscription.created_at.desc())
        .all()
    )
    return [PushSubscriptionOut.model_validate(r) for r in rows]


@router.post(
    "/subscriptions", response_model=PushSubscriptionOut, status_code=status.HTTP_201_CREATED
)
def create_subscription(
    payload: PushSubscriptionIn, db: DbDep, user: CurrentUser
) -> PushSubscriptionOut:
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )
    if existing is None:
        existing = PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent,
        )
        db.add(existing)
    else:
        existing.user_id = user.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.user_agent = payload.user_agent
        existing.last_used_at = now_utc()
    db.commit()
    db.refresh(existing)
    return PushSubscriptionOut.model_validate(existing)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(payload: PushUnsubscribeIn, db: DbDep, user: CurrentUser) -> None:
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == payload.endpoint,
        PushSubscription.user_id == user.id,
    ).delete(synchronize_session=False)
    db.commit()
