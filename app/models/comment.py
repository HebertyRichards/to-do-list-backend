import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author_user_id: Mapped[uuid.UUID] = mapped_column(
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

    author = relationship("User", foreign_keys=[author_user_id])
    task = relationship("Task", foreign_keys=[task_id])
    subtask = relationship("Subtask", foreign_keys=[subtask_id])

    __table_args__ = (
        CheckConstraint(
            "(task_id IS NOT NULL) <> (subtask_id IS NOT NULL)",
            name="ck_comment_target_exclusive",
        ),
        {"schema": "app"},
    )
