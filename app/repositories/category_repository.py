from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, category_id: int) -> Category | None:
        return await self.db.get(Category, category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[Category]:
        stmt = select(Category).where(Category.owner_user_id == user_id).order_by(Category.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_group(self, group_id: int) -> list[Category]:
        stmt = select(Category).where(Category.group_id == group_id).order_by(Category.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, category: Category) -> Category:
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        await self.db.delete(category)
        await self.db.flush()
