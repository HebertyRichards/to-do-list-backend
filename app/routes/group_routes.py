from fastapi import APIRouter, Depends, status

from app.models import User
from app.schemas.group_schemas import (
    GroupCreate,
    GroupCreated,
    GroupMemberOut,
    GroupOut,
    GroupUpdate,
    JoinGroupInput,
    JoinRequestOut,
)
from app.services.group_service import GroupService
from app.utils.dependencies import get_current_user

group_routes = APIRouter(prefix="/groups", tags=["groups"])


@group_routes.get("", response_model=list[GroupOut])
async def list_groups(user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.list_groups(user)


@group_routes.get("/{group_slug}", response_model=GroupOut)
async def get_group(group_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.get_group(user, group_slug)


@group_routes.patch("/{group_slug}", response_model=GroupOut)
async def update_group(group_slug: str, data: GroupUpdate, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.update_group(user, group_slug, data)


@group_routes.post("", response_model=GroupCreated, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreate, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.create_group(user, data)


@group_routes.post("/join", status_code=status.HTTP_200_OK)
async def request_join(data: JoinGroupInput, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.request_join(user, data)


@group_routes.get("/{group_slug}/members", response_model=list[GroupMemberOut])
async def list_members(group_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.list_members(user, group_slug)


@group_routes.get("/{group_slug}/join-requests", response_model=list[JoinRequestOut])
async def list_pending(group_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.list_pending_requests(user, group_slug)


@group_routes.post("/{group_slug}/join-requests/{request_slug}/accept", status_code=status.HTTP_200_OK)
async def accept_request(group_slug: str, request_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.resolve_join_request(user, group_slug, request_slug, accept=True)


@group_routes.post("/{group_slug}/join-requests/{request_slug}/reject", status_code=status.HTTP_200_OK)
async def reject_request(group_slug: str, request_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.resolve_join_request(user, group_slug, request_slug, accept=False)


@group_routes.delete("/{group_slug}/members/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_slug: str, username: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.remove_member(user, group_slug, username)


@group_routes.delete("/{group_slug}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(group_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.leave_group(user, group_slug)


@group_routes.delete("/{group_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_slug: str, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.delete_group(user, group_slug)
