"""Coalesce repeated notifications into a single summary chat message.

Sign-ups for several days, joins of several activities, or taking several
chors in quick succession are merged into one row in `pending_notifications`.
After `settings.notification_debounce_seconds` of quiet, the row is flushed
into the chat as one summary message and the row is deleted.

Public API:
- `queue_attendance_change(...)` / `queue_activity_join(...)` / `queue_chor_assign(...)`
- `flush_due_pending_notifications(db)` — flushes everything past its deadline
- `flush_all_pending_notifications(db)` — forces flush regardless of deadline
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import now_utc
from app.models.chat_message import ChatMessage, ChatMessageKind
from app.models.event import Event
from app.models.pending_notification import (
    PendingNotification,
    PendingNotificationKind,
)
from app.models.user import User, UserRole
from app.services.email import get_email_sender

log = logging.getLogger(__name__)


# ---- Internal helpers ------------------------------------------------------


def _debounce() -> timedelta:
    return timedelta(seconds=int(get_settings().notification_debounce_seconds))


def _upsert(
    db: Session,
    *,
    actor_user_id: int,
    kind: PendingNotificationKind,
    event_id: int | None,
    merge: callable,  # type: ignore[valid-type]
) -> PendingNotification:
    """Get-or-create a pending row and apply `merge(data)` to its data dict."""
    row = (
        db.query(PendingNotification)
        .filter(
            PendingNotification.actor_user_id == actor_user_id,
            PendingNotification.kind == kind,
            PendingNotification.event_id == event_id,
        )
        .one_or_none()
    )
    now = now_utc()
    deadline = now + _debounce()
    if row is None:
        data: dict[str, Any] = {}
        merge(data)
        row = PendingNotification(
            actor_user_id=actor_user_id,
            kind=kind,
            event_id=event_id,
            data=data,
            flush_at=deadline,
        )
        db.add(row)
        db.flush()
        return row
    # Merge into a copy so SQLAlchemy notices JSON change.
    new_data = dict(row.data or {})
    merge(new_data)
    row.data = new_data
    row.flush_at = deadline
    row.updated_at = now
    db.flush()
    return row


# ---- Public enqueue API ----------------------------------------------------


def queue_attendance_change(
    db: Session,
    *,
    actor: User,
    event_name: str,
    event_id: int,
    days_added: int,
    days_removed: int,
) -> None:
    if days_added == 0 and days_removed == 0:
        return

    def _merge(data: dict[str, Any]) -> None:
        data["event_name"] = event_name
        data["days_added"] = int(data.get("days_added", 0)) + days_added
        data["days_removed"] = int(data.get("days_removed", 0)) + days_removed

    _upsert(
        db,
        actor_user_id=actor.id,
        kind=PendingNotificationKind.ATTENDANCE,
        event_id=event_id,
        merge=_merge,
    )
    _maybe_flush_immediately(db)


def queue_activity_join(
    db: Session,
    *,
    actor: User,
    event_id: int | None,
    activity_name: str,
    target_name: str,
) -> None:
    """Record an activity join. We coalesce by (actor, event)."""

    def _merge(data: dict[str, Any]) -> None:
        items = list(data.get("joins", []))
        items.append({"activity": activity_name, "target": target_name})
        data["joins"] = items

    _upsert(
        db,
        actor_user_id=actor.id,
        kind=PendingNotificationKind.ACTIVITY,
        event_id=event_id,
        merge=_merge,
    )
    _maybe_flush_immediately(db)


def queue_chor_assign(
    db: Session,
    *,
    actor: User,
    event_id: int | None,
    chor_label: str,
    target_name: str,
) -> None:
    """Record a chor assignment. We coalesce by (actor, event)."""

    def _merge(data: dict[str, Any]) -> None:
        items = list(data.get("assigns", []))
        items.append({"chor": chor_label, "target": target_name})
        data["assigns"] = items

    _upsert(
        db,
        actor_user_id=actor.id,
        kind=PendingNotificationKind.CHOR,
        event_id=event_id,
        merge=_merge,
    )
    _maybe_flush_immediately(db)


# ---- Flush ----------------------------------------------------------------


def _maybe_flush_immediately(db: Session) -> None:
    """If the debounce window is zero (tests), flush right away."""
    if _debounce().total_seconds() <= 0:
        flush_due_pending_notifications(db)


def flush_due_pending_notifications(db: Session, *, now: datetime | None = None) -> int:
    """Flush all rows whose `flush_at` is in the past. Returns rows flushed."""
    cutoff = now or now_utc()
    rows = (
        db.query(PendingNotification)
        .filter(PendingNotification.flush_at <= cutoff)
        .order_by(PendingNotification.flush_at.asc())
        .all()
    )
    return _flush_rows(db, rows)


def flush_all_pending_notifications(db: Session) -> int:
    """Force-flush everything regardless of deadline (admin/test only)."""
    rows = db.query(PendingNotification).order_by(PendingNotification.flush_at.asc()).all()
    return _flush_rows(db, rows)


def _flush_rows(db: Session, rows: list[PendingNotification]) -> int:
    if not rows:
        return 0
    actor_ids = {r.actor_user_id for r in rows}
    event_ids = {r.event_id for r in rows if r.event_id is not None}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()}
    events = (
        {e.id: e for e in db.query(Event).filter(Event.id.in_(event_ids)).all()}
        if event_ids
        else {}
    )
    for row in rows:
        try:
            actor = actors.get(row.actor_user_id)
            if actor is None:
                # Actor was deleted while pending. Drop the row silently.
                db.delete(row)
                continue
            ev_name = (
                row.data.get("event_name")
                if isinstance(row.data, dict) and row.data.get("event_name")
                else (events.get(row.event_id).name if row.event_id in events else None)
            )
            body, icon = _summarize(row, actor=actor, event_name=ev_name)
            if body:
                _post_message(
                    db,
                    body=body,
                    icon=icon,
                    actor_user_id=actor.id,
                    related_event_id=row.event_id,
                )
        except Exception:  # noqa: BLE001
            log.exception("Failed to flush pending notification %s", row.id)
        finally:
            db.delete(row)
    db.flush()
    return len(rows)


def _summarize(
    row: PendingNotification, *, actor: User, event_name: str | None
) -> tuple[str | None, str | None]:
    data = row.data or {}
    event_part = f" på '{event_name}'" if event_name else ""
    if row.kind == PendingNotificationKind.ATTENDANCE:
        added = int(data.get("days_added", 0))
        removed = int(data.get("days_removed", 0))
        if added == 0 and removed == 0:
            return None, None
        parts: list[str] = []
        if added:
            parts.append(f"tilmeldte sig {added} dag{'e' if added != 1 else ''}")
        if removed:
            parts.append(f"meldte fra på {removed} dag{'e' if removed != 1 else ''}")
        return f"{actor.name} {' og '.join(parts)}{event_part}.", "user-check"
    if row.kind == PendingNotificationKind.ACTIVITY:
        joins = data.get("joins") or []
        if not joins:
            return None, None
        return _summarize_targets_and_items(
            actor=actor,
            items=joins,
            item_key="activity",
            verb="tilmeldte",
            noun_singular="aktiviteten",
            noun_plural="aktiviteter",
            event_part=event_part,
        ), "user-plus"
    if row.kind == PendingNotificationKind.CHOR:
        assigns = data.get("assigns") or []
        if not assigns:
            return None, None
        return _summarize_targets_and_items(
            actor=actor,
            items=assigns,
            item_key="chor",
            verb="tog",
            noun_singular="opgaven",
            noun_plural="opgaver",
            event_part=event_part,
        ), "hand"
    return None, None


def _summarize_targets_and_items(
    *,
    actor: User,
    items: list[dict[str, str]],
    item_key: str,
    verb: str,
    noun_singular: str,
    noun_plural: str,
    event_part: str,
) -> str:
    """Build "<actor> <verb> <noun> X, Y og Z til <who>." with sane grouping.

    When all targets are the same: one "til <who>" suffix.
    Otherwise we group items by target.
    """
    by_target: dict[str, list[str]] = {}
    for it in items:
        name = (it.get(item_key) or "").strip()
        target = (it.get("target") or "").strip()
        if not name:
            continue
        by_target.setdefault(target, []).append(name)

    def _who(target: str) -> str:
        return "sig selv" if target == actor.name else target

    def _join_names(names: list[str]) -> str:
        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            unique.append(n)
        if len(unique) == 1:
            return unique[0]
        return ", ".join(unique[:-1]) + " og " + unique[-1]

    if len(by_target) == 1:
        target, names = next(iter(by_target.items()))
        noun = noun_singular if len(set(names)) == 1 else noun_plural
        return (
            f"{actor.name} {verb} {noun} {_join_names(names)} til {_who(target)}{event_part}."
        )

    chunks: list[str] = []
    for target, names in by_target.items():
        noun = noun_singular if len(set(names)) == 1 else noun_plural
        chunks.append(f"{noun} {_join_names(names)} til {_who(target)}")
    return f"{actor.name} {verb} " + "; ".join(chunks) + f"{event_part}."


def _post_message(
    db: Session,
    *,
    body: str,
    icon: str | None,
    actor_user_id: int,
    related_event_id: int | None,
) -> None:
    msg = ChatMessage(
        kind=ChatMessageKind.SYSTEM,
        user_id=actor_user_id,
        body=body,
        icon=icon,
        related_event_id=related_event_id,
    )
    db.add(msg)
    db.flush()
    _email_opted_in(db, body=body, exclude_user_id=actor_user_id)


def _email_opted_in(db: Session, *, body: str, exclude_user_id: int | None) -> None:
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
            sender.send(db, to=u.email, subject="Karkov", body=body)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            log.exception("Failed to send notification email to %s", u.email)
