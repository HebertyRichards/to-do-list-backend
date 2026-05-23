from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    payload: dict
    read_at: datetime | None
    created_at: datetime
