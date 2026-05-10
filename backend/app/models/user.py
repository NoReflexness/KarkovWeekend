from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    PARENT = "parent"
    CHILD = "child"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int | None] = mapped_column(
        ForeignKey("families.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_picture_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.PARENT,
    )
    birthdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    parent_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_email: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notify_prompted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Highest chat-message id this user has read. Monotonically advanced via
    # `PUT /chat/read-state`. Used to render the "new messages" divider and
    # auto-scroll to it on the next visit.
    last_read_chat_message_id: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    family: Mapped["Family | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="members", foreign_keys=[family_id]
    )
    children: Mapped[list["User"]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_user_id],
        cascade="all, delete-orphan",
        single_parent=True,
    )
    parent: Mapped["User | None"] = relationship(
        back_populates="children",
        foreign_keys=[parent_user_id],
        remote_side="User.id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_child(self) -> bool:
        return self.role == UserRole.CHILD
