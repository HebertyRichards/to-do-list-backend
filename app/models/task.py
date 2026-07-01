import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.tag import task_tags


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), default=TaskStatus.pending, nullable=False
    )

    is_urgent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    position: Mapped[float] = mapped_column(
        Float, default=0.0, server_default="0", nullable=False
    )

    # Timestamps de quando a tarefa entrou no estado atual de cada dimensão.
    # Servem para calcular durações ("permaneceu N tempo") no log de atividade.
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    category_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    assignee_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("app.categories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    creator_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    category = relationship("Category", back_populates="tasks")
    creator = relationship("User", foreign_keys=[creator_user_id])
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
        Index("ix_task_category_position", "category_id", "position"),
        {"schema": "app"},
    )
