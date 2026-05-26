import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NotificationType(str, enum.Enum):
    join_request_created = "join_request_created"
    join_request_accepted = "join_request_accepted"
    join_request_rejected = "join_request_rejected"
    task_assigned = "task_assigned"
    subtask_assigned = "subtask_assigned"
    member_removed = "member_removed"
    group_deleted = "group_deleted"


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
