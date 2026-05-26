from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("app.groups.id", ondelete="CASCADE"), nullable=True, index=True
    )

    tasks = relationship("Task", back_populates="category", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL) <> (group_id IS NOT NULL)",
            name="ck_category_scope_exclusive",
        ),
        {"schema": "app"},
    )
