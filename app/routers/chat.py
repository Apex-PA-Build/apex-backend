import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.middleware.auth import get_user_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat as chat_svc

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> Any:
    """Non-streaming chat — waits for full response."""
    user_id = get_user_id(request)
    result = await chat_svc.process(user_id, body.message, session_id=body.session_id)
    return result


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
    """
    SSE streaming — Claude streams natively, forwarded directly to the UI.
    Use this for voice mode and real-time chat. No WebSocket needed.
    Event types: tool_status | chunk | tool_result | done | error
    """
    user_id = get_user_id(request)

    async def generate():
        try:
            async for event in chat_svc.stream(user_id, body.message, session_id=body.session_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
