from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise ValueError("Fuso horário inválido. Use um nome IANA, ex.: America/Sao_Paulo.") from err
    return value


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    username: str
    avatar_url: str | None
    timezone: str
    onboarded: bool


class UpdateProfileInput(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=60)
    avatar_url: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)
    onboarded: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_timezone(value)
