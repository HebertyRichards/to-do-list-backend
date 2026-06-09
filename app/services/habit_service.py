from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import Habit, HabitEntry, User
from app.models.habit import (
    ALL_DAYS_MASK,
    HabitStatus,
    days_to_mask,
    is_scheduled,
    mask_to_days,
)
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit_schemas import (
    HabitCreate,
    HabitOut,
    HabitStatsOut,
    HabitStatusUpdate,
    HabitUpdate,
)
from app.utils.security import generate_slug


def _user_today(user: User) -> date:
    try:
        tz = ZoneInfo(user.timezone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


class HabitService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.repo = HabitRepository(db)

    async def create(self, user: User, data: HabitCreate) -> HabitOut:
        mask = self._resolve_mask(data.every_day, data.days_of_week)
        habit = Habit(
            slug=generate_slug(),
            title=data.title,
            description=data.description,
            every_day=data.every_day,
            days_mask=mask,
            owner_user_id=user.id,
        )
        habit = await self.repo.create(habit)
        await self.db.commit()
        return self._habit_out(habit, None, _user_today(user))

    async def list_user(self, user: User) -> list[HabitOut]:
        today = _user_today(user)
        habits = await self.repo.list_for_user(user.id)
        status_map = await self._today_status_map(user, today)
        return [self._habit_out(h, status_map.get(h.id), today) for h in habits]

    async def list_today(self, user: User) -> list[HabitOut]:
        today = _user_today(user)
        habits = await self.repo.list_for_user(user.id)
        status_map = await self._today_status_map(user, today)
        return [
            self._habit_out(h, status_map.get(h.id), today)
            for h in habits
            if is_scheduled(h.days_mask, today)
        ]

    async def update(self, user: User, slug: str, data: HabitUpdate) -> HabitOut:
        habit = await self._get_owned(user, slug)

        if data.title is not None:
            habit.title = data.title
        if data.description is not None:
            habit.description = data.description

        every_day = data.every_day if data.every_day is not None else habit.every_day
        days = data.days_of_week if data.days_of_week is not None else mask_to_days(habit.days_mask)
        habit.every_day = every_day
        habit.days_mask = self._resolve_mask(every_day, days)

        await self.db.flush()
        await self.db.commit()
        return await self._habit_out_with_today(habit, _user_today(user))

    async def delete(self, user: User, slug: str) -> None:
        habit = await self._get_owned(user, slug)
        await self.repo.delete(habit)
        await self.db.commit()

    async def set_status(
        self, user: User, slug: str, data: HabitStatusUpdate
    ) -> HabitOut:
        habit = await self._get_owned(user, slug)
        today = _user_today(user)
        target = data.date or today

        if target > today:
            raise AppException(ErrorCode.VALIDATION_ERROR, "Nao e possivel registrar um dia futuro.")
        if not is_scheduled(habit.days_mask, target):
            raise AppException(
                ErrorCode.VALIDATION_ERROR, "Habito nao programado para este dia."
            )

        entry = await self.repo.get_entry(habit.id, target)
        if entry:
            entry.status = data.status
        else:
            self.db.add(
                HabitEntry(habit_id=habit.id, entry_date=target, status=data.status)
            )
        await self.db.flush()
        await self.db.commit()
        return await self._habit_out_with_today(habit, today)

    async def stats(self, user: User, ref_date: date | None = None) -> HabitStatsOut:
        today = ref_date or _user_today(user)
        habits = await self.repo.list_for_user(user.id)

        def active(habit: Habit, day: date) -> bool:
            return habit.created_at.date() <= day and is_scheduled(habit.days_mask, day)

        # Diário
        status_map = await self._today_status_map(user, today)
        scheduled_today = [h for h in habits if active(h, today)]
        daily_scheduled = len(scheduled_today)
        daily_done = sum(
            1 for h in scheduled_today if status_map.get(h.id) == HabitStatus.done
        )

        # Mensal (do dia 1 até a data de referência)
        month_start = today.replace(day=1)
        entries = await self.repo.list_entries_for_user_between(
            user.id, month_start, today
        )
        done_set = {
            (e.habit_id, e.entry_date)
            for e in entries
            if e.status == HabitStatus.done
        }
        monthly_scheduled = 0
        monthly_done = 0
        day = month_start
        while day <= today:
            for h in habits:
                if active(h, day):
                    monthly_scheduled += 1
                    if (h.id, day) in done_set:
                        monthly_done += 1
            day += timedelta(days=1)

        return HabitStatsOut(
            date=today,
            daily_scheduled=daily_scheduled,
            daily_done=daily_done,
            daily_percent=self._percent(daily_done, daily_scheduled),
            month=today.strftime("%Y-%m"),
            monthly_scheduled=monthly_scheduled,
            monthly_done=monthly_done,
            monthly_percent=self._percent(monthly_done, monthly_scheduled),
        )

    async def _get_owned(self, user: User, slug: str) -> Habit:
        habit = await self.repo.get_by_slug(slug)
        if not habit:
            raise AppException(ErrorCode.HABIT_NOT_FOUND)
        if habit.owner_user_id != user.id:
            raise AppException(ErrorCode.FORBIDDEN)
        return habit

    async def _today_status_map(
        self, user: User, today: date
    ) -> dict[int, HabitStatus]:
        entries = await self.repo.list_entries_for_user_between(user.id, today, today)
        return {e.habit_id: e.status for e in entries}

    async def _habit_out_with_today(self, habit: Habit, today: date) -> HabitOut:
        entry = await self.repo.get_entry(habit.id, today)
        return self._habit_out(habit, entry.status if entry else None, today)

    @staticmethod
    def _resolve_mask(every_day: bool, days: list[int]) -> int:
        if every_day:
            return ALL_DAYS_MASK
        mask = days_to_mask(days)
        if mask < 1:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                "Selecione ao menos um dia ou marque every_day.",
            )
        return mask

    @staticmethod
    def _percent(done: int, total: int) -> float:
        return round(done / total * 100, 1) if total else 0.0

    @staticmethod
    def _habit_out(
        habit: Habit, today_status: HabitStatus | None, today: date
    ) -> HabitOut:
        return HabitOut(
            slug=habit.slug,
            title=habit.title,
            description=habit.description,
            every_day=habit.every_day,
            days_of_week=mask_to_days(habit.days_mask),
            scheduled_today=is_scheduled(habit.days_mask, today),
            today_status=today_status,
            created_at=habit.created_at,
        )
