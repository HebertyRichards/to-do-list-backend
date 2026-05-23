from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user_schemas import UpdateProfileInput, UserProfile


class UserService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.users = UserRepository(db)

    async def get_profile(self, user: User) -> UserProfile:
        return UserProfile.model_validate(user)

    async def update_profile(self, user: User, data: UpdateProfileInput) -> UserProfile:
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.avatar_url is not None:
            user.avatar_url = data.avatar_url
        if data.onboarded is not None:
            user.onboarded = data.onboarded

        await self.users.update(user)
        await self.db.commit()
        return UserProfile.model_validate(user)
