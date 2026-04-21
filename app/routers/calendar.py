from typing import Any

from fastapi import APIRouter, Request

from app.middleware.auth import get_user_id
from app.schemas.calendar import CalendarEventCreate, CalendarEventRead, TodaySchedule
from app.services import calendar as cal_svc

router = APIRouter()


@router.get("/today", response_model=TodaySchedule)
async def today_schedule(request: Request) -> Any:
    user_id = get_user_id(request)
    return await cal_svc.get_today_schedule(user_id)


@router.post("/events", response_model=CalendarEventRead, status_code=201)
async def create_event(request: Request, body: CalendarEventCreate) -> Any:
    user_id = get_user_id(request)
    return await cal_svc.create_event(user_id, body.model_dump())


@router.post("/sync/google")
async def sync_google(request: Request) -> Any:
    user_id = get_user_id(request)
    return await cal_svc.sync_google_calendar(user_id)
