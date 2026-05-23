from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Subtask, User
from app.repositories.group_repository import GroupRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate


class SubtaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = SubtaskRepository(db)
        self.tasks = TaskRepository(db)
        self.groups = GroupRepository(db)

    async def create(self, user: User, data: SubtaskCreate) -> SubtaskOut:
        if data.start_date > data.due_date:
            raise AppException(ErrorCode.DATE_RANGE_INVALID)

        task = await self.tasks.get_by_id(data.task_id)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)

        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
            if data.assignee_user_id:
                if not await self.groups.get_member(task.group_id, data.assignee_user_id):
                    raise AppException(ErrorCode.ASSIGNEE_NOT_IN_GROUP)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)

        subtask = Subtask(
            task_id=data.task_id,
            title=data.title,
            description=data.description,
            start_date=data.start_date,
            due_date=data.due_date,
            creator_user_id=user.id,
            assignee_user_id=data.assignee_user_id,
        )
        subtask = await self.repo.create(subtask)
        await self.db.commit()
        return SubtaskOut.model_validate(subtask)

    async def list_for_task(self, user: User, task_id: int) -> list[SubtaskOut]:
        task = await self.tasks.get_by_id(task_id)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        subtasks = await self.repo.list_for_task(task_id)
        return [SubtaskOut.model_validate(s) for s in subtasks]

    async def update(self, user: User, subtask_id: int, data: SubtaskUpdate) -> SubtaskOut:
        subtask = await self._get_accessible(user, subtask_id)
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
        if data.assignee_user_id is not None:
            subtask.assignee_user_id = data.assignee_user_id
        await self.db.flush()
        await self.db.commit()
        return SubtaskOut.model_validate(subtask)

    async def delete(self, user: User, subtask_id: int) -> None:
        subtask = await self._get_accessible(user, subtask_id)
        await self.repo.delete(subtask)
        await self.db.commit()

    async def _get_accessible(self, user: User, subtask_id: int) -> Subtask:
        subtask = await self.repo.get_by_id(subtask_id)
        if not subtask:
            raise AppException(ErrorCode.SUBTASK_NOT_FOUND)
        task = await self.tasks.get_by_id(subtask.task_id)
        if task and task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task and task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return subtask
