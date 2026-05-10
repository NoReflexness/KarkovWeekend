"""Buffered notifications.

Some user actions (signing up for many event days, joining several activities,
taking multiple chors) would otherwise post one chat message per change and
spam the room. We instead enqueue these into `pending_notifications` and
flush them as one summarized message after a debounce window expires.

One row exists per (actor_user_id, kind, event_id) at any given time; further
changes for the same key merge counters and extend the flush_at deadline.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PendingNotificationKind(str, Enum):
    ATTENDANCE = "attendance"
    ACTIVITY = "activity"
    CHOR = "chor"


class PendingNotification(Base):
    __tablename__ = "pending_notifications"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id", "kind", "event_id", name="uq_pending_notif_key"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[PendingNotificationKind] = mapped_column(
        SAEnum(
            PendingNotificationKind,
            name="pending_notification_kind",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    flush_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
