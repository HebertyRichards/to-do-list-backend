from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Tag, Task, task_tags


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_id: int) -> Task | None:
        stmt = (
            select(Task)
            .options(selectinload(Task.tags))
            .where(Task.id == task_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.tags))
            .where(Task.owner_user_id == user_id)
            .order_by(Task.due_date)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_group(self, group_id: int) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.tags))
            .where(Task.group_id == group_id)
            .order_by(Task.due_date)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_assigned(self, user_id: int) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.tags))
            .where(Task.assignee_user_id == user_id)
            .order_by(Task.due_date)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, task: Task) -> Task:
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task, ["tags"])
        return task

    async def delete(self, task: Task) -> None:
        await self.db.delete(task)
        await self.db.flush()
