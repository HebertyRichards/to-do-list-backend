import uuid
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Category, Notification, Tag, Task, User
from app.models.group_member import GroupRole
from app.models.notification import NotificationType
from app.models.task import TaskStatus
from app.repositories.category_repository import CategoryRepository
from app.repositories.group_repository import GroupRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.task_schemas import TagOut, TaskCreate, TaskOut, TaskUpdate
from app.services.activity_recorder import ActivityRecorder, seconds_between
from app.utils.security import generate_slug
from app.ws.manager import notification_manager


class TaskService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = TaskRepository(db)
        self.cats = CategoryRepository(db)
        self.groups = GroupRepository(db)
        self.notifs = NotificationRepository(db)
        self.activity = ActivityRecorder(db)

    async def create(self, user: User, data: TaskCreate) -> TaskOut:
        cat = await self.cats.get_by_slug(data.category_slug)
        if not cat:
            raise AppException(ErrorCode.CATEGORY_NOT_FOUND)

        if cat.group_id:
            if not await self.groups.get_member(cat.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif cat.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)

        assignee_user_id = await self._resolve_assignee(
            data.assignee_username, group_id=cat.group_id
        )

        tags = await self._resolve_or_create_tags(
            data.tag_names,
            owner_user_id=None if cat.group_id else user.id,
            group_id=cat.group_id,
        )

        position = await self.repo.next_position(cat.id)

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
            is_urgent=data.is_urgent,
            position=position,
            tags=tags,
        )
        task = await self.repo.create(task)

        self.activity.created(user.id, task_id=task.id)

        if assignee_user_id and assignee_user_id != user.id:
            await self._notify_assignee(task, assignee_user_id, user.username)

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
        now = datetime.now(timezone.utc)

        if data.start_date or data.due_date:
            start = data.start_date or task.start_date
            due = data.due_date or task.due_date
            if start > due:
                raise AppException(ErrorCode.DATE_RANGE_INVALID)

        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description
        if data.start_date is not None or data.due_date is not None:
            if data.start_date is not None:
                task.start_date = data.start_date
            if data.due_date is not None:
                task.due_date = data.due_date
            self.activity.dates_changed(
                user.id, data.start_date, data.due_date, task_id=task.id
            )
        if data.status is not None and data.status != task.status:
            crosses_done_boundary = TaskStatus.done in (data.status, task.status)
            if crosses_done_boundary and user.id not in (
                task.creator_user_id,
                task.assignee_user_id,
            ):
                raise AppException(ErrorCode.COMPLETE_NOT_ALLOWED)
            held = None
            held_username = None
            if data.status == TaskStatus.done and task.assignee_user_id:
                held = seconds_between(task.assignee_changed_at, now)
                held_username = task.assignee.username if task.assignee else None
            self.activity.status_changed(
                user.id,
                task.status,
                data.status,
                seconds_between(task.status_changed_at, now),
                assignee_held_seconds=held,
                assignee_username=held_username,
                task_id=task.id,
            )
            task.status = data.status
            task.status_changed_at = now
        if data.is_urgent is not None and data.is_urgent != task.is_urgent:
            task.is_urgent = data.is_urgent
            self.activity.urgent_changed(user.id, data.is_urgent, task_id=task.id)
        if data.category_slug is not None:
            new_cat = await self.cats.get_by_slug(data.category_slug)
            if not new_cat:
                raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
            self._assert_category_matches_task_scope(new_cat, task)
            if new_cat.id != task.category_id:
                old_cat = task.category
                self.activity.category_moved(
                    user.id,
                    from_slug=old_cat.slug,
                    from_name=old_cat.name,
                    to_slug=new_cat.slug,
                    to_name=new_cat.name,
                    duration_seconds=seconds_between(task.category_changed_at, now),
                    task_id=task.id,
                )
                task.category_id = new_cat.id
                task.category_changed_at = now
                if data.position is None:
                    task.position = await self.repo.next_position(new_cat.id)
        if data.position is not None:
            task.position = data.position

        previous_assignee = task.assignee_user_id
        if data.assignee_username is not None:
            new_assignee_id = await self._resolve_assignee(
                data.assignee_username, group_id=task.group_id
            )
            if new_assignee_id != previous_assignee:
                self.activity.assignee_changed(
                    user.id,
                    task.assignee.username if task.assignee else None,
                    data.assignee_username or None,
                    prev_held_seconds=(
                        seconds_between(task.assignee_changed_at, now)
                        if previous_assignee
                        else None
                    ),
                    task_id=task.id,
                )
                task.assignee_user_id = new_assignee_id
                task.assignee_changed_at = now

        if data.tag_names is not None:
            task.tags = await self._resolve_or_create_tags(
                data.tag_names,
                owner_user_id=task.owner_user_id,
                group_id=task.group_id,
            )

        await self.db.flush()
        await self.db.refresh(task, ["category", "creator", "assignee", "tags", "subtasks"])

        if (
            task.assignee_user_id
            and task.assignee_user_id != previous_assignee
            and task.assignee_user_id != user.id
        ):
            await self._notify_assignee(task, task.assignee_user_id, user.username)

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

    @staticmethod
    def _assert_category_matches_task_scope(new_cat: Category, task: Task) -> None:
        if task.group_id is not None:
            if new_cat.group_id != task.group_id:
                raise AppException(ErrorCode.FORBIDDEN, "Categoria fora do escopo do grupo.")
        else:
            if new_cat.owner_user_id != task.owner_user_id:
                raise AppException(ErrorCode.FORBIDDEN, "Categoria fora do escopo do usuário.")

    async def _notify_assignee(
        self, task: Task, assignee_user_id: uuid.UUID, assigner_username: str
    ) -> None:
        payload: dict = {"task_slug": task.slug, "assigned_by": assigner_username}
        if task.group_id:
            group = await self.groups.get_by_id(task.group_id)
            if group:
                payload["group_slug"] = group.slug
                payload["group_name"] = group.name

        notif = Notification(
            user_id=assignee_user_id,
            type=NotificationType.task_assigned,
            title=f"{assigner_username} atribuiu uma tarefa a você: {task.title}",
            payload=payload,
        )
        await self.notifs.create(notif)
        await notification_manager.push(
            assignee_user_id,
            {"type": NotificationType.task_assigned.value, **payload},
        )

    async def _resolve_or_create_tags(
        self, tag_names: list[str], owner_user_id: uuid.UUID | None, group_id: int | None
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
        subtasks = task.subtasks
        done_count = sum(1 for s in subtasks if s.status == TaskStatus.done)
        is_overdue = (
            task.status != TaskStatus.done
            and task.due_date < datetime.now(timezone.utc)
        )
        return TaskOut(
            slug=task.slug,
            title=task.title,
            description=task.description,
            status=task.status,
            is_urgent=task.is_urgent,
            is_overdue=is_overdue,
            position=task.position,
            start_date=task.start_date,
            due_date=task.due_date,
            created_at=task.created_at,
            creator_username=task.creator.username,
            category_slug=task.category.slug,
            category_name=task.category.name,
            category_color=task.category.color,
            assignee_username=task.assignee.username if task.assignee else None,
            assignee_avatar_url=task.assignee.avatar_url if task.assignee else None,
            tags=[TagOut(name=t.name, color=t.color) for t in task.tags],
            subtask_done_count=done_count,
            subtask_total_count=len(subtasks),
        )
