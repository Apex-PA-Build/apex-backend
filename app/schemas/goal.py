import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    category: str = Field(
        default="general",
        pattern="^(work|health|finance|personal|learning|general)$",
    )
    target_date: datetime | None = None
    check_in_schedule: str = Field(
        default="weekly", pattern="^(daily|weekly|monthly)$"
    )


class GoalRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    category: str
    status: str
    progress_pct: float
    target_date: datetime | None
    check_in_schedule: str
    created_at: datetime
    updated_at: datetime


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: str | None = Field(
        default=None, pattern="^(active|paused|completed|abandoned)$"
    )
    target_date: datetime | None = None
    progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class GoalProgressDetail(BaseModel):
    goal: GoalRead
    linked_tasks_total: int
    linked_tasks_done: int
    days_remaining: int | None
    on_track: bool
    weekly_actions_this_week: int
    suggestion: str


class WeeklyReview(BaseModel):
    week_label: str
    goals_reviewed: list[GoalRead]
    off_course: list[str]
    wins: list[str]
    narrative: str
    recommended_focus: str


class AlignmentCheck(BaseModel):
    aligned_pct: float
    unlinked_tasks: int
    suggestion: str
    goal_gaps: list[str]
