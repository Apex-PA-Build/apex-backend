from typing import Any

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import llm
from app.utils.prompts import build_weekly_review_prompt

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    if "target_date" in payload and hasattr(payload["target_date"], "isoformat"):
        payload["target_date"] = str(payload["target_date"])
    result = await client.table("goals").insert(payload).execute()
    return result.data[0]


async def get(user_id: str, goal_id: str) -> dict[str, Any]:
    client = await get_client()
    result = await client.table("goals").select("*").eq("id", goal_id).execute()
    if not result.data:
        raise NotFoundError("Goal")
    goal = result.data[0]
    if goal["user_id"] != user_id:
        raise ForbiddenError()
    return goal


async def list_goals(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    client = await get_client()
    query = (
        client.table("goals")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    result = await query.execute()
    return result.data or []


async def update(user_id: str, goal_id: str, data: dict[str, Any]) -> dict[str, Any]:
    goal = await get(user_id, goal_id)
    if goal["user_id"] != user_id:
        raise ForbiddenError()
    payload = {k: v for k, v in data.items() if v is not None}
    if "target_date" in payload and hasattr(payload["target_date"], "isoformat"):
        payload["target_date"] = str(payload["target_date"])
    client = await get_client()
    result = await client.table("goals").update(payload).eq("id", goal_id).execute()
    return result.data[0]


async def delete(user_id: str, goal_id: str) -> None:
    goal = await get(user_id, goal_id)
    if goal["user_id"] != user_id:
        raise ForbiddenError()
    client = await get_client()
    await client.table("goals").update({"status": "abandoned"}).eq("id", goal_id).execute()


async def recalculate_progress(user_id: str, goal_id: str) -> int:
    """Recalculate goal progress from linked tasks and update the goal."""
    client = await get_client()
    result = await (
        client.table("tasks")
        .select("status")
        .eq("goal_id", goal_id)
        .eq("user_id", user_id)
        .execute()
    )
    tasks = result.data or []
    if not tasks:
        return 0
    done = sum(1 for t in tasks if t["status"] == "done")
    pct = int((done / len(tasks)) * 100)
    await client.table("goals").update({"progress_pct": pct}).eq("id", goal_id).execute()
    return pct


async def weekly_review(user_id: str) -> dict[str, Any]:
    """Generate a narrative weekly review of all active goals."""
    from datetime import timedelta
    from app.utils.datetime import utcnow

    goals = await list_goals(user_id, status="active")
    week_ago = (utcnow() - timedelta(days=7)).isoformat()

    client = await get_client()
    completed_result = await (
        client.table("tasks")
        .select("title, goal_id, updated_at")
        .eq("user_id", user_id)
        .eq("status", "done")
        .gte("updated_at", week_ago)
        .execute()
    )
    completed = completed_result.data or []

    prompt = build_weekly_review_prompt(user_id, goals, completed)
    return await llm.extract_json(prompt, model=settings.model_medium)


async def alignment_check(user_id: str) -> dict[str, Any]:
    """Return what % of tasks are linked to goals."""
    client = await get_client()
    all_tasks = await client.table("tasks").select("goal_id").eq("user_id", user_id).eq("status", "pending").execute()
    tasks = all_tasks.data or []
    total = len(tasks)
    linked = sum(1 for t in tasks if t.get("goal_id"))
    pct = int((linked / total * 100)) if total else 0
    return {"total_tasks": total, "linked_to_goal": linked, "alignment_pct": pct}
