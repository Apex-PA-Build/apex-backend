import asyncio
import json
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per user and channel."""

    def __init__(self) -> None:
        # user_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)
        logger.info("ws_connected", user_id=user_id, total=len(self._connections[user_id]))

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(user_id, None)
        logger.info("ws_disconnected", user_id=user_id)

    async def send_to_user(self, user_id: str, data: dict[str, Any]) -> int:
        """Send a JSON message to all connections for a user. Returns sent count."""
        conns = self._connections.get(user_id, [])
        dead: list[WebSocket] = []
        sent = 0
        for ws in conns:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(data))
                    sent += 1
                else:
                    dead.append(ws)
            except Exception as exc:
                logger.warning("ws_send_failed", user_id=user_id, error=str(exc))
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)
        return sent

    async def broadcast(self, user_ids: list[str], data: dict[str, Any]) -> None:
        await asyncio.gather(*[self.send_to_user(uid, data) for uid in user_ids])

    def active_users(self) -> list[str]:
        return list(self._connections.keys())

    def connection_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))


# Singleton manager used across all WebSocket routers
manager = ConnectionManager()
