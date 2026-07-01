from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.activity import ActivityType


class ActivityOut(BaseModel):
    slug: str
    type: ActivityType
    payload: dict
    actor_username: str
    actor_avatar_url: str | None = None
    created_at: datetime


class TimelineItemOut(BaseModel):
    """Item unificado da timeline: comentário humano ou evento de sistema."""

    kind: Literal["comment", "activity"]
    slug: str
    created_at: datetime
    actor_username: str
    actor_avatar_url: str | None = None

    # comment-only
    body: str | None = None
    updated_at: datetime | None = None
    can_edit: bool = False
    can_delete: bool = False

    # activity-only
    type: ActivityType | None = None
    payload: dict | None = None
