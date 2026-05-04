from typing import Any

import httpx

from app.core.exceptions import IntegrationError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.utils import datetime as dt_utils

logger = get_logger(__name__)


async def create_event(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    for field in ("start_at", "end_at"):
        if field in payload and hasattr(payload[field], "isoformat"):
            payload[field] = payload[field].isoformat()

    # Push to Google Calendar if connected
    try:
        await _push_to_google(user_id, payload)
    except Exception as e:
        logger.warning("google_calendar_push_failed", error=str(e))

    result = await client.table("calendar_events").insert(payload).execute()
    event = result.data[0]

    # Auto-schedule a follow-up reminder when the event ends
    try:
        await _schedule_followup_reminder(user_id, event)
    except Exception as e:
        logger.warning("followup_reminder_failed", error=str(e))

    return event


async def _schedule_followup_reminder(user_id: str, event: dict[str, Any]) -> None:
    """Create a reminder that fires when the event ends, asking if it was completed."""
    end_at = event.get("end_at")
    title = event.get("title", "your event")
    event_id = event.get("id")
    if not end_at:
        return
    client = await get_client()
    await client.table("reminders").insert({
        "user_id": user_id,
        "title": f"Did you complete: {title}?",
        "body": "Your session just ended. How did it go?",
        "type": "follow_up",
        "remind_at": end_at,
        "status": "pending",
        "metadata": {
            "type": "event_followup",
            "event_id": event_id,
            "event_title": title,
            "actions": [
                {
                    "label": "✅ Done",
                    "message": f"I completed '{title}'"
                },
                {
                    "label": "🔄 Reschedule",
                    "message": f"Reschedule '{title}' to tomorrow at the same time"
                },
                {
                    "label": "⏸ Partially done",
                    "message": f"I partially completed '{title}', need to continue later"
                },
            ],
        },
    }).execute()
    logger.info("followup_reminder_scheduled", event_id=event_id, remind_at=end_at)


async def _push_to_google(user_id: str, event: dict[str, Any]) -> None:
    from app.services.integration import get_access_token
    token = await get_access_token(user_id, "google")

    body = {
        "summary": event.get("title", "APEX Event"),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": {"dateTime": event["start_at"], "timeZone": "UTC"},
        "end":   {"dateTime": event["end_at"],   "timeZone": "UTC"},
        "attendees": [{"email": e} for e in event.get("attendees", [])],
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )

    if resp.status_code not in (200, 201):
        raise IntegrationError(f"Google Calendar create failed: {resp.status_code} {resp.text}")


async def get_today_events(user_id: str) -> list[dict[str, Any]]:
    start = dt_utils.start_of_day()
    end = dt_utils.end_of_day()
    client = await get_client()
    result = await (
        client.table("calendar_events")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_cancelled", False)
        .gte("start_at", start.isoformat())
        .lte("start_at", end.isoformat())
        .order("start_at")
        .execute()
    )
    return result.data or []


async def get_today_schedule(user_id: str) -> dict[str, Any]:
    events = await get_today_events(user_id)
    free_blocks = dt_utils.find_free_blocks(events)
    conflicts = dt_utils.detect_conflicts(events)
    total_meeting_min = sum(
        int((dt_utils.parse_iso(e["end_at"]) - dt_utils.parse_iso(e["start_at"])).total_seconds() / 60)
        for e in events
        if not e.get("is_cancelled")
    )
    deep_work_available = any(b["duration_minutes"] >= 90 for b in free_blocks)
    return {
        "events": events,
        "free_blocks": free_blocks,
        "total_meeting_minutes": total_meeting_min,
        "deep_work_available": deep_work_available,
        "conflicts": conflicts,
    }


async def sync_google_calendar(user_id: str) -> dict[str, Any]:
    """Fetch events from Google Calendar and upsert into Supabase."""
    from app.services.integration import get_access_token

    try:
        token = await get_access_token(user_id, "google")
    except Exception:
        raise IntegrationError("Google Calendar not connected. Connect it in Settings.")

    now = dt_utils.utcnow()
    time_min = now.isoformat()
    time_max = (now.replace(day=now.day + 30)).isoformat()  # next 30 days

    async with httpx.AsyncClient() as http:
        resp = await http.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": 100,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
            timeout=15,
        )
    if resp.status_code != 200:
        raise IntegrationError(f"Google Calendar API error: {resp.status_code}")

    items = resp.json().get("items", [])
    client = await get_client()
    synced = 0
    for item in items:
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
        if not start or not end:
            continue
        attendees = [
            a.get("email", "") for a in item.get("attendees", []) if a.get("email")
        ]
        payload = {
            "user_id": user_id,
            "external_id": item["id"],
            "title": item.get("summary", "Untitled"),
            "description": item.get("description"),
            "location": item.get("location"),
            "start_at": start,
            "end_at": end,
            "attendees": attendees,
            "source": "google",
            "is_cancelled": item.get("status") == "cancelled",
        }
        await (
            client.table("calendar_events")
            .upsert(payload, on_conflict="user_id,external_id,source")
            .execute()
        )
        synced += 1

    return {"synced": synced, "provider": "google"}
