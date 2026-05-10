from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EventStatus(str, Enum):
    PLANLAGT = "planlagt"
    AABENT = "aabent"
    DELTAGELSE_LAAST = "deltagelse_laast"
    AFSLUTTET = "afsluttet"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summerhouse_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    host_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="event_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EventStatus.PLANLAGT,
    )
    bed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summerhouse_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summerhouse_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summerhouse_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    summerhouse_scraped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    days: Mapped[list["EventDay"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventDay.date",
    )


class EventDay(Base):
    __tablename__ = "event_days"
    __table_args__ = (UniqueConstraint("event_id", "date", name="uq_event_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    event: Mapped[Event] = relationship(back_populates="days")
    chors: Mapped[list["Chor"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="event_day", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="event_day", cascade="all, delete-orphan"
    )
    attendances: Mapped[list["Attendance"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="event_day", cascade="all, delete-orphan"
    )
