import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.cache import subscribe
from app.core.logging import get_logger
from app.core.security import get_user_id_from_token
from app.services.call_service import append_transcript_chunk
from app.services.notification_service import manager

router = APIRouter()
logger = get_logger(__name__)


async def _authenticate_ws(websocket: WebSocket) -> str | None:
    """Extract and validate JWT from query param or first WS message."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            data = json.loads(raw)
            token = data.get("token")
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=4001)
            return None

    try:
        return get_user_id_from_token(token)
    except Exception:
        await websocket.close(code=4001)
        return None


@router.websocket("/brief")
async def ws_brief(websocket: WebSocket) -> None:
    """
    Stream the morning brief narrative token-by-token.
    Client sends: {"token": "<jwt>"}
    Server sends: {"type": "token", "data": "..."} then {"type": "done"}
    """
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        return

    await manager.connect(user_id, websocket)
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select
        from app.services.llm_service import stream_chat

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.id == user_id)  # type: ignore[arg-type]
            )
            user = result.scalar_one_or_none()
            if not user:
                await websocket.send_json({"type": "error", "data": "User not found"})
                return

            system = (
                f"You are APEX, {user.name}'s assistant. "
                "Deliver a warm, intelligent morning brief in 4 sentences."
            )
            async for token in stream_chat(
                messages=[{"role": "user", "content": f"Good morning, {user.name}. Give me my brief."}],
                system=system,
            ):
                await websocket.send_json({"type": "token", "data": token})

        await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        logger.info("ws_brief_disconnected", user_id=user_id)
    except Exception as exc:
        logger.error("ws_brief_error", user_id=user_id, error=str(exc))
    finally:
        manager.disconnect(user_id, websocket)


@router.websocket("/call")
async def ws_call(websocket: WebSocket) -> None:
    """
    Live call transcript feed.
    Client sends: {"token": "<jwt>", "session_id": "<id>"} then raw transcript chunks.
    Server sends: {"type": "ack", "chunk_index": N} for each received chunk.
    """
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        return

    await manager.connect(user_id, websocket)
    session_id: str | None = None
    chunk_index = 0

    try:
        # Expect session init message
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        init = json.loads(raw)
        session_id = init.get("session_id")

        if not session_id:
            await websocket.send_json({"type": "error", "data": "session_id required"})
            return

        await websocket.send_json({"type": "ready", "session_id": session_id})

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                chunk = msg.get("chunk", "")
            except json.JSONDecodeError:
                chunk = raw

            if chunk:
                appended = append_transcript_chunk(session_id, chunk)
                if appended:
                    chunk_index += 1
                    await websocket.send_json({"type": "ack", "chunk_index": chunk_index})

    except WebSocketDisconnect:
        logger.info("ws_call_disconnected", user_id=user_id, chunks=chunk_index)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "data": "Init timeout"})
    except Exception as exc:
        logger.error("ws_call_error", user_id=user_id, error=str(exc))
    finally:
        manager.disconnect(user_id, websocket)


@router.websocket("/reminders")
async def ws_reminders(websocket: WebSocket) -> None:
    """
    Push real-time reminder nudges to the client.
    Subscribes to Redis channel and forwards messages.
    Client sends: {"token": "<jwt>"}
    Server sends: {"type": "reminder", "data": {...}}
    """
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        return

    await manager.connect(user_id, websocket)
    pubsub = await subscribe(f"reminders:{user_id}")

    try:
        await websocket.send_json({"type": "connected", "channel": "reminders"})

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json({"type": "reminder", "data": data})
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning("ws_reminders_parse_error", error=str(exc))

    except WebSocketDisconnect:
        logger.info("ws_reminders_disconnected", user_id=user_id)
    except Exception as exc:
        logger.error("ws_reminders_error", user_id=user_id, error=str(exc))
    finally:
        await pubsub.unsubscribe(f"reminders:{user_id}")
        manager.disconnect(user_id, websocket)


@router.websocket("/agent")
async def ws_agent(websocket: WebSocket) -> None:
    """
    PA-to-PA live event stream.
    Notifies user when their agent receives a message or a negotiation is resolved.
    Client sends: {"token": "<jwt>"}
    Server sends: {"type": "agent_event", "data": {...}}
    """
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        return

    await manager.connect(user_id, websocket)
    pubsub = await subscribe(f"agent:{user_id}")

    try:
        await websocket.send_json({"type": "connected", "channel": "agent"})

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json({"type": "agent_event", "data": data})
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning("ws_agent_parse_error", error=str(exc))

    except WebSocketDisconnect:
        logger.info("ws_agent_disconnected", user_id=user_id)
    except Exception as exc:
        logger.error("ws_agent_error", user_id=user_id, error=str(exc))
    finally:
        await pubsub.unsubscribe(f"agent:{user_id}")
        manager.disconnect(user_id, websocket)
