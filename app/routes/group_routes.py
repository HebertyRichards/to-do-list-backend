from fastapi import APIRouter, Depends, status
from app.models import User
from app.schemas.group_schemas import (
    GroupCreate,
    GroupCreated,
    GroupMemberOut,
    JoinGroupInput,
    JoinRequestOut,
)
from app.services.group_service import GroupService
from app.utils.dependencies import get_current_user

group_routes = APIRouter(prefix="/groups", tags=["groups"])


@group_routes.post("", response_model=GroupCreated, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreate, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.create_group(user, data)


@group_routes.post("/join", status_code=status.HTTP_200_OK)
async def request_join(data: JoinGroupInput, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.request_join(user, data)


@group_routes.get("/{group_id}/members", response_model=list[GroupMemberOut])
async def list_members(group_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.list_members(user, group_id)


@group_routes.get("/{group_id}/join-requests", response_model=list[JoinRequestOut])
async def list_pending(group_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.list_pending_requests(user, group_id)


@group_routes.post("/{group_id}/join-requests/{request_id}/accept", status_code=status.HTTP_200_OK)
async def accept_request(group_id: int, request_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.resolve_join_request(user, group_id, request_id, accept=True)


@group_routes.post("/{group_id}/join-requests/{request_id}/reject", status_code=status.HTTP_200_OK)
async def reject_request(group_id: int, request_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    return await service.resolve_join_request(user, group_id, request_id, accept=False)


@group_routes.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_id: int, user_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.remove_member(user, group_id, user_id)


@group_routes.delete("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(group_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.leave_group(user, group_id)


@group_routes.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, user: User = Depends(get_current_user), service: GroupService = Depends()):
    await service.delete_group(user, group_id)
