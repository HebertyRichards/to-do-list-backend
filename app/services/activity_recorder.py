from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Activity, ActivityType
from app.models.task import TaskStatus
from app.utils.security import generate_slug


def seconds_between(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds()))


class ActivityRecorder:
    """Registra eventos imutáveis na sessão."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _add(
        self,
        actor_id,
        atype: ActivityType,
        payload: dict,
        *,
        task_id: int | None = None,
        subtask_id: int | None = None,
    ) -> None:
        self.db.add(
            Activity(
                slug=generate_slug(),
                actor_user_id=actor_id,
                type=atype,
                payload=payload,
                task_id=task_id,
                subtask_id=subtask_id,
            )
        )

    def created(self, actor_id, *, task_id=None, subtask_id=None) -> None:
        self._add(actor_id, ActivityType.created, {}, task_id=task_id, subtask_id=subtask_id)

    def status_changed(
        self,
        actor_id,
        old: TaskStatus,
        new: TaskStatus,
        duration_seconds: int,
        *,
        assignee_held_seconds: int | None = None,
        assignee_username: str | None = None,
        task_id=None,
        subtask_id=None,
    ) -> None:
        if new == TaskStatus.done:
            atype = ActivityType.delivered
        elif old == TaskStatus.done:
            atype = ActivityType.reopened
        else:
            atype = ActivityType.status_changed
        payload: dict = {
            "from": old.value,
            "to": new.value,
            "duration_seconds": duration_seconds,
        }
        if assignee_held_seconds is not None:
            payload["assignee_held_seconds"] = assignee_held_seconds
        if assignee_username is not None:
            payload["assignee_username"] = assignee_username
        self._add(actor_id, atype, payload, task_id=task_id, subtask_id=subtask_id)

    def category_moved(
        self,
        actor_id,
        from_slug: str,
        from_name: str,
        to_slug: str,
        to_name: str,
        duration_seconds: int,
        *,
        task_id: int,
    ) -> None:
        self._add(
            actor_id,
            ActivityType.category_moved,
            {
                "from_slug": from_slug,
                "from_name": from_name,
                "to_slug": to_slug,
                "to_name": to_name,
                "duration_seconds": duration_seconds,
            },
            task_id=task_id,
        )

    def assignee_changed(
        self,
        actor_id,
        from_username: str | None,
        to_username: str | None,
        *,
        prev_held_seconds: int | None = None,
        task_id=None,
        subtask_id=None,
    ) -> None:
        payload: dict = {"from": from_username, "to": to_username}
        if prev_held_seconds is not None:
            payload["prev_held_seconds"] = prev_held_seconds
        self._add(
            actor_id, ActivityType.assignee_changed, payload, task_id=task_id, subtask_id=subtask_id
        )

    def urgent_changed(self, actor_id, value: bool, *, task_id=None, subtask_id=None) -> None:
        self._add(
            actor_id, ActivityType.urgent_changed, {"to": value}, task_id=task_id, subtask_id=subtask_id
        )

    def dates_changed(
        self,
        actor_id,
        start_date: datetime | None,
        due_date: datetime | None,
        *,
        task_id=None,
        subtask_id=None,
    ) -> None:
        payload: dict = {}
        if start_date is not None:
            payload["start_date"] = start_date.isoformat()
        if due_date is not None:
            payload["due_date"] = due_date.isoformat()
        self._add(
            actor_id, ActivityType.dates_changed, payload, task_id=task_id, subtask_id=subtask_id
        )
