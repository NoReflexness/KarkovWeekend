from enum import Enum

from sqlalchemy import ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChorMeal(str, Enum):
    MORGENMAD = "morgenmad"
    FROKOST = "frokost"
    AFTENSMAD = "aftensmad"


class ChorAction(str, Enum):
    FORBEREDELSE = "forberedelse"
    OPRYDNING = "oprydning"


class Chor(Base):
    __tablename__ = "chors"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_day_id: Mapped[int] = mapped_column(
        ForeignKey("event_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meal: Mapped[ChorMeal] = mapped_column(
        SAEnum(ChorMeal, name="chor_meal", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    action: Mapped[ChorAction] = mapped_column(
        SAEnum(ChorAction, name="chor_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    assignee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    event_day = relationship("EventDay", back_populates="chors")
