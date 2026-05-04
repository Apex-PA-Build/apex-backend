from typing import Any

from fastapi import APIRouter, Query, Request

from app.middleware.auth import get_user_id
from app.schemas.common import MessageResponse
from app.schemas.reminder import ReminderCreate, ReminderRead, SnoozeRequest
from app.services import reminder as reminder_svc

router = APIRouter()


@router.get("", response_model=list[ReminderRead])
async def list_reminders(
    request: Request,
    status: str | None = Query(None),
) -> Any:
    user_id = get_user_id(request)
    return await reminder_svc.list_reminders(user_id, status=status)


@router.post("", response_model=ReminderRead, status_code=201)
async def create_reminder(request: Request, body: ReminderCreate) -> Any:
    user_id = get_user_id(request)
    return await reminder_svc.create(user_id, body.model_dump())


@router.post("/{reminder_id}/snooze", response_model=ReminderRead)
async def snooze_reminder(request: Request, reminder_id: str, body: SnoozeRequest) -> Any:
    user_id = get_user_id(request)
    return await reminder_svc.snooze(user_id, reminder_id, body.minutes)


@router.post("/{reminder_id}/dismiss", response_model=MessageResponse)
async def dismiss_reminder(request: Request, reminder_id: str) -> Any:
    user_id = get_user_id(request)
    await reminder_svc.dismiss(user_id, reminder_id)
    return {"message": "Reminder dismissed"}


@router.post("/dismiss-all", response_model=MessageResponse)
async def dismiss_all(request: Request) -> Any:
    """Dismiss all fired reminders — clears the notifications panel."""
    user_id = get_user_id(request)
    await reminder_svc.dismiss_all(user_id)
    return {"message": "All notifications cleared"}
