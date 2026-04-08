from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.services.reminder_service import (
    dismiss_reminder,
    get_pending_reminders,
    snooze_reminder,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("")
async def list_reminders(request: Request) -> list[dict]:
    """Return all pending smart reminders for the current user."""
    return await get_pending_reminders(_uid(request))


@router.post("/snooze/{reminder_id}")
async def snooze(
    reminder_id: str,
    request: Request,
    snooze_minutes: int = 30,
) -> dict:
    """Snooze a reminder for the specified number of minutes."""
    snoozed = await snooze_reminder(_uid(request), reminder_id, snooze_minutes)
    return {"snoozed": snoozed, "reminder_id": reminder_id, "minutes": snooze_minutes}


@router.post("/dismiss/{reminder_id}")
async def dismiss(reminder_id: str, request: Request) -> dict:
    """Permanently dismiss a reminder."""
    dismissed = await dismiss_reminder(_uid(request), reminder_id)
    return {"dismissed": dismissed, "reminder_id": reminder_id}
