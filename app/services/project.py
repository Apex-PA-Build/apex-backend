from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("projects").insert(payload).execute()
    logger.info("project_created", title=data.get("title"))
    return result.data[0]


async def list_projects(user_id: str, status: str | None = None) -> list[dict[str, Any]]:
    client = await get_client()
    query = (
        client.table("projects")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    result = await query.execute()
    return result.data or []


async def get_status(user_id: str, project_title: str) -> dict[str, Any]:
    client = await get_client()
    proj = await (
        client.table("projects")
        .select("id, title, status, due_date, description")
        .eq("user_id", user_id)
        .ilike("title", f"%{project_title}%")
        .limit(1)
        .execute()
    )
    if not proj.data:
        return {"error": f"No project found matching '{project_title}'"}

    project = proj.data[0]
    tasks = await (
        client.table("tasks")
        .select("title, status, priority, due_at")
        .eq("user_id", user_id)
        .eq("goal_id", project["id"])
        .execute()
    )
    return {**project, "tasks": tasks.data or []}


async def update(user_id: str, project_title: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    proj = await (
        client.table("projects")
        .select("id")
        .eq("user_id", user_id)
        .ilike("title", f"%{project_title}%")
        .limit(1)
        .execute()
    )
    if not proj.data:
        return {"error": f"No project found matching '{project_title}'"}
    result = await (
        client.table("projects")
        .update(data)
        .eq("id", proj.data[0]["id"])
        .execute()
    )
    return result.data[0]
