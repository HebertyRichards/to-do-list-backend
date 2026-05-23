from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Tag, Task, User
from app.models.group_member import GroupRole
from app.models.task import TaskStatus
from app.repositories.category_repository import CategoryRepository
from app.repositories.group_repository import GroupRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task_schemas import TaskCreate, TaskOut, TaskUpdate


class TaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = TaskRepository(db)
        self.cats = CategoryRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: TaskCreate) -> TaskOut:
        if data.start_date > data.due_date:
            raise AppException(ErrorCode.DATE_RANGE_INVALID)

        cat = await self.cats.get_by_id(data.category_id)
        if not cat:
            raise AppException(ErrorCode.CATEGORY_NOT_FOUND)

        if data.group_id:
            member = await self.groups.get_member(data.group_id, user.id)
            if not member:
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            if data.assignee_user_id and data.assignee_user_id != user.id:
                assignee_member = await self.groups.get_member(data.group_id, data.assignee_user_id)
                if not assignee_member:
                    raise AppException(ErrorCode.ASSIGNEE_NOT_IN_GROUP)

        tags = await self._resolve_tags(data.tag_ids)
        task = Task(
            title=data.title,
            description=data.description,
            start_date=data.start_date,
            due_date=data.due_date,
            category_id=data.category_id,
            creator_user_id=user.id,
            owner_user_id=None if data.group_id else user.id,
            group_id=data.group_id,
            assignee_user_id=data.assignee_user_id,
            tags=tags,
        )
        task = await self.repo.create(task)
        await self.db.commit()
        return TaskOut.model_validate(task)

    async def list_user(self, user: User) -> list[TaskOut]:
        tasks = await self.repo.list_for_user(user.id)
        return [TaskOut.model_validate(t) for t in tasks]

    async def list_group(self, user: User, group_id: int) -> list[TaskOut]:
        if not await self.groups.get_member(group_id, user.id):
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        tasks = await self.repo.list_for_group(group_id)
        return [TaskOut.model_validate(t) for t in tasks]

    async def update(self, user: User, task_id: int, data: TaskUpdate) -> TaskOut:
        task = await self._get_accessible(user, task_id)

        if data.start_date or data.due_date:
            start = data.start_date or task.start_date
            due = data.due_date or task.due_date
            if start > due:
                raise AppException(ErrorCode.DATE_RANGE_INVALID)

        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description
        if data.start_date is not None:
            task.start_date = data.start_date
        if data.due_date is not None:
            task.due_date = data.due_date
        if data.status is not None:
            task.status = data.status
        if data.category_id is not None:
            task.category_id = data.category_id
        if data.assignee_user_id is not None:
            task.assignee_user_id = data.assignee_user_id
        if data.tag_ids is not None:
            task.tags = await self._resolve_tags(data.tag_ids)

        await self.db.flush()
        await self.db.commit()
        return TaskOut.model_validate(task)

    async def delete(self, user: User, task_id: int) -> None:
        task = await self._get_accessible(user, task_id)

        if task.group_id:
            member = await self.groups.get_member(task.group_id, user.id)
            if member and member.role != GroupRole.admin and task.creator_user_id != user.id:
                raise AppException(ErrorCode.FORBIDDEN)

        await self.repo.delete(task)
        await self.db.commit()

    async def _get_accessible(self, user: User, task_id: int) -> Task:
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return task

    async def _resolve_tags(self, tag_ids: list[int]) -> list[Tag]:
        if not tag_ids:
            return []
        stmt = select(Tag).where(Tag.id.in_(tag_ids))
        return list((await self.db.execute(stmt)).scalars().all())
