from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_per_person: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_per_night: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_utility: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
