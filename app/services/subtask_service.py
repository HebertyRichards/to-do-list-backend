import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Notification, Subtask, User
from app.models.notification import NotificationType
from app.repositories.group_repository import GroupRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate
from app.utils.security import generate_slug
from app.ws.manager import notification_manager


class SubtaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = SubtaskRepository(db)
        self.tasks = TaskRepository(db)
        self.groups = GroupRepository(db)
        self.notifs = NotificationRepository(db)

    async def create(self, user: User, data: SubtaskCreate) -> SubtaskOut:
        task = await self.tasks.get_by_slug(data.task_slug)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)

        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)

        assignee_user_id = await self._resolve_assignee(
            data.assignee_username, group_id=task.group_id
        )

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

        if assignee_user_id and assignee_user_id != user.id:
            await self._notify_assignee(subtask, task.slug, assignee_user_id, user.username)

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

        previous_assignee = subtask.assignee_user_id
        if data.assignee_username is not None:
            new_assignee_id = await self._resolve_assignee(
                data.assignee_username, group_id=subtask.task.group_id
            )
            subtask.assignee_user_id = new_assignee_id

        await self.db.flush()
        await self.db.refresh(subtask, ["creator", "assignee"])

        if (
            subtask.assignee_user_id
            and subtask.assignee_user_id != previous_assignee
            and subtask.assignee_user_id != user.id
        ):
            await self._notify_assignee(
                subtask, subtask.task.slug, subtask.assignee_user_id, user.username
            )

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

    async def _resolve_assignee(
        self, assignee_username: str | None, group_id: int | None
    ) -> uuid.UUID | None:
        if not assignee_username:
            return None
        user_repo = UserRepository(self.db)
        assignee = await user_repo.get_by_username(assignee_username)
        if not assignee:
            raise AppException(ErrorCode.USER_NOT_FOUND)
        if group_id and not await self.groups.get_member(group_id, assignee.id):
            raise AppException(ErrorCode.ASSIGNEE_NOT_IN_GROUP)
        return assignee.id

    async def _notify_assignee(
        self,
        subtask: Subtask,
        task_slug: str,
        assignee_user_id: uuid.UUID,
        assigner_username: str,
    ) -> None:
        notif = Notification(
            user_id=assignee_user_id,
            type=NotificationType.subtask_assigned,
            title=f"{assigner_username} atribuiu uma subtarefa a você: {subtask.title}",
            payload={
                "subtask_slug": subtask.slug,
                "task_slug": task_slug,
                "assigned_by": assigner_username,
            },
        )
        await self.notifs.create(notif)
        await notification_manager.push(
            assignee_user_id,
            {
                "type": NotificationType.subtask_assigned.value,
                "subtask_slug": subtask.slug,
                "task_slug": task_slug,
                "assigned_by": assigner_username,
            },
        )

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
