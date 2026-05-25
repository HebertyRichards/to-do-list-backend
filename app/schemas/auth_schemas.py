import re
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

_PASSWORD_RULES = [
    (r"[A-Z]", "A senha deve conter ao menos uma letra maiúscula"),
    (r"[a-z]", "A senha deve conter ao menos uma letra minúscula"),
    (r"[0-9]", "A senha deve conter ao menos um número"),
    (r"[^A-Za-z0-9]", "A senha deve conter ao menos um caractere especial"),
]


def _validate_password(v: str) -> str:
    for pattern, msg in _PASSWORD_RULES:
        if not re.search(pattern, v):
            raise ValueError(msg)
    return v


class RegisterInput(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    username: str
    avatar_url: str | None
    onboarded: bool


class SessionInfo(BaseModel):
    user: CurrentUser
    session_expires_at: datetime
    access_expires_at: datetime


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordInput(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return _validate_password(v)

    @model_validator(mode="after")
    def _passwords_match(self) -> "ResetPasswordInput":
        if self.new_password != self.confirm_new_password:
            raise ValueError("As senhas não coincidem")
        return self
