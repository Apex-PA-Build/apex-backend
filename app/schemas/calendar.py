from datetime import datetime

from pydantic import BaseModel


class CalendarEventCreate(BaseModel):
    title: str
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    attendees: list[str] = []


class CalendarEventRead(BaseModel):
    id: str
    title: str
    description: str | None
    location: str | None
    start_at: str
    end_at: str
    attendees: list[str]
    source: str
    buffer_before: int
    is_cancelled: bool


class FreeBlock(BaseModel):
    start_at: str
    end_at: str
    duration_minutes: int


class TodaySchedule(BaseModel):
    events: list[CalendarEventRead]
    free_blocks: list[FreeBlock]
    total_meeting_minutes: int
    deep_work_available: bool
    conflicts: list[str]
