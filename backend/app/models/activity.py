from datetime import datetime, time

from sqlalchemy import DateTime, ForeignKey, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_day_id: Mapped[int] = mapped_column(
        ForeignKey("event_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event_day = relationship("EventDay", back_populates="activities")
    attendees: Mapped[list["ActivityAttendee"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )


class ActivityAttendee(Base):
    __tablename__ = "activity_attendees"

    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    activity = relationship("Activity", back_populates="attendees")
