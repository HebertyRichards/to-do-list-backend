import json
import logging
import uuid

from app.config.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

_TTL_SECONDS = 60


def _first_page_key(user_id: uuid.UUID) -> str:
    return f"notif:first_page:{user_id}"


def _unread_key(user_id: uuid.UUID) -> str:
    return f"notif:unread:{user_id}"


async def get_first_page(user_id: uuid.UUID) -> dict | None:
    if not is_redis_available():
        return None
    try:
        raw = await (await get_redis()).get(_first_page_key(user_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Cache de notificacoes (get) falhou user_id=%s: %s", user_id, exc)
        return None


async def set_first_page(user_id: uuid.UUID, page: dict) -> None:
    if not is_redis_available():
        return
    try:
        await (await get_redis()).setex(_first_page_key(user_id), _TTL_SECONDS, json.dumps(page))
    except Exception as exc:
        logger.warning("Cache de notificacoes (set) falhou user_id=%s: %s", user_id, exc)


async def get_unread_count(user_id: uuid.UUID) -> int | None:
    if not is_redis_available():
        return None
    try:
        raw = await (await get_redis()).get(_unread_key(user_id))
        return int(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Cache de unread (get) falhou user_id=%s: %s", user_id, exc)
        return None


async def set_unread_count(user_id: uuid.UUID, count: int) -> None:
    if not is_redis_available():
        return
    try:
        await (await get_redis()).setex(_unread_key(user_id), _TTL_SECONDS, str(count))
    except Exception as exc:
        logger.warning("Cache de unread (set) falhou user_id=%s: %s", user_id, exc)


async def invalidate(user_id: uuid.UUID) -> None:
    if not is_redis_available():
        return
    try:
        await (await get_redis()).delete(_first_page_key(user_id), _unread_key(user_id))
    except Exception as exc:
        logger.warning("Cache de notificacoes (invalidate) falhou user_id=%s: %s", user_id, exc)
