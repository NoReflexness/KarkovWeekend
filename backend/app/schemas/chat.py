from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Literal["user", "system"]
    user_id: int | None
    user_name: str | None = None
    body: str
    related_event_id: int | None
    icon: str | None
    created_at: datetime


class ChatMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class NotifyPrefIn(BaseModel):
    notify_email: bool


class NotifyPrefOut(BaseModel):
    notify_email: bool | None
    notify_prompted_at: datetime | None
    needs_prompt: bool


class ReadStateOut(BaseModel):
    """Per-user "last read chat message id" + the current latest id.

    The frontend uses `last_read_message_id` to render the "new messages"
    divider, and `latest_message_id` to know how far it can advance the
    marker after the user has dwelt on the chat.
    """

    last_read_message_id: int
    latest_message_id: int


class ReadStateIn(BaseModel):
    last_read_message_id: int = Field(ge=0)
