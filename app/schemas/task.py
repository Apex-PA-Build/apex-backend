import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    energy_required: str | None = Field(default="medium", pattern="^(low|medium|high)$")
    due_at: datetime | None = None
    goal_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    source_integration: str | None = None


class TaskRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    eisenhower_quadrant: int | None
    energy_required: str
    due_at: datetime | None
    goal_id: uuid.UUID | None
    source_integration: str | None
    created_at: datetime
    updated_at: datetime


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(pending|in_progress|done|deferred|cancelled)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    energy_required: str | None = Field(default=None, pattern="^(low|medium|high)$")
    due_at: datetime | None = None
    goal_id: uuid.UUID | None = None
    eisenhower_quadrant: int | None = Field(default=None, ge=1, le=4)


class TaskBulkDefer(BaseModel):
    task_ids: list[uuid.UUID] = Field(min_length=1)
    defer_to: datetime


class EisenhowerClassifyRequest(BaseModel):
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class EisenhowerClassifyResponse(BaseModel):
    results: dict[str, int]  # task_id -> quadrant (1-4)


class FocusNowResponse(BaseModel):
    task: TaskRead | None
    reason: str
    alternatives: list[TaskRead]

class BrainDumpRequest(BaseModel):
    text: str = Field(min_length=1)

class BrainDumpResponse(BaseModel):
    tasks_created: list[TaskRead]

class ReplanDayRequest(BaseModel):
    context: str = Field(min_length=1)

class ReplanDayResponse(BaseModel):
    message: str
    tasks_rescheduled: int
    tasks_deferred: int
