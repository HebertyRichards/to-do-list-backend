from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Category, User
from app.repositories.category_repository import CategoryRepository
from app.repositories.group_repository import GroupRepository
from app.schemas.category_schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.utils.security import generate_slug


class CategoryService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = CategoryRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: CategoryCreate) -> CategoryOut:
        if data.group_slug:
            group = await self.groups.get_by_slug(data.group_slug)
            if not group:
                raise AppException(ErrorCode.GROUP_NOT_FOUND)
            if not await self.groups.get_member(group.id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            cat = Category(slug=generate_slug(), name=data.name, color=data.color, group_id=group.id)
        else:
            cat = Category(slug=generate_slug(), name=data.name, color=data.color, owner_user_id=user.id)

        cat = await self.repo.create(cat)
        await self.db.commit()
        return CategoryOut.model_validate(cat)

    async def list_user(self, user: User) -> list[CategoryOut]:
        cats = await self.repo.list_for_user(user.id)
        return [CategoryOut.model_validate(c) for c in cats]

    async def list_group(self, user: User, group_slug: str) -> list[CategoryOut]:
        group = await self.groups.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if not await self.groups.get_member(group.id, user.id):
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        cats = await self.repo.list_for_group(group.id)
        return [CategoryOut.model_validate(c) for c in cats]

    async def update(self, user: User, category_slug: str, data: CategoryUpdate) -> CategoryOut:
        cat = await self._get_owned(user, category_slug)
        if data.name is not None:
            cat.name = data.name
        if data.color is not None:
            cat.color = data.color
        await self.db.flush()
        await self.db.commit()
        return CategoryOut.model_validate(cat)

    async def delete(self, user: User, category_slug: str) -> None:
        cat = await self._get_owned(user, category_slug)
        await self.repo.delete(cat)
        await self.db.commit()

    async def _get_owned(self, user: User, category_slug: str) -> Category:
        cat = await self.repo.get_by_slug(category_slug)
        if not cat:
            raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
        if cat.owner_user_id != user.id:
            if cat.group_id:
                if not await self.groups.get_member(cat.group_id, user.id):
                    raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            else:
                raise AppException(ErrorCode.FORBIDDEN)
        return cat
