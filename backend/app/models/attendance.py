from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Attendance(Base):
    __tablename__ = "attendances"

    event_day_id: Mapped[int] = mapped_column(
        ForeignKey("event_days.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    event_day = relationship("EventDay", back_populates="attendances")
    user = relationship("User")
