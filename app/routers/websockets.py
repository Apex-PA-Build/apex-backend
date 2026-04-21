import asyncio
import json

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.logging import get_logger
from app.services import chat as chat_svc
from app.services.notification import notification_manager

router = APIRouter()
logger = get_logger(__name__)


def _verify_ws_token(token: str) -> str | None:
    """Decode and verify a Supabase JWT. Returns user_id or None."""
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    Streaming chat with APEX.

    Protocol:
      1. Client sends: {"token": "<supabase_jwt>"}
      2. Client sends: {"message": "..."}
      3. Server streams: {"type": "chunk"|"tool_status"|"tool_done"|"tool_result"|"done", ...}
      4. Repeat from step 2
    """
    await websocket.accept()

    # Auth handshake
    try:
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return

    user_id = _verify_ws_token(auth_data.get("token", ""))
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token")
        return

    await websocket.send_json({"type": "connected", "user_id": user_id})
    logger.info("ws_chat_connected", user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "").strip()
            if not message:
                continue

            async for event in chat_svc.stream(user_id, message):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("ws_chat_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("ws_chat_error", user_id=user_id, error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": "Something went wrong"})
        except Exception:
            pass


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """
    Server-push events (reminders, agent messages, notifications).

    Protocol:
      1. Client sends: {"token": "<supabase_jwt>"}
      2. Server pushes events as JSON objects
      3. Client sends {"type": "ping"} — server responds {"type": "pong"}
    """
    await websocket.accept()

    # Auth handshake
    try:
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return

    user_id = _verify_ws_token(auth_data.get("token", ""))
    if not user_id:
        await websocket.close(code=4003, reason="Invalid token")
        return

    await notification_manager.connect(user_id, websocket)
    await websocket.send_json({"type": "connected", "user_id": user_id})
    logger.info("ws_events_connected", user_id=user_id)

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        notification_manager.disconnect(user_id, websocket)
        logger.info("ws_events_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("ws_events_error", user_id=user_id, error=str(e))
        notification_manager.disconnect(user_id, websocket)
