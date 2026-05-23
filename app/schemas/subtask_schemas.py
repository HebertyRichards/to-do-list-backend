from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.task import TaskStatus


class SubtaskCreate(BaseModel):
    task_id: int
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    start_date: datetime
    due_date: datetime
    assignee_user_id: int | None = None

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
    assignee_user_id: int | None = None


class SubtaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    title: str
    description: str | None
    status: TaskStatus
    start_date: datetime
    due_date: datetime
    creator_user_id: int
    assignee_user_id: int | None
