import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventRead,
    SuggestBufferRequest,
    SuggestBufferResponse,
    SyncResponse,
    TodaySchedule,
)
from app.services.calendar_service import (
    create_event,
    get_today_schedule,
    suggest_buffer,
    sync_google_calendar,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("/today", response_model=TodaySchedule)
async def today_schedule(
    request: Request, db: AsyncSession = Depends(get_db)
) -> TodaySchedule:
    data = await get_today_schedule(_uid(request), db)
    return TodaySchedule(
        date=data["date"],
        events=[CalendarEventRead.model_validate(e) for e in data["events"]],
        free_blocks=data["free_blocks"],
        total_meeting_minutes=data["total_meeting_minutes"],
        deep_work_available_minutes=data["deep_work_available_minutes"],
    )


@router.post("/events", response_model=CalendarEventRead, status_code=201)
async def add_event(
    data: CalendarEventCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CalendarEventRead:
    event = await create_event(_uid(request), data, db)
    return CalendarEventRead.model_validate(event)


@router.post("/sync", response_model=SyncResponse)
async def sync_calendar(
    request: Request, db: AsyncSession = Depends(get_db)
) -> SyncResponse:
    """Trigger a manual sync from connected Google Calendar."""
    result = await sync_google_calendar(_uid(request), db)
    return SyncResponse(**result)


@router.post("/suggest-buffer", response_model=SuggestBufferResponse)
async def get_suggest_buffer(
    data: SuggestBufferRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SuggestBufferResponse:
    result = await suggest_buffer(data.event_id, _uid(request), db)
    return SuggestBufferResponse(**result)
