import asyncio
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import agent as agent_svc
from app.services import calendar as cal_svc
from app.services import llm
from app.services import memory as mem_svc
from app.services import task as task_svc
from app.utils.prompts import build_brief_prompt

logger = get_logger(__name__)


async def generate(user_id: str) -> dict[str, Any]:
    """Generate a personalized morning brief for the user."""
    # Fetch all context in parallel
    schedule_data, tasks, agent_messages = await asyncio.gather(
        cal_svc.get_today_schedule(user_id),
        task_svc.list_tasks(user_id, status="pending", limit=10),
        agent_svc.get_messages(user_id, direction="inbox"),
    )

    # Retrieve relevant memories for the day's context
    memories: list[dict[str, Any]] = []
    if schedule_data["events"]:
        first_event_title = schedule_data["events"][0].get("title", "")
        if first_event_title:
            memories = await mem_svc.search(user_id, first_event_title, limit=5)

    # Get user profile for personalisation
    client = await get_client()
    profile_result = await client.table("profiles").select("name, timezone, mood_today").eq("id", user_id).execute()
    profile = profile_result.data[0] if profile_result.data else {"name": "there", "timezone": "UTC", "mood_today": None}

    pending_agent = [m for m in agent_messages if m["status"] == "pending"]

    prompt = build_brief_prompt(
        user_name=profile["name"],
        events=schedule_data["events"],
        tasks=tasks,
        memories=memories,
        agent_messages=pending_agent,
    )

    brief = await llm.extract_json(prompt, model=settings.model_large)

    # Append schedule metadata
    brief["schedule_summary"] = {
        "total_meetings": len(schedule_data["events"]),
        "total_meeting_minutes": schedule_data["total_meeting_minutes"],
        "deep_work_available": schedule_data["deep_work_available"],
        "conflicts": schedule_data["conflicts"],
    }

    return brief


async def save_mood(user_id: str, mood: str) -> None:
    """Persist today's mood to the user's profile."""
    client = await get_client()
    await client.table("profiles").update({"mood_today": mood}).eq("id", user_id).execute()
