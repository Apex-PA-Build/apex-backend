from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.services.call_service import end_call_session, start_call_session

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.post("/start", status_code=201)
async def start_call(request: Request) -> dict:
    """
    Log the start of a call session.
    Returns a session_id to pass to the WebSocket call listener.
    """
    session_id = start_call_session(_uid(request))
    return {"session_id": session_id, "message": "Call session started. Connect to WS /ws/call."}


@router.post("/{session_id}/end")
async def end_call(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    End a call session.
    Triggers transcript extraction, task creation, and memory storage.
    """
    result = await end_call_session(session_id, _uid(request), db)
    return result



@router.get("/{session_id}/summary")
async def get_call_summary(session_id: str, request: Request) -> dict:
    """Retrieve the post-call summary for a completed session."""
    from app.services.call_service import _active_sessions
    if session_id in _active_sessions:
        return {"status": "in_progress", "session_id": session_id}
    return {"status": "ended", "session_id": session_id, "message": "Call has ended."}
