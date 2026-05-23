from fastapi import APIRouter, Depends, status
from app.models import User
from app.schemas.task_schemas import TaskCreate, TaskOut, TaskUpdate
from app.services.task_service import TaskService
from app.utils.dependencies import get_current_user

task_routes = APIRouter(prefix="/tasks", tags=["tasks"])


@task_routes.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create(data: TaskCreate, user: User = Depends(get_current_user), service: TaskService = Depends()):
    return await service.create(user, data)


@task_routes.get("", response_model=list[TaskOut])
async def list_user(user: User = Depends(get_current_user), service: TaskService = Depends()):
    return await service.list_user(user)


@task_routes.get("/group/{group_id}", response_model=list[TaskOut])
async def list_group(group_id: int, user: User = Depends(get_current_user), service: TaskService = Depends()):
    return await service.list_group(user, group_id)


@task_routes.patch("/{task_id}", response_model=TaskOut)
async def update(task_id: int, data: TaskUpdate, user: User = Depends(get_current_user), service: TaskService = Depends()):
    return await service.update(user, task_id, data)


@task_routes.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(task_id: int, user: User = Depends(get_current_user), service: TaskService = Depends()):
    await service.delete(user, task_id)
