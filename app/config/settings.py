from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(...)
    log_level: str = Field(...)

    database_url: str = Field(...)
    database_url_sync: str = Field(...)

    redis_url: str = Field(...)
    redis_enabled: bool = Field(default=True)

    jwt_secret: str = Field(...)
    jwt_algorithm: str = Field(...)
    access_token_minutes: int = Field(...)
    refresh_token_days: int = Field(...)

    trust_forwarded_for: bool = Field(default=False)

    frontend_origin: str = Field(...)
    cookie_domain: str = Field(default="")
    cookie_secure: bool = Field(...)
    cookie_samesite: str = Field(...)
    email_user: str = Field(...)
    email_pass: str = Field(...)

    @field_validator("email_pass", "email_user", mode="before")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
