from fastapi import APIRouter, Depends, status
from app.models import User
from app.schemas.subtask_schemas import SubtaskCreate, SubtaskOut, SubtaskUpdate
from app.services.subtask_service import SubtaskService
from app.utils.dependencies import get_current_user

subtask_routes = APIRouter(prefix="/subtasks", tags=["subtasks"])


@subtask_routes.post("", response_model=SubtaskOut, status_code=status.HTTP_201_CREATED)
async def create(data: SubtaskCreate, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.create(user, data)


@subtask_routes.get("/task/{task_id}", response_model=list[SubtaskOut])
async def list_for_task(task_id: int, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.list_for_task(user, task_id)


@subtask_routes.patch("/{subtask_id}", response_model=SubtaskOut)
async def update(subtask_id: int, data: SubtaskUpdate, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    return await service.update(user, subtask_id, data)


@subtask_routes.delete("/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(subtask_id: int, user: User = Depends(get_current_user), service: SubtaskService = Depends()):
    await service.delete(user, subtask_id)
