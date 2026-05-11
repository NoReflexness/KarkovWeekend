from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import UserOut

__all__ = [
    "UserOut",
    "UserUpdate",
    "AdminUserUpdate",
    "ChildCreate",
    "ChildUpdate",
    "ChangePasswordRequest",
    "RoleUpdate",
]


class RoleUpdate(BaseModel):
    role: Literal["admin", "parent"]


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    birthdate: date | None = None


class AdminUserUpdate(BaseModel):
    """Admin-only update payload for any user (parent, admin, or child).

    `family_id` is special: presence in the payload is significant. Omit it
    to leave the user's family alone, send `null` to detach them, or send an
    integer to attach/move them. Detection uses Pydantic v2's
    `model_fields_set` in the route handler.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    birthdate: date | None = None
    email: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    family_id: int | None = None


class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    birthdate: date
    email: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class ChildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    birthdate: date | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
