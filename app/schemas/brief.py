from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleBlock(BaseModel):
    start_at: datetime
    end_at: datetime
    title: str
    type: str  # meeting | focus | buffer | personal
    risk: str | None = None  # e.g. "attendee tends to run late"
    suggestion: str | None = None


class Risk(BaseModel):
    description: str
    severity: str  # low | medium | high
    mitigation: str | None = None


class DailyBrief(BaseModel):
    date: str
    greeting: str
    narrative: str = Field(description="APEX's curated story of the day ahead")
    schedule_blocks: list[ScheduleBlock]
    focus_recommendation: str
    risks: list[Risk]
    pending_agent_items: list[str]
    mood_checkin_prompt: str
    generated_at: datetime


class MoodCheckin(BaseModel):
    mood: str = Field(pattern="^(great|good|okay|tired|stressed|overwhelmed)$")
    note: str | None = Field(default=None, max_length=500)


class BriefHistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    date: str
    greeting: str
    generated_at: datetime
