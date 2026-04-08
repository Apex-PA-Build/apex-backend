import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    attendees: list[dict[str, Any]] = Field(default_factory=list)
    buffer_minutes: int = Field(default=0, ge=0, le=120)


class CalendarEventRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    attendees: list[Any]
    source: str
    buffer_minutes: int
    is_cancelled: bool


class TodaySchedule(BaseModel):
    date: str
    events: list[CalendarEventRead]
    free_blocks: list[dict[str, Any]]
    total_meeting_minutes: int
    deep_work_available_minutes: int


class SuggestBufferRequest(BaseModel):
    event_id: uuid.UUID
    reason: str | None = None


class SuggestBufferResponse(BaseModel):
    event_id: uuid.UUID
    suggested_buffer_minutes: int
    reason: str


class SyncResponse(BaseModel):
    provider: str
    events_synced: int
    conflicts_detected: int
    last_synced_at: datetime
