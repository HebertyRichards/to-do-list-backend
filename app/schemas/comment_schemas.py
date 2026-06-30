from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    slug: str
    body: str
    author_username: str
    author_avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool
