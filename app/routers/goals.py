from typing import Any

from fastapi import APIRouter, Query, Request

from app.middleware.auth import get_user_id
from app.schemas.common import MessageResponse
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.services import goal as goal_svc

router = APIRouter()


@router.get("", response_model=list[GoalRead])
async def list_goals(request: Request, status: str | None = Query(None)) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.list_goals(user_id, status=status)


@router.post("", response_model=GoalRead, status_code=201)
async def create_goal(request: Request, body: GoalCreate) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.create(user_id, body.model_dump())


@router.get("/review")
async def weekly_review(request: Request) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.weekly_review(user_id)


@router.get("/alignment")
async def alignment_check(request: Request) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.alignment_check(user_id)


@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(request: Request, goal_id: str) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.get(user_id, goal_id)


@router.patch("/{goal_id}", response_model=GoalRead)
async def update_goal(request: Request, goal_id: str, body: GoalUpdate) -> Any:
    user_id = get_user_id(request)
    return await goal_svc.update(user_id, goal_id, body.model_dump(exclude_none=True))


@router.post("/{goal_id}/recalculate")
async def recalculate_progress(request: Request, goal_id: str) -> Any:
    user_id = get_user_id(request)
    pct = await goal_svc.recalculate_progress(user_id, goal_id)
    return {"goal_id": goal_id, "progress_pct": pct}


@router.delete("/{goal_id}", response_model=MessageResponse)
async def delete_goal(request: Request, goal_id: str) -> Any:
    user_id = get_user_id(request)
    await goal_svc.delete(user_id, goal_id)
    return {"message": "Goal marked as abandoned"}
