from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.task import TaskStatus


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime
    due_date: datetime

    @model_validator(mode="after")
    def _check_dates(self):
        if self.start_date > self.due_date:
            raise ValueError("start_date deve ser anterior ou igual a due_date")
        return self


class TaskCreate(TaskBase):
    category_id: int
    group_id: int | None = None
    assignee_user_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None
    status: TaskStatus | None = None
    category_id: int | None = None
    assignee_user_id: int | None = None
    tag_ids: list[int] | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    start_date: datetime
    due_date: datetime
    category_id: int
    creator_user_id: int
    owner_user_id: int | None
    group_id: int | None
    assignee_user_id: int | None
    tags: list[TagOut] = Field(default_factory=list)
