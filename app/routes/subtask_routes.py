from fastapi import APIRouter, Depends, status

from app.models import User
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate
from app.services.subtask_service import SubtaskService
from app.utils.dependencies import get_current_user

subtask_routes = APIRouter(prefix="/subtasks", tags=["subtasks"])


@subtask_routes.post("", response_model=SubtaskOut, status_code=status.HTTP_201_CREATED)
async def create(data: SubtaskCreate, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.create(user, data)


@subtask_routes.get("", response_model=list[SubtaskOut])
async def list_user(user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.list_user(user)


@subtask_routes.get("/group/{group_slug}", response_model=list[SubtaskOut])
async def list_group(group_slug: str, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.list_group(user, group_slug)


@subtask_routes.get("/task/{task_slug}", response_model=list[SubtaskOut])
async def list_for_task(task_slug: str, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.list_for_task(user, task_slug)


@subtask_routes.patch("/{subtask_slug}", response_model=SubtaskOut)
async def update(subtask_slug: str, data: SubtaskUpdate, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.update(user, subtask_slug, data)


@subtask_routes.delete("/{subtask_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(subtask_slug: str, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    await service.delete(user, subtask_slug)
