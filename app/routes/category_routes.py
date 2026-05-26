from fastapi import APIRouter, Depends, status

from app.models import User
from app.schemas.category_schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.services.category_service import CategoryService
from app.utils.dependencies import get_current_user

category_routes = APIRouter(prefix="/categories", tags=["categories"])


@category_routes.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create(data: CategoryCreate, user: User = Depends(get_current_user), service: CategoryService = Depends()):
    return await service.create(user, data)


@category_routes.get("", response_model=list[CategoryOut])
async def list_user(user: User = Depends(get_current_user), service: CategoryService = Depends()):
    return await service.list_user(user)


@category_routes.get("/group/{group_slug}", response_model=list[CategoryOut])
async def list_group(group_slug: str, user: User = Depends(get_current_user), service: CategoryService = Depends()):
    return await service.list_group(user, group_slug)


@category_routes.patch("/{category_slug}", response_model=CategoryOut)
async def update(category_slug: str, data: CategoryUpdate, user: User = Depends(get_current_user), service: CategoryService = Depends()):
    return await service.update(user, category_slug, data)


@category_routes.delete("/{category_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(category_slug: str, user: User = Depends(get_current_user), service: CategoryService = Depends()):
    await service.delete(user, category_slug)
