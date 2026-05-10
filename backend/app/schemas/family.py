from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import UserOut


class FamilyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FamilyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    profile_picture_url: str | None = None


class FamilyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    profile_picture_url: str | None
    created_at: datetime
    members: list[UserOut] = []


class InviteCreate(BaseModel):
    email: EmailStr
    notify: bool = False


class InviteOut(BaseModel):
    id: int
    email: str
    family_id: int
    token: str
    expires_at: datetime
    notified_at: datetime | None = None
    used_at: datetime | None = None


class InviteSendResult(BaseModel):
    sent: int
    invites: list[InviteOut]
