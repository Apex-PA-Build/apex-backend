import asyncio
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationManager:
    """Manages active WebSocket connections for server-push events."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, []).append(websocket)
        logger.info("ws_connected", user_id=user_id, total=len(self._connections[user_id]))

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(user_id, None)
        logger.info("ws_disconnected", user_id=user_id)

    async def send(self, user_id: str, event: dict[str, Any]) -> None:
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(user_id, ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        for user_id in list(self._connections):
            await self.send(user_id, event)


notification_manager = NotificationManager()
