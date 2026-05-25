from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Tag, Task, User
from app.models.group_member import GroupRole
from app.repositories.category_repository import CategoryRepository
from app.repositories.group_repository import GroupRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task_schemas import TagOut, TaskCreate, TaskOut, TaskUpdate
from app.utils.security import generate_slug


class TaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = TaskRepository(db)
        self.cats = CategoryRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: TaskCreate) -> TaskOut:
        cat = await self.cats.get_by_slug(data.category_slug)
        if not cat:
            raise AppException(ErrorCode.CATEGORY_NOT_FOUND)

        if cat.group_id:
            if not await self.groups.get_member(cat.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)

        assignee_user_id = None
        if data.assignee_username:
            user_repo = UserRepository(self.db)
            assignee = await user_repo.get_by_username(data.assignee_username)
            if not assignee:
                raise AppException(ErrorCode.USER_NOT_FOUND)
            if cat.group_id and not await self.groups.get_member(cat.group_id, assignee.id):
                raise AppException(ErrorCode.ASSIGNEE_NOT_IN_GROUP)
            assignee_user_id = assignee.id

        tags = await self._resolve_or_create_tags(
            data.tag_names,
            owner_user_id=None if cat.group_id else user.id,
            group_id=cat.group_id,
        )

        task = Task(
            slug=generate_slug(),
            title=data.title,
            description=data.description,
            start_date=data.start_date,
            due_date=data.due_date,
            category_id=cat.id,
            creator_user_id=user.id,
            owner_user_id=None if cat.group_id else user.id,
            group_id=cat.group_id,
            assignee_user_id=assignee_user_id,
            tags=tags,
        )
        task = await self.repo.create(task)
        await self.db.commit()
        return self._task_out(task)

    async def list_user(self, user: User) -> list[TaskOut]:
        tasks = await self.repo.list_for_user(user.id)
        return [self._task_out(t) for t in tasks]

    async def list_group(self, user: User, group_slug: str) -> list[TaskOut]:
        group = await self.groups.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if not await self.groups.get_member(group.id, user.id):
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        tasks = await self.repo.list_for_group(group.id)
        return [self._task_out(t) for t in tasks]

    async def update(self, user: User, task_slug: str, data: TaskUpdate) -> TaskOut:
        task = await self._get_accessible(user, task_slug)

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
        if data.category_slug is not None:
            cat = await self.cats.get_by_slug(data.category_slug)
            if not cat:
                raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
            task.category_id = cat.id
        if data.assignee_username is not None:
            user_repo = UserRepository(self.db)
            assignee = await user_repo.get_by_username(data.assignee_username)
            if not assignee:
                raise AppException(ErrorCode.USER_NOT_FOUND)
            task.assignee_user_id = assignee.id
        if data.tag_names is not None:
            task.tags = await self._resolve_or_create_tags(
                data.tag_names,
                owner_user_id=task.owner_user_id,
                group_id=task.group_id,
            )

        await self.db.flush()
        await self.db.refresh(task, ["category", "creator", "assignee", "tags"])
        await self.db.commit()
        return self._task_out(task)

    async def delete(self, user: User, task_slug: str) -> None:
        task = await self._get_accessible(user, task_slug)

        if task.group_id:
            member = await self.groups.get_member(task.group_id, user.id)
            if member and member.role != GroupRole.admin and task.creator_user_id != user.id:
                raise AppException(ErrorCode.FORBIDDEN)

        await self.repo.delete(task)
        await self.db.commit()

    async def _get_accessible(self, user: User, task_slug: str) -> Task:
        task = await self.repo.get_by_slug(task_slug)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return task

    async def _resolve_or_create_tags(
        self, tag_names: list[str], owner_user_id: int | None, group_id: int | None
    ) -> list[Tag]:
        if not tag_names:
            return []
        tags = []
        for name in tag_names:
            if owner_user_id:
                stmt = select(Tag).where(Tag.name == name, Tag.owner_user_id == owner_user_id)
            else:
                stmt = select(Tag).where(Tag.name == name, Tag.group_id == group_id)
            tag = (await self.db.execute(stmt)).scalar_one_or_none()
            if not tag:
                tag = Tag(name=name, owner_user_id=owner_user_id, group_id=group_id)
                self.db.add(tag)
                await self.db.flush()
                await self.db.refresh(tag)
            tags.append(tag)
        return tags

    @staticmethod
    def _task_out(task: Task) -> TaskOut:
        return TaskOut(
            slug=task.slug,
            title=task.title,
            description=task.description,
            status=task.status,
            start_date=task.start_date,
            due_date=task.due_date,
            created_at=task.created_at,
            creator_username=task.creator.username,
            category_slug=task.category.slug,
            assignee_username=task.assignee.username if task.assignee else None,
            tags=[TagOut(name=t.name, color=t.color) for t in task.tags],
        )
