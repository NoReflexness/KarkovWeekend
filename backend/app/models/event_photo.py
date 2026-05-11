from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EventPhoto(Base):
    """A photo attached to an event.

    Anyone authenticated can upload; the uploader, the event host, or an admin
    can edit/delete. Exactly one photo per event can be marked as the "group
    photo" (enforced at the application layer — we just unset the previous
    group photo when a new one is marked).

    `taken_at` is best-effort extracted from EXIF DateTimeOriginal during upload
    so the gallery can sort chronologically even when batches are uploaded
    long after the fact.
    """

    __tablename__ = "event_photos"
    __table_args__ = (
        Index("ix_event_photos_event_id_taken_at", "event_id", "taken_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploader_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_group_photo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
