import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete, cache_get, cache_set
from app.core.logging import get_logger

logger = get_logger(__name__)

REMINDER_TTL = 86400 * 7  # 7 days


def _reminder_key(user_id: str) -> str:
    return f"reminders:{user_id}"


async def add_reminder(
    user_id: str,
    reminder_id: str,
    content: str,
    trigger_type: str,
    trigger_context: dict[str, Any],
) -> dict[str, Any]:
    """Schedule a smart reminder for a user."""
    reminder = {
        "id": reminder_id,
        "content": content,
        "trigger_type": trigger_type,  # time | location | deadline | inactivity | relationship
        "trigger_context": trigger_context,
        "status": "pending",  # pending | snoozed | dismissed | fired
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    key = _reminder_key(user_id)
    existing: list[dict] = await cache_get(key) or []
    existing.append(reminder)
    await cache_set(key, existing, ttl=REMINDER_TTL)
    logger.info("reminder_added", user_id=user_id, trigger_type=trigger_type)
    return reminder


async def get_pending_reminders(user_id: str) -> list[dict[str, Any]]:
    key = _reminder_key(user_id)
    all_reminders: list[dict] = await cache_get(key) or []
    return [r for r in all_reminders if r.get("status") == "pending"]


async def snooze_reminder(user_id: str, reminder_id: str, snooze_minutes: int = 30) -> bool:
    key = _reminder_key(user_id)
    reminders: list[dict] = await cache_get(key) or []
    for r in reminders:
        if r["id"] == reminder_id:
            r["status"] = "snoozed"
            r["snoozed_until"] = (
                datetime.now(timezone.utc).isoformat()
            )
            await cache_set(key, reminders, ttl=REMINDER_TTL)
            return True
    return False


async def dismiss_reminder(user_id: str, reminder_id: str) -> bool:
    key = _reminder_key(user_id)
    reminders: list[dict] = await cache_get(key) or []
    for r in reminders:
        if r["id"] == reminder_id:
            r["status"] = "dismissed"
            await cache_set(key, reminders, ttl=REMINDER_TTL)
            return True
    return False


async def create_deadline_reminder(
    user_id: str,
    task_id: str,
    task_title: str,
    due_at: datetime,
    db: AsyncSession,
) -> dict[str, Any]:
    reminder_id = str(uuid.uuid4())
    hours_left = max(0, (due_at - datetime.now(timezone.utc)).total_seconds() / 3600)
    content = (
        f"You said you'd finish '{task_title}' by {due_at.strftime('%-I:%M %p')}. "
        f"{'It is overdue.' if hours_left <= 0 else f'{int(hours_left)}h left.'}"
    )
    return await add_reminder(
        user_id=user_id,
        reminder_id=reminder_id,
        content=content,
        trigger_type="deadline",
        trigger_context={"task_id": task_id, "due_at": due_at.isoformat()},
    )


async def create_relationship_reminder(
    user_id: str,
    person_name: str,
    context: str,
) -> dict[str, Any]:
    reminder_id = str(uuid.uuid4())
    return await add_reminder(
        user_id=user_id,
        reminder_id=reminder_id,
        content=f"It's been a while since you reached out to {person_name}. {context}",
        trigger_type="relationship",
        trigger_context={"person": person_name},
    )
