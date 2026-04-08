import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IntegrationError
from app.core.logging import get_logger
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar import CalendarEventCreate
from app.services.integration_service import get_access_token
from app.utils.datetime_utils import find_free_blocks, slots_overlap

logger = get_logger(__name__)


async def sync_google_calendar(user_id: str, db: AsyncSession) -> dict:
    try:
        token = await get_access_token("google", user_id, db)
    except Exception:
        raise IntegrationError("Google Calendar not connected")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": datetime.now(timezone.utc).isoformat(),
                "maxResults": 50,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
    if resp.status_code != 200:
        raise IntegrationError(f"Google Calendar sync failed: {resp.status_code}")

    items = resp.json().get("items", [])
    synced = 0
    conflicts = 0

    for item in items:
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})
        start_str = start_raw.get("dateTime") or start_raw.get("date")
        end_str = end_raw.get("dateTime") or end_raw.get("date")
        if not start_str or not end_str:
            continue

        start_at = datetime.fromisoformat(start_str)
        end_at = datetime.fromisoformat(end_str)
        external_id = item.get("id", "")

        existing = await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.external_id == external_id,
                CalendarEvent.user_id == uuid.UUID(user_id),
            )
        )
        event = existing.scalar_one_or_none()

        if event:
            event.title = item.get("summary", "Untitled")
            event.start_at = start_at
            event.end_at = end_at
        else:
            event = CalendarEvent(
                user_id=uuid.UUID(user_id),
                external_id=external_id,
                title=item.get("summary", "Untitled"),
                description=item.get("description"),
                location=item.get("location"),
                start_at=start_at,
                end_at=end_at,
                attendees=item.get("attendees", []),
                source="google",
            )
            db.add(event)
            synced += 1

    # Basic conflict detection
    all_events = await get_today_events(user_id, db)
    for i, ev1 in enumerate(all_events):
        for ev2 in all_events[i + 1:]:
            if slots_overlap(ev1.start_at, ev1.end_at, ev2.start_at, ev2.end_at):
                conflicts += 1

    logger.info("calendar_synced", user_id=user_id, synced=synced, conflicts=conflicts)
    return {
        "provider": "google",
        "events_synced": synced,
        "conflicts_detected": conflicts,
        "last_synced_at": datetime.now(timezone.utc),
    }


async def get_today_events(user_id: str, db: AsyncSession) -> list[CalendarEvent]:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    result = await db.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == uuid.UUID(user_id),
            CalendarEvent.start_at >= day_start,
            CalendarEvent.start_at <= day_end,
            CalendarEvent.is_cancelled == False,  # noqa: E712
        )
        .order_by(CalendarEvent.start_at)
    )
    return list(result.scalars().all())


async def get_today_schedule(user_id: str, db: AsyncSession) -> dict:
    events = await get_today_events(user_id, db)
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=18, minute=0, second=0, microsecond=0)
    event_slots = [(e.start_at, e.end_at) for e in events]
    free_blocks = find_free_blocks(event_slots, day_start, day_end)
    total_meeting_min = sum(
        int((e.end_at - e.start_at).total_seconds() / 60) for e in events
    )
    deep_work_min = sum(
        int((b["end"] - b["start"]).total_seconds() / 60)
        for b in free_blocks
        if int((b["end"] - b["start"]).total_seconds() / 60) >= 45
    )
    return {
        "date": now.strftime("%Y-%m-%d"),
        "events": events,
        "free_blocks": [{"start": b["start"].isoformat(), "end": b["end"].isoformat()} for b in free_blocks],
        "total_meeting_minutes": total_meeting_min,
        "deep_work_available_minutes": deep_work_min,
    }


async def create_event(user_id: str, data: CalendarEventCreate, db: AsyncSession) -> CalendarEvent:
    event = CalendarEvent(user_id=uuid.UUID(user_id), **data.model_dump())
    db.add(event)
    await db.flush()
    return event


async def suggest_buffer(event_id: uuid.UUID, user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == uuid.UUID(user_id),
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Event {event_id} not found")

    attendee_count = len(event.attendees or [])
    suggested = 10
    if attendee_count > 5:
        suggested = 15
    if attendee_count > 10:
        suggested = 20

    return {
        "event_id": event_id,
        "suggested_buffer_minutes": suggested,
        "reason": f"Event has {attendee_count} attendees; buffer recommended for overrun.",
    }
