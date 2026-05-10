from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChatMessageKind(str, Enum):
    USER = "user"
    SYSTEM = "system"


class ChatMessage(Base):
    """Global chat room.

    System messages are posted automatically by the notifications service in
    response to notifiable events; user messages are free-form chatter and do
    NOT trigger notifications.
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ChatMessageKind] = mapped_column(
        SAEnum(
            ChatMessageKind,
            name="chat_message_kind",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ChatMessageKind.USER,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
