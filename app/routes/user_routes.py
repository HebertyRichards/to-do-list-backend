from fastapi import APIRouter, Depends
from app.models import User
from app.schemas.user_schemas import UpdateProfileInput, UserProfile
from app.services.user_service import UserService
from app.utils.dependencies import get_current_user

user_routes = APIRouter(prefix="/users", tags=["users"])


@user_routes.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user), service: UserService = Depends()):
    return await service.get_profile(current_user)


@user_routes.patch("/me", response_model=UserProfile)
async def update_profile(
    data: UpdateProfileInput,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(),
):
    return await service.update_profile(current_user, data)
