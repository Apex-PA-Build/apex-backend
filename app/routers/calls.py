from typing import Any

from fastapi import APIRouter, Request

from app.middleware.auth import get_user_id
from app.schemas.call import CallChunk, CallStartResponse, CallSummary
from app.services import call as call_svc

router = APIRouter()


@router.post("/start", response_model=CallStartResponse, status_code=201)
async def start_call(request: Request, title: str | None = None) -> Any:
    user_id = get_user_id(request)
    session = await call_svc.start_session(user_id, title=title)
    return {"session_id": session["id"], "started_at": session["started_at"]}


@router.post("/{session_id}/transcript")
async def add_transcript(request: Request, session_id: str, body: CallChunk) -> dict[str, str]:
    user_id = get_user_id(request)
    await call_svc.append_transcript(user_id, session_id, body.text)
    return {"status": "ok"}


@router.post("/{session_id}/end", response_model=CallSummary)
async def end_call(request: Request, session_id: str) -> Any:
    user_id = get_user_id(request)
    result = await call_svc.end_session(user_id, session_id)
    return {
        "session_id": session_id,
        "summary": result.get("summary", ""),
        "action_items": result.get("action_items", []),
        "decisions": result.get("decisions", []),
        "people_mentioned": result.get("people_mentioned", []),
        "follow_ups": result.get("follow_ups", []),
        "key_dates": result.get("key_dates", []),
        "tasks_created": result.get("tasks_created", 0),
    }


@router.get("/{session_id}", response_model=dict)
async def get_call(request: Request, session_id: str) -> Any:
    user_id = get_user_id(request)
    return await call_svc.get_session(user_id, session_id)
