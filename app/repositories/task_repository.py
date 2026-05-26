import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Task


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return (
            select(Task)
            .options(
                selectinload(Task.tags),
                selectinload(Task.category),
                selectinload(Task.creator),
                selectinload(Task.assignee),
            )
        )

    async def get_by_id(self, task_id: int) -> Task | None:
        stmt = self._base_query().where(Task.id == task_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Task | None:
        stmt = self._base_query().where(Task.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Task]:
        stmt = self._base_query().where(Task.owner_user_id == user_id).order_by(Task.due_date)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_group(self, group_id: int) -> list[Task]:
        stmt = self._base_query().where(Task.group_id == group_id).order_by(Task.due_date)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, task: Task) -> Task:
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task, ["tags", "category", "creator", "assignee"])
        return task

    async def delete(self, task: Task) -> None:
        await self.db.delete(task)
        await self.db.flush()
