import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Habit, HabitEntry


class HabitRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Habit | None:
        stmt = select(Habit).where(Habit.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Habit]:
        stmt = (
            select(Habit)
            .where(Habit.owner_user_id == user_id)
            .order_by(Habit.created_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create(self, habit: Habit) -> Habit:
        self.db.add(habit)
        await self.db.flush()
        await self.db.refresh(habit)
        return habit

    async def delete(self, habit: Habit) -> None:
        await self.db.delete(habit)
        await self.db.flush()

    async def get_entry(self, habit_id: int, entry_date: date) -> HabitEntry | None:
        stmt = select(HabitEntry).where(
            HabitEntry.habit_id == habit_id,
            HabitEntry.entry_date == entry_date,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_entries_for_user_between(
        self, user_id: uuid.UUID, start: date, end: date
    ) -> list[HabitEntry]:
        stmt = (
            select(HabitEntry)
            .join(Habit, HabitEntry.habit_id == Habit.id)
            .where(
                Habit.owner_user_id == user_id,
                HabitEntry.entry_date >= start,
                HabitEntry.entry_date <= end,
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())
