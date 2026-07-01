from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Activity


class ActivityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return select(Activity).options(selectinload(Activity.actor))

    async def list_for_task(self, task_id: int) -> list[Activity]:
        stmt = (
            self._base_query()
            .where(Activity.task_id == task_id)
            .order_by(Activity.created_at, Activity.id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_subtask(self, subtask_id: int) -> list[Activity]:
        stmt = (
            self._base_query()
            .where(Activity.subtask_id == subtask_id)
            .order_by(Activity.created_at, Activity.id)
        )
        return list((await self.db.execute(stmt)).scalars().all())
