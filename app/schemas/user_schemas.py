from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    username: str
    avatar_url: str | None
    onboarded: bool


class UpdateProfileInput(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=60)
    avatar_url: str | None = Field(default=None, max_length=500)
    onboarded: bool | None = None
