"""Pydantic models for the Web Push subscription API."""

from datetime import datetime

from pydantic import BaseModel, Field


class VapidPublicKeyOut(BaseModel):
    public_key: str
    subject: str


class PushKeysIn(BaseModel):
    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=256)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    keys: PushKeysIn
    user_agent: str | None = Field(default=None, max_length=400)


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)


class PushSubscriptionOut(BaseModel):
    id: int
    endpoint: str
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}
