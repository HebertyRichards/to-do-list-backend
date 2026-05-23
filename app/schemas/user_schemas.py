from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    onboarded: bool


class UpdateProfileInput(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)
    onboarded: bool | None = None
