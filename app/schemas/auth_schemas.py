from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RegisterInput(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    full_name: str | None
    avatar_url: str | None
    onboarded: bool


class SessionInfo(BaseModel):
    user: CurrentUser
    session_expires_at: datetime
    access_expires_at: datetime
