import asyncio
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import SessionLocal
from app.config.redis_client import get_redis, is_redis_available
from app.config.settings import get_settings
from app.models import Habit, HabitEntry, JoinRequest, Notification, User
from app.models.habit import HabitStatus, is_scheduled
from app.models.notification import NotificationType
from app.ws.manager import notification_manager

logger = logging.getLogger(__name__)

REMINDER_TITLE = "Você ainda não fez nenhuma tarefa do diário hoje."

_LOCK_KEY = "locks:daily_jobs"


async def _acquire_cycle_lock(ttl_seconds: int) -> bool:
    if not is_redis_available():
        return True
    try:
        redis = await get_redis()
        return bool(await redis.set(_LOCK_KEY, "1", nx=True, ex=ttl_seconds))
    except Exception as exc:
        logger.warning("Lock do ciclo de jobs falhou, prosseguindo: %s", exc)
        return True


def _safe_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


async def _already_reminded_today(
    db: AsyncSession, user_id: uuid.UUID, local_midnight_utc: datetime
) -> bool:
    stmt = select(
        exists().where(
            Notification.user_id == user_id,
            Notification.type == NotificationType.daily_reminder,
            Notification.created_at >= local_midnight_utc,
        )
    )
    return bool((await db.execute(stmt)).scalar())


async def _has_activity_today(db: AsyncSession, user_id: uuid.UUID, today) -> bool:
    stmt = select(
        exists()
        .where(
            HabitEntry.habit_id == Habit.id,
            Habit.owner_user_id == user_id,
            HabitEntry.entry_date == today,
            HabitEntry.status != HabitStatus.pending,
        )
    )
    return bool((await db.execute(stmt)).scalar())


async def run_daily_reminder_check() -> int:
    settings = get_settings()
    sent = 0

    async with SessionLocal() as db:
        rows = await db.execute(
            select(User, Habit).join(Habit, Habit.owner_user_id == User.id)
        )
        habits_by_user: dict[uuid.UUID, tuple[User, list[Habit]]] = {}
        for user, habit in rows.all():
            habits_by_user.setdefault(user.id, (user, []))[1].append(habit)

        for user, habits in habits_by_user.values():
            zone = _safe_zone(user.timezone)
            now_local = datetime.now(zone)
            if now_local.hour < settings.daily_reminder_hour:
                continue

            today = now_local.date()
            if not any(is_scheduled(h.days_mask, today) for h in habits):
                continue

            if await _has_activity_today(db, user.id, today):
                continue

            local_midnight_utc = datetime.combine(today, time.min, tzinfo=zone).astimezone(
                timezone.utc
            )
            if await _already_reminded_today(db, user.id, local_midnight_utc):
                continue

            notif = Notification(
                user_id=user.id,
                type=NotificationType.daily_reminder,
                title=REMINDER_TITLE,
                payload={"date": today.isoformat()},
            )
            db.add(notif)
            await db.commit()

            await notification_manager.push(user.id, {
                "type": NotificationType.daily_reminder.value,
                "date": today.isoformat(),
            })
            sent += 1

    if sent:
        logger.info("Lembretes do diario enviados: %d", sent)
    return sent


async def run_retention_cleanup() -> None:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.cleanup_retention_days)

    async with SessionLocal() as db:
        notif_result = await db.execute(
            delete(Notification).where(Notification.read_at < cutoff)
        )
        req_result = await db.execute(
            delete(JoinRequest).where(JoinRequest.expires_at < cutoff)
        )
        await db.commit()

    removed = notif_result.rowcount + req_result.rowcount
    if removed:
        logger.info(
            "Limpeza: %d notificacoes e %d join requests removidos",
            notif_result.rowcount,
            req_result.rowcount,
        )


async def daily_reminder_loop() -> None:
    settings = get_settings()
    interval = max(settings.daily_reminder_check_minutes, 1) * 60
    lock_ttl = max(interval - 60, 60)
    while True:
        try:
            if await _acquire_cycle_lock(lock_ttl):
                await run_daily_reminder_check()
                await run_retention_cleanup()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha no ciclo de jobs em background")
        await asyncio.sleep(interval)
