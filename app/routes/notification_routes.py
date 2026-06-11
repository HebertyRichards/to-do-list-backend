from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models import User
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification_schemas import NotificationOut, NotificationPage, UnreadCountOut
from app.utils import notification_cache
from app.utils.dependencies import get_current_user

notification_routes = APIRouter(prefix="/notifications", tags=["notifications"])


@notification_routes.get("", response_model=NotificationPage)
async def list_notifications(
    cursor: int | None = Query(default=None, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_first_page = cursor is None
    if is_first_page:
        cached = await notification_cache.get_first_page(user.id)
        if cached is not None:
            return NotificationPage.model_validate(cached)

    repo = NotificationRepository(db)
    items = await repo.list_for_user(user.id, cursor=cursor, limit=limit + 1)
    has_more = len(items) > limit
    items = items[:limit]
    page = NotificationPage(
        items=[NotificationOut.model_validate(n) for n in items],
        next_cursor=items[-1].id if has_more and items else None,
    )

    if is_first_page:
        await notification_cache.set_first_page(user.id, page.model_dump(mode="json"))
    return page


@notification_routes.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    cached = await notification_cache.get_unread_count(user.id)
    if cached is not None:
        return UnreadCountOut(count=cached)

    repo = NotificationRepository(db)
    count = await repo.count_unread(user.id)
    await notification_cache.set_unread_count(user.id, count)
    return UnreadCountOut(count=count)


@notification_routes.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = NotificationRepository(db)
    await repo.mark_read(user.id, notification_id)
    await db.commit()
    await notification_cache.invalidate(user.id)


@notification_routes.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    repo = NotificationRepository(db)
    await repo.mark_all_read(user.id)
    await db.commit()
    await notification_cache.invalidate(user.id)
