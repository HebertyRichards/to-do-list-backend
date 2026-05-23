import asyncio
import json
import logging
from typing import Dict, List, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self):
        self._connections: Dict[int, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            if websocket not in self._connections[user_id]:
                self._connections[user_id].append(websocket)
        logger.debug(f"WS conectado user_id={user_id}")

    async def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        async with self._lock:
            conns = self._connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if not conns and user_id in self._connections:
                del self._connections[user_id]
        logger.debug(f"WS desconectado user_id={user_id}")

    async def push(self, user_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._connections.get(user_id, []))

        if not conns:
            return

        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    live = self._connections.get(user_id, [])
                    if ws in live:
                        live.remove(ws)


notification_manager = NotificationManager()
