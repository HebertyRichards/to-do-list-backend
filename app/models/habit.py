import enum
import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

ALL_DAYS_MASK = 0b1111111


class HabitStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


def days_to_mask(days: list[int]) -> int:
    mask = 0
    for d in days:
        mask |= 1 << d
    return mask


def mask_to_days(mask: int) -> list[int]:
    return [d for d in range(7) if mask & (1 << d)]


def is_scheduled(mask: int, day: date) -> bool:
    return bool(mask & (1 << (day.isoweekday() % 7)))


class Habit(Base, TimestampMixin):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    every_day: Mapped[bool] = mapped_column(default=False, nullable=False)
    days_mask: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    entries = relationship(
        "HabitEntry", back_populates="habit", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "days_mask >= 1 AND days_mask <= 127",
            name="ck_habit_days_mask_range",
        ),
        CheckConstraint(
            "every_day = false OR days_mask = 127",
            name="ck_habit_every_day_mask",
        ),
        {"schema": "app"},
    )


class HabitEntry(Base, TimestampMixin):
    __tablename__ = "habit_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey("app.habits.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[HabitStatus] = mapped_column(
        Enum(HabitStatus, name="habit_status"),
        default=HabitStatus.pending,
        nullable=False,
    )

    habit = relationship("Habit", back_populates="entries")

    __table_args__ = (
        UniqueConstraint("habit_id", "entry_date", name="uq_habit_entry_date"),
        {"schema": "app"},
    )
