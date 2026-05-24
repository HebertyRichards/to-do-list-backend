import json
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.config.redis_client import get_redis
from app.errors import AppException, ErrorCode
from app.models import Group, GroupMember, JoinRequest, Notification, Subtask, Task, User
from app.models.group_member import GroupRole
from app.models.join_request import JoinRequestStatus
from app.models.notification import NotificationType
from app.repositories.group_repository import GroupRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.ws.manager import notification_manager
from app.schemas.group_schemas import (
    GroupCreate,
    GroupCreated,
    GroupMemberOut,
    GroupOut,
    JoinGroupInput,
    JoinRequestOut,
)
from app.utils.security import generate_group_key, generate_slug, hash_group_key, verify_group_key

JOIN_REQUEST_TTL_DAYS = 3


class GroupService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = GroupRepository(db)
        self.notifs = NotificationRepository(db)

    async def list_groups(self, user: User) -> list[GroupOut]:
        groups = await self.repo.list_for_user(user.id)
        return [
            GroupOut(
                slug=g.slug,
                name=g.name,
                description=g.description,
                member_count=len(g.members),
            )
            for g in groups
        ]

    async def create_group(self, user: User, data: GroupCreate) -> GroupCreated:
        raw_key = generate_group_key()
        group = Group(
            slug=generate_slug(),
            name=data.name,
            description=data.description,
            key_hash=hash_group_key(raw_key),
            admin_user_id=user.id,
        )
        group = await self.repo.create_group(group)

        admin_member = GroupMember(group_id=group.id, user_id=user.id, role=GroupRole.admin)
        await self.repo.create_member(admin_member)
        await self.db.commit()

        return GroupCreated(
            slug=group.slug,
            name=group.name,
            description=group.description,
            key=raw_key,
        )

    async def request_join(self, user: User, data: JoinGroupInput) -> dict:
        key_hash = hash_group_key(data.key)
        group = await self.repo.get_by_key_hash(key_hash)
        if not group:
            raise AppException(ErrorCode.INVALID_GROUP_KEY)

        if await self.repo.get_member(group.id, user.id):
            raise AppException(ErrorCode.ALREADY_GROUP_MEMBER)

        if await self.repo.get_pending_request(group.id, user.id):
            raise AppException(ErrorCode.JOIN_REQUEST_ALREADY_PENDING)

        expires_at = datetime.now(timezone.utc) + timedelta(days=JOIN_REQUEST_TTL_DAYS)
        req = JoinRequest(
            slug=generate_slug(),
            group_id=group.id,
            user_id=user.id,
            status=JoinRequestStatus.pending,
            expires_at=expires_at,
        )
        req = await self.repo.create_join_request(req)

        redis = await get_redis()
        await redis.setex(
            f"join_request:{req.slug}",
            JOIN_REQUEST_TTL_DAYS * 86400,
            json.dumps({"request_slug": req.slug}),
        )

        notif = Notification(
            user_id=group.admin_user_id,
            type=NotificationType.join_request_created,
            title=f"{user.username} quer entrar em {group.name}",
            payload={"request_slug": req.slug, "group_slug": group.slug, "username": user.username},
        )
        await self.notifs.create(notif)
        await self.db.commit()

        await notification_manager.push(group.admin_user_id, {
            "type": "join_request_created",
            "request_slug": req.slug,
            "group_slug": group.slug,
            "username": user.username,
        })

        return {"message": "Solicitacao enviada. Aguarde aprovacao do administrador."}

    async def resolve_join_request(
        self, admin: User, group_slug: str, request_slug: str, accept: bool
    ) -> dict:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.admin_user_id != admin.id:
            raise AppException(ErrorCode.NOT_GROUP_ADMIN)

        req = await self.repo.get_request_by_slug(request_slug)
        if not req or req.group_id != group.id:
            raise AppException(ErrorCode.JOIN_REQUEST_NOT_FOUND)

        now = datetime.now(timezone.utc)
        if req.expires_at.replace(tzinfo=timezone.utc) < now:
            req.status = JoinRequestStatus.expired
            req.resolved_at = now
            await self.db.commit()
            raise AppException(ErrorCode.JOIN_REQUEST_EXPIRED)

        req.status = JoinRequestStatus.accepted if accept else JoinRequestStatus.rejected
        req.resolved_at = now

        notif_type = NotificationType.join_request_accepted if accept else NotificationType.join_request_rejected
        notif_title = f"Sua solicitacao para {group.name} foi {'aceita' if accept else 'recusada'}."

        if accept:
            member = GroupMember(group_id=group.id, user_id=req.user_id, role=GroupRole.member)
            await self.repo.create_member(member)

        notif = Notification(
            user_id=req.user_id,
            type=notif_type,
            title=notif_title,
            payload={"group_slug": group.slug, "group_name": group.name},
        )
        await self.notifs.create(notif)
        await self.db.commit()

        await notification_manager.push(req.user_id, {
            "type": notif_type.value,
            "group_slug": group.slug,
            "group_name": group.name,
        })

        return {"accepted": accept}

    async def list_members(self, user: User, group_slug: str) -> list[GroupMemberOut]:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if not await self.repo.get_member(group.id, user.id):
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)
        members = await self.repo.list_members(group.id)
        return [
            GroupMemberOut(username=m.user.username, role=m.role, joined_at=m.joined_at)
            for m in members
        ]

    async def list_pending_requests(self, admin: User, group_slug: str) -> list[JoinRequestOut]:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.admin_user_id != admin.id:
            raise AppException(ErrorCode.NOT_GROUP_ADMIN)

        reqs = await self.repo.list_pending_requests(group.id)
        return [
            JoinRequestOut(
                slug=r.slug,
                username=r.user.username,
                status=r.status,
                expires_at=r.expires_at,
                created_at=r.created_at,
            )
            for r in reqs
        ]

    async def remove_member(self, admin: User, group_slug: str, username: str) -> None:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.admin_user_id != admin.id:
            raise AppException(ErrorCode.NOT_GROUP_ADMIN)

        user_repo = UserRepository(self.db)
        target = await user_repo.get_by_username(username)
        if not target:
            raise AppException(ErrorCode.USER_NOT_FOUND)

        member = await self.repo.get_member(group.id, target.id)
        if not member:
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)

        await self._delete_user_tasks_in_group(target.id, group.id)
        await self.repo.remove_member(member)

        notif = Notification(
            user_id=target.id,
            type=NotificationType.member_removed,
            title=f"Voce foi removido do grupo {group.name}.",
            payload={"group_slug": group.slug, "group_name": group.name},
        )
        await self.notifs.create(notif)
        await self.db.commit()

        await notification_manager.push(target.id, {
            "type": "member_removed",
            "group_slug": group.slug,
            "group_name": group.name,
        })

    async def leave_group(self, user: User, group_slug: str) -> None:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.admin_user_id == user.id:
            raise AppException(ErrorCode.FORBIDDEN, "Admin deve excluir o grupo, nao sair.")

        member = await self.repo.get_member(group.id, user.id)
        if not member:
            raise AppException(ErrorCode.NOT_GROUP_MEMBER)

        await self._delete_user_tasks_in_group(user.id, group.id)
        await self.repo.remove_member(member)
        await self.db.commit()

    async def delete_group(self, admin: User, group_slug: str) -> None:
        group = await self.repo.get_by_slug(group_slug)
        if not group:
            raise AppException(ErrorCode.GROUP_NOT_FOUND)
        if group.admin_user_id != admin.id:
            raise AppException(ErrorCode.NOT_GROUP_ADMIN)

        members = await self.repo.list_members(group.id)
        member_ids = [m.user_id for m in members if m.user_id != admin.id]

        await self.repo.delete_group(group)
        await self.db.commit()

        for uid in member_ids:
            await notification_manager.push(uid, {
                "type": "group_deleted",
                "group_slug": group.slug,
                "group_name": group.name,
            })

    async def _delete_user_tasks_in_group(self, user_id: int, group_id: int) -> None:
        user_task_ids_subq = (
            select(Task.id)
            .where(Task.group_id == group_id, Task.creator_user_id == user_id)
            .scalar_subquery()
        )
        await self.db.execute(delete(Subtask).where(Subtask.task_id.in_(user_task_ids_subq)))
        await self.db.execute(
            delete(Task).where(Task.group_id == group_id, Task.creator_user_id == user_id)
        )
