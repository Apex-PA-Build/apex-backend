import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.schemas.goal import (
    AlignmentCheck,
    GoalCreate,
    GoalProgressDetail,
    GoalRead,
    GoalUpdate,
    WeeklyReview,
)
from app.services.goal_service import (
    alignment_check,
    create_goal,
    get_goal,
    get_goal_progress,
    list_goals,
    update_goal,
    weekly_review,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("", response_model=list[GoalRead])
async def get_goals(request: Request, db: AsyncSession = Depends(get_db)) -> list[GoalRead]:
    goals = await list_goals(_uid(request), db)
    return [GoalRead.model_validate(g) for g in goals]


@router.post("", response_model=GoalRead, status_code=201)
async def add_goal(
    data: GoalCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GoalRead:
    goal = await create_goal(_uid(request), data, db)
    return GoalRead.model_validate(goal)


@router.patch("/{goal_id}", response_model=GoalRead)
async def edit_goal(
    goal_id: uuid.UUID,
    data: GoalUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GoalRead:
    goal = await update_goal(goal_id, _uid(request), data, db)
    return GoalRead.model_validate(goal)


@router.get("/{goal_id}/progress", response_model=GoalProgressDetail)
async def goal_progress(
    goal_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GoalProgressDetail:
    detail = await get_goal_progress(goal_id, _uid(request), db)
    return GoalProgressDetail(
        goal=GoalRead.model_validate(detail["goal"]),
        **{k: v for k, v in detail.items() if k != "goal"},
    )


@router.get("/weekly-review", response_model=WeeklyReview)
async def get_weekly_review(
    request: Request, db: AsyncSession = Depends(get_db)
) -> WeeklyReview:
    data = await weekly_review(_uid(request), db)
    return WeeklyReview(
        goals_reviewed=[GoalRead.model_validate(g) for g in data["goals_reviewed"]],
        **{k: v for k, v in data.items() if k != "goals_reviewed"},
    )


@router.get("/alignment-check", response_model=AlignmentCheck)
async def get_alignment_check(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AlignmentCheck:
    data = await alignment_check(_uid(request), db)
    return AlignmentCheck(**data)
