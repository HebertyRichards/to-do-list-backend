from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.habit import HabitStatus


def _validate_days(days: list[int]) -> None:
    for d in days:
        if d < 0 or d > 6:
            raise ValueError(
                "days_of_week deve conter valores entre 0 (domingo) e 6 (sábado)."
            )


class HabitBase(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    every_day: bool = False
    days_of_week: list[int] = Field(
        default_factory=list,
        description="Dias da semana: 0=domingo … 6=sábado. Ignorado quando every_day=true.",
    )

    @model_validator(mode="after")
    def _check_days(self):
        if self.every_day:
            return self
        if not self.days_of_week:
            raise ValueError("Selecione ao menos um dia ou marque every_day.")
        _validate_days(self.days_of_week)
        return self


class HabitCreate(HabitBase):
    pass


class HabitUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    every_day: bool | None = None
    days_of_week: list[int] | None = None

    @model_validator(mode="after")
    def _check_days(self):
        if self.days_of_week is not None:
            _validate_days(self.days_of_week)
        return self


class HabitStatusUpdate(BaseModel):
    status: HabitStatus
    date: date_type | None = Field(
        default=None, description="Dia do registro. Omita para usar hoje (UTC)."
    )


class HabitOut(BaseModel):
    slug: str
    title: str
    description: str | None
    every_day: bool
    days_of_week: list[int]
    scheduled_today: bool
    today_status: HabitStatus | None = None
    created_at: datetime


class HabitStatsOut(BaseModel):
    date: date_type
    daily_scheduled: int
    daily_done: int
    daily_percent: float
    month: str
    monthly_scheduled: int
    monthly_done: int
    monthly_percent: float
