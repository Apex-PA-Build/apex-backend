from datetime import date

from pydantic import BaseModel


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    category: str = "work"  # work | health | finance | personal | learning
    target_date: date | None = None
    check_in_schedule: str = "weekly"  # daily | weekly | monthly


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    target_date: date | None = None
    check_in_schedule: str | None = None


class GoalRead(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    category: str
    status: str
    progress_pct: int
    target_date: str | None
    check_in_schedule: str
    created_at: str
    updated_at: str
