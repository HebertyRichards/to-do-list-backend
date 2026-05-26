import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class JoinRequestStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class JoinRequest(Base, TimestampMixin):
    __tablename__ = "join_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("app.groups.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[JoinRequestStatus] = mapped_column(
        Enum(JoinRequestStatus, name="join_request_status"),
        default=JoinRequestStatus.pending,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group = relationship("Group", back_populates="join_requests")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_join_request_pending", "group_id", "user_id", "status"),
        {"schema": "app"},
    )
