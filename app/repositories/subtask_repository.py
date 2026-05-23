from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Subtask


class SubtaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, subtask_id: int) -> Subtask | None:
        return await self.db.get(Subtask, subtask_id)

    async def list_for_task(self, task_id: int) -> list[Subtask]:
        stmt = select(Subtask).where(Subtask.task_id == task_id).order_by(Subtask.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_assigned(self, user_id: int) -> list[Subtask]:
        stmt = select(Subtask).where(Subtask.assignee_user_id == user_id).order_by(Subtask.due_date)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, subtask: Subtask) -> Subtask:
        self.db.add(subtask)
        await self.db.flush()
        await self.db.refresh(subtask)
        return subtask

    async def delete(self, subtask: Subtask) -> None:
        await self.db.delete(subtask)
        await self.db.flush()
