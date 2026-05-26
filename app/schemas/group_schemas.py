from datetime import datetime

from pydantic import BaseModel, Field

from app.models.group_member import GroupRole
from app.models.join_request import JoinRequestStatus


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class GroupCreated(BaseModel):
    slug: str
    name: str
    description: str | None
    key: str


class GroupOut(BaseModel):
    slug: str
    name: str
    description: str | None
    member_count: int


class GroupMemberOut(BaseModel):
    username: str
    role: GroupRole
    joined_at: datetime


class JoinGroupInput(BaseModel):
    key: str = Field(min_length=1, max_length=128)


class JoinRequestOut(BaseModel):
    slug: str
    username: str
    status: JoinRequestStatus
    expires_at: datetime
    created_at: datetime
