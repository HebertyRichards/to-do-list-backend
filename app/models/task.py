import enum
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.tag import task_tags


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), default=TaskStatus.pending, nullable=False
    )

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("app.categories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creator_user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    assignee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category = relationship("Category", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_user_id])
    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=task_tags, lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL) <> (group_id IS NOT NULL)",
            name="ck_task_scope_exclusive",
        ),
        CheckConstraint(
            "start_date <= due_date",
            name="ck_task_dates",
        ),
        {"schema": "app"},
    )
