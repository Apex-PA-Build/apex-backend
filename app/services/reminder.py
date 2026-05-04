from datetime import timedelta
from typing import Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.utils.datetime import utcnow

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    if "remind_at" in payload and hasattr(payload["remind_at"], "isoformat"):
        payload["remind_at"] = payload["remind_at"].isoformat()
    result = await client.table("reminders").insert(payload).execute()
    return result.data[0]


async def list_reminders(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    client = await get_client()
    query = (
        client.table("reminders")
        .select("*")
        .eq("user_id", user_id)
        .order("remind_at")
    )
    if status:
        query = query.eq("status", status)
    result = await query.execute()
    return result.data or []


async def snooze(user_id: str, reminder_id: str, minutes: int = 30) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("reminders")
        .select("*")
        .eq("id", reminder_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Reminder")

    snoozed_until = (utcnow() + timedelta(minutes=minutes)).isoformat()
    update = await (
        client.table("reminders")
        .update({"status": "snoozed", "snoozed_until": snoozed_until, "remind_at": snoozed_until})
        .eq("id", reminder_id)
        .execute()
    )
    return update.data[0]


async def dismiss(user_id: str, reminder_id: str) -> None:
    client = await get_client()
    result = await (
        client.table("reminders")
        .update({"status": "dismissed"})
        .eq("id", reminder_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Reminder")


async def get_due_reminders(user_id: str) -> list[dict[str, Any]]:
    """Fetch pending reminders that are due now (used by scheduler)."""
    client = await get_client()
    now = utcnow().isoformat()
    result = await (
        client.table("reminders")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .lte("remind_at", now)
        .execute()
    )
    return result.data or []


async def mark_fired(reminder_id: str) -> None:
    client = await get_client()
    await client.table("reminders").update({"status": "fired"}).eq("id", reminder_id).execute()


async def dismiss_all(user_id: str) -> None:
    client = await get_client()
    await (
        client.table("reminders")
        .update({"status": "dismissed"})
        .eq("user_id", user_id)
        .eq("status", "fired")
        .execute()
    )
