import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.llm_service import extract_json
from app.services.memory_service import extract_and_store_memories
from app.services.task_service import create_task
from app.schemas.task import TaskCreate
from app.utils.prompt_builder import build_call_extraction_prompt

logger = get_logger(__name__)

# In-memory session store (use Redis in production for multi-instance)
_active_sessions: dict[str, dict[str, Any]] = {}


def start_call_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    _active_sessions[session_id] = {
        "user_id": user_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "transcript_chunks": [],
    }
    logger.info("call_session_started", user_id=user_id, session_id=session_id)
    return session_id


def append_transcript_chunk(session_id: str, chunk: str) -> bool:
    session = _active_sessions.get(session_id)
    if not session:
        return False
    session["transcript_chunks"].append(chunk)
    return True


def get_partial_transcript(session_id: str) -> str:
    session = _active_sessions.get(session_id)
    if not session:
        return ""
    return " ".join(session["transcript_chunks"])


async def end_call_session(
    session_id: str,
    user_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    session = _active_sessions.pop(session_id, None)
    if not session:
        return {"error": "Session not found"}

    full_transcript = " ".join(session["transcript_chunks"])
    if not full_transcript.strip():
        return {"summary": "No transcript captured.", "action_items": [], "decisions": []}

    prompt = build_call_extraction_prompt(full_transcript)
    try:
        extracted: dict[str, Any] = await extract_json(prompt)  # type: ignore[assignment]
    except Exception as exc:
        logger.error("call_extraction_failed", error=str(exc), session_id=session_id)
        extracted = {}

    # Auto-create tasks from action items
    action_items = extracted.get("action_items", [])
    created_tasks = []
    for item in action_items[:10]:
        action = item.get("action", "")
        if not action:
            continue
        owner = item.get("owner", "").lower()
        if not owner or user_id.lower() in owner or "me" in owner or "i " in owner.lower():
            task = await create_task(
                user_id=user_id,
                data=TaskCreate(
                    title=action[:500],
                    source_integration="call",
                    description=f"From call session {session_id}",
                ),
                db=db,
            )
            created_tasks.append(str(task.id))

    # Store memories from call
    await extract_and_store_memories(
        user_id=user_id,
        text=full_transcript,
        source="call",
        db=db,
    )

    result = {
        "session_id": session_id,
        "summary": extracted.get("summary", ""),
        "decisions": extracted.get("decisions", []),
        "action_items": action_items,
        "follow_ups": extracted.get("follow_ups", []),
        "people_mentioned": extracted.get("people_mentioned", []),
        "dates_mentioned": extracted.get("dates_mentioned", []),
        "tasks_created": created_tasks,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "call_session_ended",
        session_id=session_id,
        user_id=user_id,
        tasks_created=len(created_tasks),
    )
    return result
