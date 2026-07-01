import uuid
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Notification, Subtask, Task, User
from app.models.notification import NotificationType
from app.models.task import TaskStatus
from app.repositories.group_repository import GroupRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate
from app.services.activity_recorder import ActivityRecorder, seconds_between
from app.utils.security import generate_slug
from app.ws.manager import notification_manager


class SubtaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = SubtaskRepository(db)
        self.tasks = TaskRepository(db)
        self.groups = GroupRepository(db)
        self.notifs = NotificationRepository(db)
        self.activity = ActivityRecorder(db)

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
            is_urgent=data.is_urgent,
        )
        subtask = await self.repo.create(subtask)

        self.activity.created(user.id, subtask_id=subtask.id)

        if assignee_user_id and assignee_user_id != user.id:
            await self._notify_assignee(subtask, task, assignee_user_id, user.username)

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

    async def list_user(self, user: User) -> list[SubtaskOut]:
        subtasks = await self.repo.list_for_user(user.id)
        return [self._subtask_out(s) for s in subtasks]

    async def list_group(self, user: User, group_slug: str) -> list[SubtaskOut]:
        group = await self.groups.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if not await self.groups.get_member(group.id, user.id):
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        subtasks = await self.repo.list_for_group(group.id)
        return [self._subtask_out(s) for s in subtasks]

    async def update(self, user: User, subtask_slug: str, data: SubtaskUpdate) -> SubtaskOut:
        subtask = await self._get_accessible(user, subtask_slug)
        now = datetime.now(timezone.utc)
        if data.title is not None:
            subtask.title = data.title
        if data.description is not None:
            subtask.description = data.description
        if data.start_date is not None or data.due_date is not None:
            if data.start_date is not None:
                subtask.start_date = data.start_date
            if data.due_date is not None:
                subtask.due_date = data.due_date
            self.activity.dates_changed(
                user.id, data.start_date, data.due_date, subtask_id=subtask.id
            )
        if data.status is not None and data.status != subtask.status:
            crosses_done_boundary = TaskStatus.done in (data.status, subtask.status)
            if crosses_done_boundary and user.id not in (
                subtask.creator_user_id,
                subtask.assignee_user_id,
            ):
                raise AppException(ErrorCode.COMPLETE_NOT_ALLOWED)
            held = None
            held_username = None
            if data.status == TaskStatus.done and subtask.assignee_user_id:
                held = seconds_between(subtask.assignee_changed_at, now)
                held_username = subtask.assignee.username if subtask.assignee else None
            self.activity.status_changed(
                user.id,
                subtask.status,
                data.status,
                seconds_between(subtask.status_changed_at, now),
                assignee_held_seconds=held,
                assignee_username=held_username,
                subtask_id=subtask.id,
            )
            subtask.status = data.status
            subtask.status_changed_at = now
        if data.is_urgent is not None and data.is_urgent != subtask.is_urgent:
            subtask.is_urgent = data.is_urgent
            self.activity.urgent_changed(user.id, data.is_urgent, subtask_id=subtask.id)

        previous_assignee = subtask.assignee_user_id
        if data.assignee_username is not None:
            new_assignee_id = await self._resolve_assignee(
                data.assignee_username, group_id=subtask.task.group_id
            )
            if new_assignee_id != previous_assignee:
                self.activity.assignee_changed(
                    user.id,
                    subtask.assignee.username if subtask.assignee else None,
                    data.assignee_username or None,
                    prev_held_seconds=(
                        seconds_between(subtask.assignee_changed_at, now)
                        if previous_assignee
                        else None
                    ),
                    subtask_id=subtask.id,
                )
                subtask.assignee_user_id = new_assignee_id
                subtask.assignee_changed_at = now

        await self.db.flush()
        await self.db.refresh(subtask, ["creator", "assignee"])

        if (
            subtask.assignee_user_id
            and subtask.assignee_user_id != previous_assignee
            and subtask.assignee_user_id != user.id
        ):
            await self._notify_assignee(
                subtask, subtask.task, subtask.assignee_user_id, user.username
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
        task: Task,
        assignee_user_id: uuid.UUID,
        assigner_username: str,
    ) -> None:
        payload: dict = {
            "subtask_slug": subtask.slug,
            "task_slug": task.slug,
            "assigned_by": assigner_username,
        }
        if task.group_id:
            group = await self.groups.get_by_id(task.group_id)
            if group:
                payload["group_slug"] = group.slug
                payload["group_name"] = group.name

        notif = Notification(
            user_id=assignee_user_id,
            type=NotificationType.subtask_assigned,
            title=f"{assigner_username} atribuiu uma subtarefa a você: {subtask.title}",
            payload=payload,
        )
        await self.notifs.create(notif)
        await notification_manager.push(
            assignee_user_id,
            {"type": NotificationType.subtask_assigned.value, **payload},
        )

    @staticmethod
    def _subtask_out(subtask: Subtask) -> SubtaskOut:
        is_overdue = (
            subtask.status != TaskStatus.done
            and subtask.due_date < datetime.now(timezone.utc)
        )
        return SubtaskOut(
            slug=subtask.slug,
            task_slug=subtask.task.slug,
            title=subtask.title,
            description=subtask.description,
            status=subtask.status,
            is_urgent=subtask.is_urgent,
            is_overdue=is_overdue,
            start_date=subtask.start_date,
            due_date=subtask.due_date,
            created_at=subtask.created_at,
            creator_username=subtask.creator.username,
            assignee_username=subtask.assignee.username if subtask.assignee else None,
            assignee_avatar_url=subtask.assignee.avatar_url if subtask.assignee else None,
        )
