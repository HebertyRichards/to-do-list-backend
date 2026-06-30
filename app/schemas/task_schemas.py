from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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
    category_slug: str
    assignee_username: str | None = None
    is_urgent: bool = False
    tag_names: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None
    status: TaskStatus | None = None
    is_urgent: bool | None = None
    category_slug: str | None = None
    assignee_username: str | None = Field(
        default=None,
        description="Omita ou envie null para não alterar. Envie string vazia para desatribuir.",
    )
    tag_names: list[str] | None = None


class TagOut(BaseModel):
    name: str
    color: str | None


class TaskOut(BaseModel):
    slug: str
    title: str
    description: str | None
    status: TaskStatus
    is_urgent: bool
    is_overdue: bool
    start_date: datetime
    due_date: datetime
    created_at: datetime
    creator_username: str
    category_slug: str
    assignee_username: str | None = None
    assignee_avatar_url: str | None = None
    tags: list[TagOut] = Field(default_factory=list)
    subtask_done_count: int = 0
    subtask_total_count: int = 0
