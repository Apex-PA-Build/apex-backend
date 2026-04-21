from datetime import datetime

from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"  # low | medium | high | critical
    energy_required: str | None = None  # low | medium | high
    due_at: datetime | None = None
    goal_id: str | None = None
    parent_task_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    energy_required: str | None = None
    due_at: datetime | None = None
    goal_id: str | None = None
    eisenhower_quadrant: int | None = None


class TaskRead(BaseModel):
    id: str
    user_id: str
    goal_id: str | None
    parent_task_id: str | None
    title: str
    description: str | None
    status: str
    priority: str
    eisenhower_quadrant: int | None
    energy_required: str | None
    due_at: str | None
    source_integration: str | None
    created_at: str
    updated_at: str


class BrainDumpRequest(BaseModel):
    text: str


class ReplanRequest(BaseModel):
    reason: str
    available_minutes: int = 120
