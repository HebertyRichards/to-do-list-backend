from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification_schemas import NotificationOut
from app.utils.dependencies import get_current_user

notification_routes = APIRouter(prefix="/notifications", tags=["notifications"])


@notification_routes.get("", response_model=list[NotificationOut])
async def list_notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = NotificationRepository(db)
    items = await repo.list_for_user(user.id)
    return [NotificationOut.model_validate(n) for n in items]


@notification_routes.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = NotificationRepository(db)
    await repo.mark_read(user.id, notification_id)
    await db.commit()


@notification_routes.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = NotificationRepository(db)
    await repo.mark_all_read(user.id)
    await db.commit()
