from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Comment, Subtask, Task, User
from app.models.group_member import GroupRole
from app.repositories.comment_repository import CommentRepository
from app.repositories.group_repository import GroupRepository
from app.repositories.subtask_repository import SubtaskRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.comment_schemas import CommentCreate, CommentOut, CommentUpdate
from app.utils.security import generate_slug


class CommentService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = CommentRepository(db)
        self.tasks = TaskRepository(db)
        self.subtasks = SubtaskRepository(db)
        self.groups = GroupRepository(db)

    async def list_for_task(self, user: User, task_slug: str) -> list[CommentOut]:
        task = await self._get_accessible_task(user, task_slug)
        is_admin = await self._is_group_admin(user, task.group_id)
        comments = await self.repo.list_for_task(task.id)
        return [self._comment_out(c, user, is_admin) for c in comments]

    async def list_for_subtask(self, user: User, subtask_slug: str) -> list[CommentOut]:
        subtask = await self._get_accessible_subtask(user, subtask_slug)
        is_admin = await self._is_group_admin(user, subtask.task.group_id)
        comments = await self.repo.list_for_subtask(subtask.id)
        return [self._comment_out(c, user, is_admin) for c in comments]

    async def create_for_task(
        self, user: User, task_slug: str, data: CommentCreate
    ) -> CommentOut:
        task = await self._get_accessible_task(user, task_slug)
        comment = Comment(
            slug=generate_slug(), body=data.body, author_user_id=user.id, task_id=task.id
        )
        comment = await self.repo.create(comment)
        await self.db.commit()
        is_admin = await self._is_group_admin(user, task.group_id)
        return self._comment_out(comment, user, is_admin)

    async def create_for_subtask(
        self, user: User, subtask_slug: str, data: CommentCreate
    ) -> CommentOut:
        subtask = await self._get_accessible_subtask(user, subtask_slug)
        comment = Comment(
            slug=generate_slug(),
            body=data.body,
            author_user_id=user.id,
            subtask_id=subtask.id,
        )
        comment = await self.repo.create(comment)
        await self.db.commit()
        is_admin = await self._is_group_admin(user, subtask.task.group_id)
        return self._comment_out(comment, user, is_admin)

    async def update(
        self, user: User, comment_slug: str, data: CommentUpdate
    ) -> CommentOut:
        comment = await self._get(comment_slug)
        if comment.author_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        comment.body = data.body
        await self.db.flush()
        await self.db.refresh(comment, ["author"])
        await self.db.commit()
        is_admin = await self._is_group_admin(user, await self._comment_group_id(comment))
        return self._comment_out(comment, user, is_admin)

    async def delete(self, user: User, comment_slug: str) -> None:
        comment = await self._get(comment_slug)
        if comment.author_user_id != user.id:
            group_id = await self._comment_group_id(comment)
            if not await self._is_group_admin(user, group_id):
                raise AppException(ErrorCode.FORBIDDEN)
        await self.repo.delete(comment)
        await self.db.commit()

    async def _get(self, comment_slug: str) -> Comment:
        comment = await self.repo.get_by_slug(comment_slug)
        if not comment:
            raise AppException(ErrorCode.COMMENT_NOT_FOUND)
        return comment

    async def _get_accessible_task(self, user: User, task_slug: str) -> Task:
        task = await self.tasks.get_by_slug(task_slug)
        if not task:
            raise AppException(ErrorCode.TASK_NOT_FOUND)
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return task

    async def _get_accessible_subtask(self, user: User, subtask_slug: str) -> Subtask:
        subtask = await self.subtasks.get_by_slug(subtask_slug)
        if not subtask:
            raise AppException(ErrorCode.SUBTASK_NOT_FOUND)
        task = subtask.task
        if task.group_id:
            if not await self.groups.get_member(task.group_id, user.id):
                raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        elif task.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return subtask

    async def _is_group_admin(self, user: User, group_id: int | None) -> bool:
        if not group_id:
            return False
        member = await self.groups.get_member(group_id, user.id)
        return bool(member and member.role == GroupRole.admin)

    async def _comment_group_id(self, comment: Comment) -> int | None:
        if comment.task_id is not None:
            task = await self.db.get(Task, comment.task_id)
            return task.group_id if task else None
        subtask = await self.db.get(Subtask, comment.subtask_id)
        if not subtask:
            return None
        task = await self.db.get(Task, subtask.task_id)
        return task.group_id if task else None

    @staticmethod
    def _comment_out(comment: Comment, user: User, is_group_admin: bool) -> CommentOut:
        is_author = comment.author_user_id == user.id
        return CommentOut(
            slug=comment.slug,
            body=comment.body,
            author_username=comment.author.username,
            author_avatar_url=comment.author.avatar_url,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            can_edit=is_author,
            can_delete=is_author or is_group_admin,
        )
