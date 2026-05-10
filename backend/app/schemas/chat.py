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
