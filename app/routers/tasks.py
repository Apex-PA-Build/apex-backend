from typing import Any

from fastapi import APIRouter, Query, Request

from app.middleware.auth import get_user_id
from app.schemas.common import MessageResponse
from app.schemas.task import BrainDumpRequest, ReplanRequest, TaskCreate, TaskRead, TaskUpdate
from app.services import task as task_svc

router = APIRouter()


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> Any:
    user_id = get_user_id(request)
    return await task_svc.list_tasks(user_id, status=status, limit=limit, offset=offset)


@router.post("", response_model=TaskRead, status_code=201)
async def create_task(request: Request, body: TaskCreate) -> Any:
    user_id = get_user_id(request)
    return await task_svc.create(user_id, body.model_dump())


@router.get("/focus", response_model=TaskRead | None)
async def focus_now(
    request: Request,
    energy: str | None = Query(None, description="Filter by energy level: low|medium|high"),
) -> Any:
    user_id = get_user_id(request)
    return await task_svc.focus_now(user_id, energy=energy)


@router.post("/brain-dump", response_model=list[TaskRead], status_code=201)
async def brain_dump(request: Request, body: BrainDumpRequest) -> Any:
    user_id = get_user_id(request)
    return await task_svc.brain_dump(user_id, body.text)


@router.post("/replan", response_model=list[TaskRead])
async def replan_day(request: Request, body: ReplanRequest) -> Any:
    user_id = get_user_id(request)
    return await task_svc.replan_day(user_id, body.reason, body.available_minutes)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(request: Request, task_id: str) -> Any:
    user_id = get_user_id(request)
    return await task_svc.get(user_id, task_id)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(request: Request, task_id: str, body: TaskUpdate) -> Any:
    user_id = get_user_id(request)
    return await task_svc.update(user_id, task_id, body.model_dump(exclude_none=True))


@router.delete("/{task_id}", response_model=MessageResponse)
async def delete_task(request: Request, task_id: str) -> Any:
    user_id = get_user_id(request)
    await task_svc.delete(user_id, task_id)
    return {"message": "Task deleted"}
