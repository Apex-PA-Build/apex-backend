from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("routines").insert(payload).execute()
    logger.info("routine_created", title=data.get("title"))
    return result.data[0]


async def list_routines(user_id: str) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("routines")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )
    return result.data or []


async def run(user_id: str, routine_title: str) -> dict[str, Any]:
    """Returns the steps of a routine for APEX to narrate and execute."""
    client = await get_client()
    result = await (
        client.table("routines")
        .select("*")
        .eq("user_id", user_id)
        .ilike("title", f"%{routine_title}%")
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": f"No routine found matching '{routine_title}'"}

    routine = result.data[0]
    await (
        client.table("routines")
        .update({"last_run_at": "now()"})
        .eq("id", routine["id"])
        .execute()
    )
    logger.info("routine_run", title=routine["title"])
    return {"title": routine["title"], "steps": routine["steps"], "running": True}
