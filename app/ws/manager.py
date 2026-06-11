import asyncio
import json
import logging
import uuid

from fastapi import WebSocket

from app.config.redis_client import get_redis, is_redis_available
from app.utils import notification_cache

logger = logging.getLogger(__name__)

PUBSUB_CHANNEL = "notifications:push"
_RECONNECT_DELAY = 5


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
        # Push acontece sempre apos o commit; e o ponto unico para invalidar o cache.
        await notification_cache.invalidate(user_id)

        if is_redis_available():
            try:
                redis = await get_redis()
                await redis.publish(
                    PUBSUB_CHANNEL,
                    json.dumps({"user_id": str(user_id), "payload": payload}),
                )
                return
            except Exception as exc:
                logger.warning("Pub/sub publish falhou, entregando localmente: %s", exc)

        await self._deliver_local(user_id, payload)

    async def _deliver_local(self, user_id: uuid.UUID, payload: dict[str, object]) -> None:
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

    async def pubsub_listener(self) -> None:
        """Escuta o canal de push no Redis e entrega as conexoes locais.

        Permite multiplas instancias da API: quem publica nao precisa ser
        quem segura a conexao WebSocket do usuario.
        """
        while True:
            if not is_redis_available():
                await asyncio.sleep(_RECONNECT_DELAY)
                continue
            try:
                redis = await get_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(PUBSUB_CHANNEL)
                logger.info("Pub/sub de notificacoes inscrito em %s", PUBSUB_CHANNEL)
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        await self._deliver_local(uuid.UUID(data["user_id"]), data["payload"])
                    except Exception:
                        logger.exception("Mensagem pub/sub invalida ignorada")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Pub/sub listener caiu, reconectando em %ss: %s", _RECONNECT_DELAY, exc)
                await asyncio.sleep(_RECONNECT_DELAY)


notification_manager = NotificationManager()
