from datetime import time as Time

from pydantic import BaseModel, Field


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    time: Time | None = None


class ActivityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    time: Time | None = None


class AttendeesIn(BaseModel):
    user_ids: list[int]


class ChorAssignIn(BaseModel):
    user_id: int
