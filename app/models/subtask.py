import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.task import TaskStatus


class Subtask(Base, TimestampMixin):
    __tablename__ = "subtasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", create_type=False),
        default=TaskStatus.pending,
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("app.tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creator_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    task = relationship("Task", back_populates="subtasks")
    creator = relationship("User", foreign_keys=[creator_user_id])
    assignee = relationship("User", foreign_keys=[assignee_user_id])

    __table_args__ = (
        CheckConstraint("start_date <= due_date", name="ck_subtask_dates"),
        {"schema": "app"},
    )
