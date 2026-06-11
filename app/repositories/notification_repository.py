import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(
        self, user_id: uuid.UUID, cursor: int | None = None, limit: int = 10
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if cursor is not None:
            stmt = stmt.where(Notification.id < cursor)
        stmt = stmt.order_by(Notification.id.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def create(self, notification: Notification) -> Notification:
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_read(self, user_id: uuid.UUID, notification_id: int) -> None:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
