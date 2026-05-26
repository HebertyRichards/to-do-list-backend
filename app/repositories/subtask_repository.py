from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Subtask


class SubtaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return (
            select(Subtask)
            .options(
                selectinload(Subtask.task),
                selectinload(Subtask.creator),
                selectinload(Subtask.assignee),
            )
        )

    async def get_by_id(self, subtask_id: int) -> Subtask | None:
        return await self.db.get(Subtask, subtask_id)

    async def get_by_slug(self, slug: str) -> Subtask | None:
        stmt = self._base_query().where(Subtask.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_task(self, task_id: int) -> list[Subtask]:
        stmt = self._base_query().where(Subtask.task_id == task_id).order_by(Subtask.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, subtask: Subtask) -> Subtask:
        self.db.add(subtask)
        await self.db.flush()
        await self.db.refresh(subtask, ["task", "creator", "assignee"])
        return subtask

    async def delete(self, subtask: Subtask) -> None:
        await self.db.delete(subtask)
        await self.db.flush()
