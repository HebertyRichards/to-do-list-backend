from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user_id: int, limit: int = 50) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, notification: Notification) -> Notification:
        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)
        return notification

    async def mark_read(self, user_id: int, notification_id: int) -> None:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)

    async def mark_all_read(self, user_id: int) -> None:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
