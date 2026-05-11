from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    token: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    birthdate: date | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    name: str
    role: UserRole
    family_id: int | None
    profile_picture_url: str | None
    birthdate: date | None
    parent_user_id: int | None
    # True iff the user has a password set. Admins use this to identify
    # imported-via-YAML users who haven't been "activated" yet, so they can
    # send them a setup link. Computed from `User.has_password` property.
    has_password: bool = False


class LoginResponse(BaseModel):
    user: UserOut
