from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Group(Base, TimestampMixin):
    __tablename__ = "groups"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    join_requests = relationship("JoinRequest", back_populates="group", cascade="all, delete-orphan")
