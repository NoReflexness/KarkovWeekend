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
    """Admin-only update payload for any user (parent, admin, or child)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    birthdate: date | None = None
    email: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


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
