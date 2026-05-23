from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Category, User
from app.repositories.category_repository import CategoryRepository
from app.repositories.group_repository import GroupRepository
from app.schemas.category_schemas import CategoryCreate, CategoryOut, CategoryUpdate


class CategoryService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = CategoryRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: CategoryCreate) -> CategoryOut:
        if data.group_id:
            member = await self.groups.get_member(data.group_id, user.id)
            if not member:
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            cat = Category(name=data.name, color=data.color, group_id=data.group_id)
        else:
            cat = Category(name=data.name, color=data.color, owner_user_id=user.id)

        cat = await self.repo.create(cat)
        await self.db.commit()
        return CategoryOut.model_validate(cat)

    async def list_user(self, user: User) -> list[CategoryOut]:
        cats = await self.repo.list_for_user(user.id)
        return [CategoryOut.model_validate(c) for c in cats]

    async def list_group(self, user: User, group_id: int) -> list[CategoryOut]:
        member = await self.groups.get_member(group_id, user.id)
        if not member:
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        cats = await self.repo.list_for_group(group_id)
        return [CategoryOut.model_validate(c) for c in cats]

    async def update(self, user: User, category_id: int, data: CategoryUpdate) -> CategoryOut:
        cat = await self._get_owned(user, category_id)
        if data.name is not None:
            cat.name = data.name
        if data.color is not None:
            cat.color = data.color
        await self.db.flush()
        await self.db.commit()
        return CategoryOut.model_validate(cat)

    async def delete(self, user: User, category_id: int) -> None:
        cat = await self._get_owned(user, category_id)
        await self.repo.delete(cat)
        await self.db.commit()

    async def _get_owned(self, user: User, category_id: int) -> Category:
        cat = await self.repo.get_by_id(category_id)
        if not cat:
            raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
        if cat.owner_user_id != user.id:
            if cat.group_id:
                member = await self.groups.get_member(cat.group_id, user.id)
                if not member:
                    raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            else:
                raise AppException(ErrorCode.FORBIDDEN)
        return cat
