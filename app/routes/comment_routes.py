from fastapi import APIRouter, Depends, status

from app.models import User
from app.schemas.activity_schemas import TimelineItemOut
from app.schemas.comment_schemas import CommentCreate, CommentOut, CommentUpdate
from app.services.comment_service import CommentService
from app.utils.dependencies import get_current_user

comment_routes = APIRouter(prefix="/comments", tags=["comments"])


@comment_routes.get("/task/{task_slug}", response_model=list[CommentOut])
async def list_for_task(task_slug: str, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.list_for_task(user, task_slug)


@comment_routes.get("/subtask/{subtask_slug}", response_model=list[CommentOut])
async def list_for_subtask(subtask_slug: str, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.list_for_subtask(user, subtask_slug)


@comment_routes.get("/task/{task_slug}/timeline", response_model=list[TimelineItemOut])
async def timeline_for_task(task_slug: str, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.timeline_for_task(user, task_slug)


@comment_routes.get("/subtask/{subtask_slug}/timeline", response_model=list[TimelineItemOut])
async def timeline_for_subtask(subtask_slug: str, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.timeline_for_subtask(user, subtask_slug)


@comment_routes.post("/task/{task_slug}", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_for_task(task_slug: str, data: CommentCreate, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.create_for_task(user, task_slug, data)


@comment_routes.post("/subtask/{subtask_slug}", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_for_subtask(subtask_slug: str, data: CommentCreate, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.create_for_subtask(user, subtask_slug, data)


@comment_routes.patch("/{comment_slug}", response_model=CommentOut)
async def update(comment_slug: str, data: CommentUpdate, user: User = Depends(get_current_user), service: CommentService = Depends()):
    return await service.update(user, comment_slug, data)


@comment_routes.delete("/{comment_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(comment_slug: str, user: User = Depends(get_current_user), service: CommentService = Depends()):
    await service.delete(user, comment_slug)
