from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ikke logget ind")
    try:
        payload = decode_token(access_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ugyldigt token"
        ) from e
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Forkert tokentype")
    user_id = int(payload["sub"])
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bruger findes ikke")
    # Best-effort flush of debounced notifications. Never block the request.
    try:
        from app.services.notification_queue import flush_due_pending_notifications

        if flush_due_pending_notifications(db):
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole) -> Callable[[User], User]:
    def _dep(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Manglende rettigheder"
            )
        return user

    return _dep


require_admin = require_role(UserRole.ADMIN)
require_not_child = require_role(UserRole.ADMIN, UserRole.PARENT)
