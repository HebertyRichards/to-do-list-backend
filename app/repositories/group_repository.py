from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Group, GroupMember, JoinRequest
from app.models.join_request import JoinRequestStatus


class GroupRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, group_id: int) -> Group | None:
        return await self.db.get(Group, group_id)

    async def get_by_slug(self, slug: str) -> Group | None:
        stmt = select(Group).where(Group.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_key_hash(self, key_hash: str) -> Group | None:
        stmt = select(Group).where(Group.key_hash == key_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_member(self, group_id: int, user_id: int) -> GroupMember | None:
        stmt = select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_members(self, group_id: int) -> list[GroupMember]:
        stmt = (
            select(GroupMember)
            .options(selectinload(GroupMember.user))
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.joined_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_for_user(self, user_id: int) -> list[Group]:
        stmt = (
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
            .options(selectinload(Group.members))
            .order_by(Group.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_pending_request(self, group_id: int, user_id: int) -> JoinRequest | None:
        stmt = select(JoinRequest).where(
            JoinRequest.group_id == group_id,
            JoinRequest.user_id == user_id,
            JoinRequest.status == JoinRequestStatus.pending,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_request_by_slug(self, slug: str) -> JoinRequest | None:
        stmt = (
            select(JoinRequest)
            .options(selectinload(JoinRequest.user))
            .where(JoinRequest.slug == slug)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_pending_requests(self, group_id: int) -> list[JoinRequest]:
        stmt = (
            select(JoinRequest)
            .options(selectinload(JoinRequest.user))
            .where(
                JoinRequest.group_id == group_id,
                JoinRequest.status == JoinRequestStatus.pending,
                JoinRequest.expires_at > datetime.now(timezone.utc),
            )
            .order_by(JoinRequest.created_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_group(self, group: Group) -> Group:
        self.db.add(group)
        await self.db.flush()
        await self.db.refresh(group)
        return group

    async def create_member(self, member: GroupMember) -> GroupMember:
        self.db.add(member)
        await self.db.flush()
        return member

    async def create_join_request(self, req: JoinRequest) -> JoinRequest:
        self.db.add(req)
        await self.db.flush()
        await self.db.refresh(req)
        return req

    async def delete_group(self, group: Group) -> None:
        await self.db.delete(group)
        await self.db.flush()

    async def remove_member(self, member: GroupMember) -> None:
        await self.db.delete(member)
        await self.db.flush()
