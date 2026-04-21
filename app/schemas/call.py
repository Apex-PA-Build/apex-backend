from typing import Any

from pydantic import BaseModel


class CallStartResponse(BaseModel):
    session_id: str
    started_at: str


class CallChunk(BaseModel):
    text: str


class ActionItem(BaseModel):
    title: str
    owner: str
    due_date: str | None = None


class CallSummary(BaseModel):
    session_id: str
    summary: str
    action_items: list[ActionItem]
    decisions: list[str]
    people_mentioned: list[str]
    follow_ups: list[str]
    key_dates: list[str]
    tasks_created: int
