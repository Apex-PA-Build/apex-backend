from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("habits").insert(payload).execute()
    logger.info("habit_created", title=data.get("title"))
    return result.data[0]


async def list_habits(user_id: str) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("habits")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )
    return result.data or []


async def log(user_id: str, habit_title: str, note: str | None = None) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("habits")
        .select("id, title")
        .eq("user_id", user_id)
        .ilike("title", f"%{habit_title}%")
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": f"No habit found matching '{habit_title}'"}

    habit = result.data[0]
    log_result = await (
        client.table("habit_logs")
        .upsert({"habit_id": habit["id"], "user_id": user_id, "note": note}, on_conflict="habit_id,logged_at")
        .execute()
    )
    logger.info("habit_logged", habit=habit["title"])
    return {"habit": habit["title"], "logged": True}


async def get_streaks(user_id: str) -> list[dict[str, Any]]:
    from datetime import date, timedelta
    client = await get_client()
    habits = await list_habits(user_id)
    result = []
    for habit in habits:
        logs = await (
            client.table("habit_logs")
            .select("logged_at")
            .eq("habit_id", habit["id"])
            .order("logged_at", desc=True)
            .limit(60)
            .execute()
        )
        log_dates = {r["logged_at"] for r in (logs.data or [])}
        streak = 0
        today = date.today()
        while str(today - timedelta(days=streak)) in log_dates:
            streak += 1
        result.append({"habit": habit["title"], "streak": streak, "frequency": habit["frequency"]})
    return result


async def delete(user_id: str, habit_title: str) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("habits")
        .update({"is_active": False})
        .eq("user_id", user_id)
        .ilike("title", f"%{habit_title}%")
        .execute()
    )
    return {"deleted": bool(result.data)}
