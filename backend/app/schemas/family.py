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


class SetupLinkRecipient(BaseModel):
    """Summary entry for a `send-setup-links` recipient.

    Source distinguishes pre-existing parents (sent a password-reset token via
    /nulstil-adgangskode) from invite-token rows (sent the classic invite
    /registrer link). Both produce a one-shot URL that lets the user pick a
    password.
    """

    user_id: int | None = None
    invite_id: int | None = None
    email: str
    source: str  # "password_reset" | "invite_token"


class SetupLinkResult(BaseModel):
    sent: int
    skipped_no_email: int
    recipients: list[SetupLinkRecipient]
