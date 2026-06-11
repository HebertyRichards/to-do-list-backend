from fastapi import APIRouter, Depends, status

from app.models import User
from app.schemas.habit_schemas import (
    HabitCreate,
    HabitOut,
    HabitStatsOut,
    HabitStatusUpdate,
    HabitUpdate,
)
from app.services.habit_service import HabitService
from app.utils.dependencies import get_current_user, get_request_timezone

habit_routes = APIRouter(prefix="/habits", tags=["habits"])


@habit_routes.post("", response_model=HabitOut, status_code=status.HTTP_201_CREATED)
async def create(data: HabitCreate, user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.create(user, data, tz)


@habit_routes.get("", response_model=list[HabitOut])
async def list_user(user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.list_user(user, tz)


@habit_routes.get("/today", response_model=list[HabitOut])
async def list_today(user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.list_today(user, tz)


@habit_routes.get("/stats", response_model=HabitStatsOut)
async def stats(user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.stats(user, tz=tz)


@habit_routes.patch("/{slug}", response_model=HabitOut)
async def update(slug: str, data: HabitUpdate, user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.update(user, slug, data, tz)


@habit_routes.patch("/{slug}/status", response_model=HabitOut)
async def set_status(slug: str, data: HabitStatusUpdate, user: User = Depends(get_current_user), service: HabitService = Depends(), tz: str | None = Depends(get_request_timezone)):
    return await service.set_status(user, slug, data, tz)


@habit_routes.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(slug: str, user: User = Depends(get_current_user), service: HabitService = Depends()):
    await service.delete(user, slug)
