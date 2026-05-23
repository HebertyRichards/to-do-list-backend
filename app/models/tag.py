from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL) <> (group_id IS NOT NULL)",
            name="ck_tag_scope_exclusive",
        ),
        UniqueConstraint("name", "owner_user_id", name="uq_tag_name_owner"),
        UniqueConstraint("name", "group_id", name="uq_tag_name_group"),
    )
