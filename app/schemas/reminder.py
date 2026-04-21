from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReminderCreate(BaseModel):
    title: str
    body: str | None = None
    type: str = "time"  # time | location | deadline | inactivity | relationship
    remind_at: datetime
    metadata: dict[str, Any] = {}


class ReminderRead(BaseModel):
    id: str
    title: str
    body: str | None
    type: str
    remind_at: str
    status: str
    metadata: dict[str, Any]
    created_at: str


class SnoozeRequest(BaseModel):
    minutes: int = 30
