import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.goal import Goal
from app.models.task import Task
from app.schemas.goal import GoalCreate, GoalUpdate
from app.services.llm_service import chat

logger = get_logger(__name__)


async def create_goal(user_id: str, data: GoalCreate, db: AsyncSession) -> Goal:
    goal = Goal(user_id=uuid.UUID(user_id), **data.model_dump())
    db.add(goal)
    await db.flush()
    return goal


async def get_goal(goal_id: uuid.UUID, user_id: str, db: AsyncSession) -> Goal:
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == uuid.UUID(user_id))
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise NotFoundError(f"Goal {goal_id} not found")
    return goal


async def list_goals(user_id: str, db: AsyncSession) -> list[Goal]:
    result = await db.execute(
        select(Goal)
        .where(Goal.user_id == uuid.UUID(user_id), Goal.status == "active")
        .order_by(Goal.created_at.desc())
    )
    return list(result.scalars().all())


async def update_goal(goal_id: uuid.UUID, user_id: str, data: GoalUpdate, db: AsyncSession) -> Goal:
    goal = await get_goal(goal_id, user_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    return goal


async def get_goal_progress(goal_id: uuid.UUID, user_id: str, db: AsyncSession) -> dict:
    goal = await get_goal(goal_id, user_id, db)
    tasks_result = await db.execute(
        select(Task).where(Task.goal_id == goal_id, Task.user_id == uuid.UUID(user_id))
    )
    tasks = list(tasks_result.scalars().all())
    done = sum(1 for t in tasks if t.status == "done")
    total = len(tasks)
    progress = (done / total * 100) if total else 0.0
    goal.progress_pct = round(progress, 1)

    days_remaining: int | None = None
    on_track = True
    if goal.target_date:
        days_remaining = (goal.target_date - datetime.now(timezone.utc)).days
        on_track = progress >= max(0, 100 - days_remaining * 2)

    return {
        "goal": goal,
        "linked_tasks_total": total,
        "linked_tasks_done": done,
        "days_remaining": days_remaining,
        "on_track": on_track,
        "weekly_actions_this_week": sum(
            1 for t in tasks
            if t.updated_at and (datetime.now(timezone.utc) - t.updated_at).days <= 7
        ),
        "suggestion": (
            f"You haven't worked on '{goal.title}' much — protect some time for it."
            if not on_track else f"'{goal.title}' is on track. Keep going."
        ),
    }


async def weekly_review(user_id: str, db: AsyncSession) -> dict:
    goals = await list_goals(user_id, db)
    off_course = []
    wins = []

    for goal in goals:
        progress = await get_goal_progress(goal.id, user_id, db)
        if not progress["on_track"]:
            off_course.append(goal.title)
        elif progress["linked_tasks_done"] > 0:
            wins.append(f"{progress['linked_tasks_done']} tasks done toward '{goal.title}'")

    narrative = await chat(
        messages=[{
            "role": "user",
            "content": (
                f"Weekly review for a user with these goals: {[g.title for g in goals]}. "
                f"Off course: {off_course}. Wins: {wins}. "
                "Write a 3-sentence motivating but honest weekly review."
            ),
        }]
    )

    return {
        "week_label": datetime.now(timezone.utc).strftime("Week of %B %-d"),
        "goals_reviewed": goals,
        "off_course": off_course,
        "wins": wins,
        "narrative": narrative,
        "recommended_focus": off_course[0] if off_course else (goals[0].title if goals else ""),
    }


async def alignment_check(user_id: str, db: AsyncSession) -> dict:
    tasks_result = await db.execute(
        select(Task).where(
            Task.user_id == uuid.UUID(user_id),
            Task.status.in_(["pending", "in_progress"]),
        )
    )
    tasks = list(tasks_result.scalars().all())
    linked = sum(1 for t in tasks if t.goal_id is not None)
    total = len(tasks)
    pct = round(linked / total * 100, 1) if total else 100.0
    goals = await list_goals(user_id, db)
    goal_titles = [g.title for g in goals]

    return {
        "aligned_pct": pct,
        "unlinked_tasks": total - linked,
        "suggestion": (
            f"{total - linked} tasks aren't linked to any goal. Want me to review them?"
            if total - linked > 0 else "All your tasks are linked to goals."
        ),
        "goal_gaps": [g for g in goal_titles if not any(t.goal_id == g for t in tasks)],
    }
