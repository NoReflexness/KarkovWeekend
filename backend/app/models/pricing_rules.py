from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PricingRules(Base):
    """Singleton row (id=1) controlling age cutoffs.

    - Babies: age <= baby_max_age, count 0 (free).
    - Kids: baby_max_age < age <= kid_max_age, count 0.5 on per-person costs.
    - Teens+adults: age > kid_max_age, count 1.0.
    """

    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    baby_max_age: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    kid_max_age: Mapped[int] = mapped_column(Integer, nullable=False, default=13)
