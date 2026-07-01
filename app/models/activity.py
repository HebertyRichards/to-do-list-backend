import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ActivityType(str, enum.Enum):
    created = "created"
    status_changed = "status_changed"
    delivered = "delivered"  # status -> done
    reopened = "reopened"  # done -> pending
    category_moved = "category_moved"  # apenas task
    assignee_changed = "assignee_changed"  # alocou / desalocou / trocou
    urgent_changed = "urgent_changed"
    dates_changed = "dates_changed"


class Activity(Base):
    """Evento imutável (append-only) de ação sobre uma tarefa ou subtarefa.

    Compõe, junto dos comentários, a timeline unificada. O payload guarda os
    detalhes de cada tipo (from/to, target_username, duration_seconds, ...).
    """

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)

    type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, name="activity_type"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    subtask_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.subtasks.id", ondelete="CASCADE"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor = relationship("User", foreign_keys=[actor_user_id])
    task = relationship("Task", foreign_keys=[task_id])
    subtask = relationship("Subtask", foreign_keys=[subtask_id])

    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL) <> (subtask_id IS NOT NULL)",
            name="ck_activity_target_exclusive",
        ),
        {"schema": "app"},
    )
