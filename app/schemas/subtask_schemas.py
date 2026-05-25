from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from app.models.task import TaskStatus


class SubtaskCreate(BaseModel):
    task_slug: str
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime
    due_date: datetime
    assignee_username: str | None = None

    @model_validator(mode="after")
    def _check_dates(self):
        if self.start_date > self.due_date:
            raise ValueError("start_date deve ser anterior ou igual a due_date")
        return self


class SubtaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime | None = None
    due_date: datetime | None = None
    status: TaskStatus | None = None
    assignee_username: str | None = None


class SubtaskOut(BaseModel):
    slug: str
    task_slug: str
    title: str
    description: str | None
    status: TaskStatus
    start_date: datetime
    due_date: datetime
    created_at: datetime
    creator_username: str
    assignee_username: str | None = None
