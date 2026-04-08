import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.services.agent_service import get_pending_messages
from app.services.calendar_service import get_today_schedule
from app.services.llm_service import chat
from app.services.memory_service import get_user_memories
from app.services.task_service import list_tasks

logger = get_logger(__name__)


async def generate_daily_brief(user: User, db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)

    # Gather context in parallel (simplified sequential for clarity)
    schedule = await get_today_schedule(str(user.id), db)
    tasks, _ = await list_tasks(str(user.id), db, status="pending", limit=20)
    memories = await get_user_memories(str(user.id), db, limit=10)
    agent_msgs = await get_pending_messages(str(user.id), db)

    memory_snippets = [m.content for m in memories[:8]]
    pending_agent = [f"{msg.message_type}: {json.dumps(msg.content)[:80]}" for msg in agent_msgs[:5]]

    # Build context block for Claude
    context = f"""User: {user.name}
Timezone: {user.timezone}
Time: {now.strftime('%A, %B %-d at %-I:%M %p')}

Today's meetings ({len(schedule['events'])}):
{chr(10).join(f"  - {e.title} at {e.start_at.strftime('%-I:%M %p')}" for e in schedule['events'][:8])}

Pending tasks ({len(tasks)}):
{chr(10).join(f"  - [{t.priority}] {t.title}" for t in tasks[:8])}

What I know about {user.name}:
{chr(10).join(f"  - {m}" for m in memory_snippets)}

Pending PA-to-PA items:
{chr(10).join(f"  - {p}" for p in pending_agent) or '  None'}
"""

    system = (
        f"You are APEX, {user.name}'s personal assistant. "
        "Generate a morning brief as a warm, intelligent friend would — not a calendar dump. "
        "Be specific, flag real risks, and recommend one clear focus. "
        "Be honest if the day looks tough. "
        "Never say 'Great day ahead!' generically."
    )

    narrative = await chat(
        messages=[{
            "role": "user",
            "content": f"{context}\n\nWrite a 3-4 sentence morning brief narrative.",
        }],
        system=system,
        temperature=0.75,
    )

    focus_resp = await chat(
        messages=[{
            "role": "user",
            "content": f"{context}\n\nWhat is the single most important focus for today? One sentence.",
        }],
        system=system,
        temperature=0.3,
    )

    mood_prompt = await chat(
        messages=[{
            "role": "user",
            "content": f"{context}\n\nAsk a mood check-in question that is relevant to today's context. One sentence.",
        }],
        system=system,
        temperature=0.5,
    )

    risks = []
    if schedule["total_meeting_minutes"] > 240:
        risks.append({
            "description": f"{schedule['total_meeting_minutes']} minutes of meetings today — very little focus time.",
            "severity": "high",
            "mitigation": "Consider declining or shortening one meeting.",
        })
    if len(tasks) > 10:
        risks.append({
            "description": f"{len(tasks)} pending tasks may cause context switching.",
            "severity": "medium",
            "mitigation": "Use focus-now to identify the top 3.",
        })

    logger.info("brief_generated", user_id=str(user.id), events=len(schedule["events"]))

    return {
        "date": now.strftime("%Y-%m-%d"),
        "greeting": f"Good {'morning' if now.hour < 12 else 'afternoon'}, {user.name}.",
        "narrative": narrative.strip(),
        "schedule_blocks": [
            {
                "start_at": e.start_at,
                "end_at": e.end_at,
                "title": e.title,
                "type": "meeting",
            }
            for e in schedule["events"]
        ],
        "focus_recommendation": focus_resp.strip(),
        "risks": risks,
        "pending_agent_items": pending_agent,
        "mood_checkin_prompt": mood_prompt.strip(),
        "generated_at": now,
    }
