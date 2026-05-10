"""Notifications: post system messages to the global chat and (optionally) email.

Notifiable events are the things mentioned in prompt.md: when users add events,
activities, or sign themselves up to events/chors/activities. Plain user
chat messages are NOT notifiable.

Design notes:
- Public surface is the small `notify_*` functions; routers should call those
  directly so the wording lives in one place.
- We never raise from here: a notification failure must not break the user
  action that triggered it.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage, ChatMessageKind
from app.models.user import User, UserRole
from app.services.email import get_email_sender
from app.services.notification_queue import (
    queue_activity_join,
    queue_attendance_change,
    queue_chor_assign,
)

log = logging.getLogger(__name__)


def _post_system_message(
    db: Session,
    *,
    body: str,
    icon: str | None = None,
    related_event_id: int | None = None,
    actor_user_id: int | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        kind=ChatMessageKind.SYSTEM,
        user_id=actor_user_id,
        body=body,
        icon=icon,
        related_event_id=related_event_id,
    )
    db.add(msg)
    db.flush()
    _email_opted_in(db, subject="Karkov", body=body, exclude_user_id=actor_user_id)
    return msg


def _email_opted_in(
    db: Session, *, subject: str, body: str, exclude_user_id: int | None
) -> None:
    """Email every user who opted in, except the actor (they did the thing)."""
    sender = get_email_sender()
    q = (
        db.query(User)
        .filter(User.notify_email.is_(True))
        .filter(User.email.is_not(None))
        .filter(User.role != UserRole.CHILD)
    )
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    for u in q.all():
        try:
            sender.send(db, to=u.email, subject=subject, body=body)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            log.exception("Failed to send notification email to %s", u.email)


def _safe(fn):
    """Decorator: never raise from a notification call site."""

    def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return fn(*args, **kwargs)
        except Exception:  # noqa: BLE001
            log.exception("notification %s failed", fn.__name__)
            return None

    wrapped.__name__ = fn.__name__
    return wrapped


# ---- Public surface --------------------------------------------------------


@_safe
def notify_event_created(db: Session, *, actor: User, event_name: str, event_id: int) -> None:
    _post_system_message(
        db,
        body=f"{actor.name} oprettede arrangementet '{event_name}'.",
        icon="calendar-plus",
        related_event_id=event_id,
        actor_user_id=actor.id,
    )


@_safe
def notify_attendance_changed(
    db: Session,
    *,
    actor: User,
    event_name: str,
    event_id: int,
    days_added: int,
    days_removed: int,
) -> None:
    """Coalesced via the notification queue — see notification_queue.py."""
    queue_attendance_change(
        db,
        actor=actor,
        event_name=event_name,
        event_id=event_id,
        days_added=days_added,
        days_removed=days_removed,
    )


@_safe
def notify_activity_created(
    db: Session, *, actor: User, event_name: str, event_id: int, activity_name: str
) -> None:
    _post_system_message(
        db,
        body=f"{actor.name} tilføjede aktiviteten '{activity_name}' til '{event_name}'.",
        icon="sparkles",
        related_event_id=event_id,
        actor_user_id=actor.id,
    )


@_safe
def notify_activity_joined(
    db: Session,
    *,
    actor: User,
    target_name: str,
    activity_name: str,
    event_id: int | None,
) -> None:
    """Coalesced via the notification queue — see notification_queue.py."""
    queue_activity_join(
        db,
        actor=actor,
        event_id=event_id,
        activity_name=activity_name,
        target_name=target_name,
    )


@_safe
def notify_chor_assigned(
    db: Session,
    *,
    actor: User,
    target_name: str,
    chor_label: str,
    event_id: int | None,
) -> None:
    """Coalesced via the notification queue — see notification_queue.py."""
    queue_chor_assign(
        db,
        actor=actor,
        event_id=event_id,
        chor_label=chor_label,
        target_name=target_name,
    )


@_safe
def notify_summerhouse_added(
    db: Session,
    *,
    actor: User,
    event_name: str,
    event_id: int,
    url: str,
) -> None:
    _post_system_message(
        db,
        body=(
            f"{actor.name} har tilføjet et feriehus til '{event_name}'. "
            f"Se det her: {url}"
        ),
        icon="house",
        related_event_id=event_id,
        actor_user_id=actor.id,
    )


@_safe
def notify_event_finalized(db: Session, *, actor: User, event_name: str, event_id: int) -> None:
    _post_system_message(
        db,
        body=f"Arrangementet '{event_name}' er afsluttet. Det endelige regnskab er klar.",
        icon="trophy",
        related_event_id=event_id,
        actor_user_id=actor.id,
    )
