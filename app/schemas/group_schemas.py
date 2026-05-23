from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.group_member import GroupRole
from app.models.join_request import JoinRequestStatus


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class GroupCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    admin_user_id: int
    key: str


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    admin_user_id: int
    member_count: int


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    role: GroupRole
    joined_at: datetime


class JoinGroupInput(BaseModel):
    key: str = Field(min_length=1, max_length=128)


class JoinRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    user_id: int
    username: str
    status: JoinRequestStatus
    expires_at: datetime
    created_at: datetime
