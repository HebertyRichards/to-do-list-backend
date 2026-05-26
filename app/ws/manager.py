import asyncio
import json
import logging
import uuid

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            if websocket not in self._connections[user_id]:
                self._connections[user_id].append(websocket)
        logger.debug("WS conectado user_id=%s", user_id)

    async def disconnect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        async with self._lock:
            conns = self._connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns and user_id in self._connections:
                del self._connections[user_id]
        logger.debug("WS desconectado user_id=%s", user_id)

    async def push(self, user_id: uuid.UUID, payload: dict[str, object]) -> None:
        async with self._lock:
            conns = list(self._connections.get(user_id, []))

        if not conns:
            return

        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except (RuntimeError, Exception) as exc:
                logger.debug("WS send falhou user_id=%s: %s", user_id, exc)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    live = self._connections.get(user_id, [])
                    if ws in live:
                        live.remove(ws)


notification_manager = NotificationManager()
