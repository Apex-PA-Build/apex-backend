import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.schemas.task import (
    EisenhowerClassifyRequest,
    EisenhowerClassifyResponse,
    FocusNowResponse,
    TaskBulkDefer,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services.task_service import (
    bulk_defer,
    classify_tasks_eisenhower,
    create_task,
    delete_task,
    focus_now,
    list_tasks,
    update_task,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("", response_model=list[TaskRead])
async def get_tasks(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    tasks, _ = await list_tasks(_uid(request), db, status=status, limit=limit, offset=offset)
    return [TaskRead.model_validate(t) for t in tasks]


@router.post("", response_model=TaskRead, status_code=201)
async def add_task(
    data: TaskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    task = await create_task(_uid(request), data, db)
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def edit_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    task = await update_task(task_id, _uid(request), data, db)
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=204)
async def remove_task(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_task(task_id, _uid(request), db)


@router.get("/focus-now", response_model=FocusNowResponse)
async def get_focus_now(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> FocusNowResponse:
    """Return the single most important task to focus on right now."""
    result = await focus_now(_uid(request), db)
    return FocusNowResponse(
        task=TaskRead.model_validate(result["task"]) if result["task"] else None,
        reason=result["reason"],
        alternatives=[TaskRead.model_validate(t) for t in result["alternatives"]],
    )


@router.post("/bulk-defer", status_code=200)
async def defer_tasks(
    data: TaskBulkDefer,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await bulk_defer(data.task_ids, _uid(request), data.defer_to, db)
    return {"deferred": count}


@router.post("/classify", response_model=EisenhowerClassifyResponse)
async def classify_eisenhower(
    data: EisenhowerClassifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EisenhowerClassifyResponse:
    """Classify tasks into Eisenhower quadrants using LLM + heuristic fallback."""
    results = await classify_tasks_eisenhower(data.task_ids, _uid(request), db)
    return EisenhowerClassifyResponse(results=results)
