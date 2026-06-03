import asyncio
import logging

import redis.asyncio

from app.config.settings import get_settings
from app.errors import AppException, ErrorCode

logger = logging.getLogger(__name__)

THIRTY_DAYS = 60 * 60 * 24 * 30
MAX_RETRIES = 5
RETRY_DELAY = 5

_redis: redis.asyncio.Redis | None = None
_redis_available = False


class NullRedis:
    async def exists(self, *keys) -> int:
        return 0

    async def get(self, key: str):
        return None

    async def set(self, key: str, value, ex=None) -> None:
        return None

    async def setex(self, key: str, seconds: int, value) -> None:
        return None

    async def delete(self, *keys) -> int:
        return 0

    async def incr(self, key: str) -> int:
        return 1

    async def decr(self, key: str) -> int:
        return 0

    async def expire(self, key: str, seconds: int) -> int:
        return 0

    async def ttl(self, key: str) -> int:
        return -2

    async def sadd(self, key: str, *values) -> int:
        return 0

    async def srem(self, key: str, *values) -> int:
        return 0

    async def smembers(self, key: str) -> set:
        return set()

    async def hset(self, key: str, mapping: dict | None = None, **kwargs) -> int:
        return 0

    async def hgetall(self, key: str) -> dict:
        return {}

    async def hdel(self, key: str, *fields) -> int:
        return 0

    async def aclose(self) -> None:
        return None


_null_redis = NullRedis()


async def init_redis() -> None:
    global _redis, _redis_available
    settings = get_settings()

    if not settings.redis_enabled:
        _redis = None
        _redis_available = False
        logger.warning("Redis desativado via REDIS_ENABLED=false. Operando com NullRedis.")
        return

    url = settings.redis_url

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = redis.asyncio.from_url(url, decode_responses=True)
            await client.ping()
            _redis = client
            _redis_available = True
            logger.info("Redis conectado.")
            return
        except Exception as e:
            logger.warning(f"Redis tentativa {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

    logger.warning("Redis indisponivel apos tentativas. Operando com NullRedis.")
    _redis_available = False


async def get_redis() -> redis.asyncio.Redis | NullRedis:
    if not _redis_available or _redis is None:
        return _null_redis
    return _redis


def is_redis_available() -> bool:
    return _redis_available and _redis is not None


async def require_redis() -> redis.asyncio.Redis:
    if not _redis_available or _redis is None:
        raise AppException(ErrorCode.SERVICE_UNAVAILABLE)
    return _redis


async def close_redis() -> None:
    global _redis, _redis_available
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        _redis_available = False
