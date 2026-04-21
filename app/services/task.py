import json
from typing import Any

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import llm
from app.utils.datetime import utcnow
from app.utils.prompts import build_eisenhower_prompt

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    if "due_at" in payload and hasattr(payload["due_at"], "isoformat"):
        payload["due_at"] = payload["due_at"].isoformat()
    result = await client.table("tasks").insert(payload).execute()
    task = result.data[0]
    # Classify asynchronously — fire and forget the quadrant classification
    if task.get("title"):
        await _classify_quadrant(task)
    return task


async def _classify_quadrant(task: dict[str, Any]) -> None:
    try:
        prompt = build_eisenhower_prompt(
            task["title"], task.get("description"), task.get("due_at")
        )
        raw = await llm.complete(prompt, max_tokens=5)
        quadrant = int(raw.strip()[0])
        if quadrant in (1, 2, 3, 4):
            client = await get_client()
            await client.table("tasks").update({"eisenhower_quadrant": quadrant}).eq("id", task["id"]).execute()
    except Exception:
        pass  # classification is best-effort


async def get(user_id: str, task_id: str) -> dict[str, Any]:
    client = await get_client()
    result = await client.table("tasks").select("*").eq("id", task_id).execute()
    if not result.data:
        raise NotFoundError("Task")
    task = result.data[0]
    if task["user_id"] != user_id:
        raise ForbiddenError()
    return task


async def list_tasks(
    user_id: str,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    client = await get_client()
    query = (
        client.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status:
        query = query.eq("status", status)
    result = await query.execute()
    return result.data or []


async def update(user_id: str, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
    task = await get(user_id, task_id)
    if task["user_id"] != user_id:
        raise ForbiddenError()
    payload = {k: v for k, v in data.items() if v is not None}
    if "due_at" in payload and hasattr(payload["due_at"], "isoformat"):
        payload["due_at"] = payload["due_at"].isoformat()
    client = await get_client()
    result = await client.table("tasks").update(payload).eq("id", task_id).execute()
    return result.data[0]


async def delete(user_id: str, task_id: str) -> None:
    task = await get(user_id, task_id)
    if task["user_id"] != user_id:
        raise ForbiddenError()
    client = await get_client()
    await client.table("tasks").delete().eq("id", task_id).execute()


async def focus_now(user_id: str, energy: str | None = None) -> dict[str, Any] | None:
    """Return the single most important task to work on right now."""
    tasks = await list_tasks(user_id, status="pending", limit=50)
    tasks += await list_tasks(user_id, status="in_progress", limit=20)

    if not tasks:
        return None

    now = utcnow()

    def score(t: dict[str, Any]) -> tuple[int, int, int]:
        p_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(t.get("priority", "medium"), 2)
        q_score = {1: 4, 2: 3, 3: 2, 4: 1}.get(t.get("eisenhower_quadrant"), 0)
        urgency = 0
        if t.get("due_at"):
            try:
                from app.utils.datetime import parse_iso
                due = parse_iso(t["due_at"])
                hours_until_due = (due - now).total_seconds() / 3600
                urgency = 3 if hours_until_due < 4 else 2 if hours_until_due < 24 else 1
            except Exception:
                pass
        return (-p_score - q_score - urgency, 0, 0)

    if energy:
        tasks = [t for t in tasks if not t.get("energy_required") or t["energy_required"] == energy] or tasks

    return min(tasks, key=score)


async def brain_dump(user_id: str, text: str) -> list[dict[str, Any]]:
    """Parse free-form text into discrete tasks."""
    prompt = f"""Parse this brain dump into a list of discrete tasks.

TEXT: {text}

Return ONLY valid JSON array:
[
  {{
    "title": "clear, actionable task title",
    "priority": "low|medium|high|critical",
    "description": "optional context or null"
  }}
]

Keep it concise. Maximum 10 tasks."""

    try:
        items: list[dict[str, Any]] = await llm.extract_json(prompt)
    except Exception:
        return []

    created = []
    for item in items[:10]:
        if item.get("title"):
            task = await create(user_id, {
                "title": item["title"],
                "description": item.get("description"),
                "priority": item.get("priority", "medium"),
            })
            created.append(task)
    return created


async def replan_day(user_id: str, reason: str, available_minutes: int) -> list[dict[str, Any]]:
    """Compassionately reschedule today's tasks given a new constraint."""
    tasks = await list_tasks(user_id, status="pending", limit=30)

    prompt = f"""The user's day has changed: {reason}
They now have approximately {available_minutes} minutes available.

CURRENT TASKS: {json.dumps([{"title": t["title"], "priority": t["priority"], "energy": t.get("energy_required")} for t in tasks], default=str)}

Decide which tasks to keep for today and which to defer. Be compassionate and realistic.

Return ONLY valid JSON:
{{
  "keep_today": ["task title 1", "task title 2"],
  "defer": ["task title 3"],
  "message": "A warm, honest 2-sentence message about the plan"
}}"""

    try:
        plan: dict[str, Any] = await llm.extract_json(prompt, model=settings.model_medium)
    except Exception:
        return tasks

    defer_titles = set(plan.get("defer", []))
    for task in tasks:
        if task["title"] in defer_titles:
            try:
                await update(user_id, task["id"], {"status": "deferred"})
            except Exception:
                pass

    return [t for t in tasks if t["title"] not in defer_titles]
