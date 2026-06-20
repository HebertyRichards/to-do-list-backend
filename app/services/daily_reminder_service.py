import asyncio
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
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


async def _users_with_activity_today(
    db: AsyncSession, candidates: dict[uuid.UUID, tuple[User, date]]
) -> set[uuid.UUID]:
    dates = {today for _, today in candidates.values()}
    stmt = (
        select(Habit.owner_user_id, HabitEntry.entry_date)
        .join(HabitEntry, HabitEntry.habit_id == Habit.id)
        .where(
            Habit.owner_user_id.in_(candidates.keys()),
            HabitEntry.entry_date.in_(dates),
            HabitEntry.status != HabitStatus.pending,
        )
        .distinct()
    )
    active: set[uuid.UUID] = set()
    for owner_id, entry_date in (await db.execute(stmt)).all():
        if candidates[owner_id][1] == entry_date:
            active.add(owner_id)
    return active


async def _users_already_reminded_today(
    db: AsyncSession, candidates: dict[uuid.UUID, tuple[User, date]]
) -> set[uuid.UUID]:
    earliest = datetime.now(timezone.utc) - timedelta(hours=48)
    stmt = (
        select(Notification.user_id, func.max(Notification.created_at))
        .where(
            Notification.user_id.in_(candidates.keys()),
            Notification.type == NotificationType.daily_reminder,
            Notification.created_at >= earliest,
        )
        .group_by(Notification.user_id)
    )
    reminded: set[uuid.UUID] = set()
    for user_id, last_created in (await db.execute(stmt)).all():
        user, today = candidates[user_id]
        zone = _safe_zone(user.timezone)
        local_midnight_utc = datetime.combine(today, time.min, tzinfo=zone).astimezone(
            timezone.utc
        )
        if last_created >= local_midnight_utc:
            reminded.add(user_id)
    return reminded


async def run_daily_reminder_check() -> int:
    settings = get_settings()

    async with SessionLocal() as db:
        rows = await db.execute(
            select(User, Habit).join(Habit, Habit.owner_user_id == User.id)
        )
        habits_by_user: dict[uuid.UUID, tuple[User, list[Habit]]] = {}
        for user, habit in rows.all():
            habits_by_user.setdefault(user.id, (user, []))[1].append(habit)

        candidates: dict[uuid.UUID, tuple[User, date]] = {}
        for user, habits in habits_by_user.values():
            now_local = datetime.now(_safe_zone(user.timezone))
            if now_local.hour < settings.daily_reminder_hour:
                continue
            today = now_local.date()
            if not any(is_scheduled(h.days_mask, today) for h in habits):
                continue
            candidates[user.id] = (user, today)

        if not candidates:
            return 0

        active = await _users_with_activity_today(db, candidates)
        reminded = await _users_already_reminded_today(db, candidates)

        to_notify: list[tuple[uuid.UUID, date]] = []
        for user_id, (_user, today) in candidates.items():
            if user_id in active or user_id in reminded:
                continue
            db.add(
                Notification(
                    user_id=user_id,
                    type=NotificationType.daily_reminder,
                    title=REMINDER_TITLE,
                    payload={"date": today.isoformat()},
                )
            )
            to_notify.append((user_id, today))

        if not to_notify:
            return 0

        await db.commit()

    for user_id, today in to_notify:
        await notification_manager.push(
            user_id,
            {"type": NotificationType.daily_reminder.value, "date": today.isoformat()},
        )

    logger.info("Lembretes do diario enviados: %d", len(to_notify))
    return len(to_notify)


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
