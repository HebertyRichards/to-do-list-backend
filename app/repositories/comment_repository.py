from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment


class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _base_query(self):
        return select(Comment).options(selectinload(Comment.author))

    async def get_by_slug(self, slug: str) -> Comment | None:
        stmt = self._base_query().where(Comment.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_task(self, task_id: int) -> list[Comment]:
        stmt = self._base_query().where(Comment.task_id == task_id).order_by(Comment.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_subtask(self, subtask_id: int) -> list[Comment]:
        stmt = (
            self._base_query()
            .where(Comment.subtask_id == subtask_id)
            .order_by(Comment.created_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, comment: Comment) -> Comment:
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment, ["author"])
        return comment

    async def delete(self, comment: Comment) -> None:
        await self.db.delete(comment)
        await self.db.flush()
