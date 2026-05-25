from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Subtask, User
from app.repositories.group_repository import GroupRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate
from app.utils.security import generate_slug


class SubtaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = SubtaskRepository(db)
        self.tasks = TaskRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: SubtaskCreate) -> SubtaskOut:
        task = await self.tasks.get_by_slug(data.task_slug)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)

        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)

        assignee_user_id = None
        if data.assignee_username:
            user_repo = UserRepository(self.db)
            assignee = await user_repo.get_by_username(data.assignee_username)
            if not assignee:
                raise AppException(ErrorCode.USER_NOT_FOUND)
            if task.group_id and not await self.groups.get_member(task.group_id, assignee.id):
                raise AppException(ErrorCode.ASSIGNEE_NOT_IN_GROUP)
            assignee_user_id = assignee.id

        subtask = Subtask(
            slug=generate_slug(),
            task_id=task.id,
            title=data.title,
            description=data.description,
            start_date=data.start_date,
            due_date=data.due_date,
            creator_user_id=user.id,
            assignee_user_id=assignee_user_id,
        )
        subtask = await self.repo.create(subtask)
        await self.db.commit()
        return self._subtask_out(subtask)

    async def list_for_task(self, user: User, task_slug: str) -> list[SubtaskOut]:
        task = await self.tasks.get_by_slug(task_slug)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        subtasks = await self.repo.list_for_task(task.id)
        return [self._subtask_out(s) for s in subtasks]

    async def update(self, user: User, subtask_slug: str, data: SubtaskUpdate) -> SubtaskOut:
        subtask = await self._get_accessible(user, subtask_slug)
        if data.title is not None:
            subtask.title = data.title
        if data.description is not None:
            subtask.description = data.description
        if data.start_date is not None:
            subtask.start_date = data.start_date
        if data.due_date is not None:
            subtask.due_date = data.due_date
        if data.status is not None:
            subtask.status = data.status
        if data.assignee_username is not None:
            user_repo = UserRepository(self.db)
            assignee = await user_repo.get_by_username(data.assignee_username)
            if not assignee:
                raise AppException(ErrorCode.USER_NOT_FOUND)
            subtask.assignee_user_id = assignee.id
            await self.db.flush()
            await self.db.refresh(subtask, ["creator", "assignee"])
        else:
            await self.db.flush()
        await self.db.commit()
        return self._subtask_out(subtask)

    async def delete(self, user: User, subtask_slug: str) -> None:
        subtask = await self._get_accessible(user, subtask_slug)
        await self.repo.delete(subtask)
        await self.db.commit()

    async def _get_accessible(self, user: User, subtask_slug: str) -> Subtask:
        subtask = await self.repo.get_by_slug(subtask_slug)
        if not subtask:
            raise AppException(ErrorCode.SUBTASK_NOT_FOUND)
        task = subtask.task
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return subtask

    @staticmethod
    def _subtask_out(subtask: Subtask) -> SubtaskOut:
        return SubtaskOut(
            slug=subtask.slug,
            task_slug=subtask.task.slug,
            title=subtask.title,
            description=subtask.description,
            status=subtask.status,
            start_date=subtask.start_date,
            due_date=subtask.due_date,
            created_at=subtask.created_at,
            creator_username=subtask.creator.username,
            assignee_username=subtask.assignee.username if subtask.assignee else None,
        )
