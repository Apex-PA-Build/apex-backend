from typing import Any

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import llm
from app.services import memory as memory_svc
from app.services import task as task_svc
from app.utils.datetime import utcnow
from app.utils.prompts import build_call_extraction_prompt

logger = get_logger(__name__)


async def start_session(user_id: str, title: str | None = None) -> dict[str, Any]:
    client = await get_client()
    result = await client.table("call_sessions").insert({
        "user_id": user_id,
        "title": title or "Untitled Call",
        "status": "active",
    }).execute()
    return result.data[0]


async def append_transcript(user_id: str, session_id: str, text: str) -> None:
    client = await get_client()
    result = await (
        client.table("call_sessions")
        .select("user_id, transcript")
        .eq("id", session_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Call session")
    session = result.data[0]
    if session["user_id"] != user_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()

    new_transcript = (session["transcript"] or "") + "\n" + text.strip()
    await (
        client.table("call_sessions")
        .update({"transcript": new_transcript})
        .eq("id", session_id)
        .execute()
    )


async def end_session(user_id: str, session_id: str) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("call_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Call session")

    session = result.data[0]
    if session["status"] == "ended":
        return session  # idempotent

    transcript = session.get("transcript", "").strip()
    if not transcript:
        await (
            client.table("call_sessions")
            .update({"status": "ended", "ended_at": utcnow().isoformat()})
            .eq("id", session_id)
            .execute()
        )
        return {**session, "status": "ended", "summary": "No transcript recorded."}

    # Extract structure from transcript
    prompt = build_call_extraction_prompt(transcript)
    try:
        extracted: dict[str, Any] = await llm.extract_json(prompt, model=settings.model_medium)
    except Exception:
        extracted = {"summary": "Could not extract summary.", "action_items": [], "decisions": [], "people_mentioned": [], "follow_ups": [], "key_dates": []}

    # Auto-create tasks from action items owned by the user
    tasks_created = 0
    for item in extracted.get("action_items", []):
        owner = (item.get("owner") or "").lower()
        if owner in ("me", "i", user_id):
            try:
                await task_svc.create(user_id, {
                    "title": item["title"],
                    "due_at": item.get("due_date"),
                    "priority": "high",
                    "source_integration": "call",
                })
                tasks_created += 1
            except Exception:
                pass

    # Store memories from transcript
    await memory_svc.extract_and_store(user_id, transcript, source="call")

    now = utcnow().isoformat()
    await (
        client.table("call_sessions")
        .update({
            "status": "ended",
            "ended_at": now,
            "summary": extracted.get("summary"),
            "action_items": extracted.get("action_items", []),
            "decisions": extracted.get("decisions", []),
            "people": extracted.get("people_mentioned", []),
        })
        .eq("id", session_id)
        .execute()
    )

    return {
        **session,
        "status": "ended",
        "summary": extracted.get("summary"),
        "action_items": extracted.get("action_items", []),
        "decisions": extracted.get("decisions", []),
        "people_mentioned": extracted.get("people_mentioned", []),
        "follow_ups": extracted.get("follow_ups", []),
        "key_dates": extracted.get("key_dates", []),
        "tasks_created": tasks_created,
    }


async def get_session(user_id: str, session_id: str) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("call_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("Call session")
    return result.data[0]
