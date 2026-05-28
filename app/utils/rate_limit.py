import logging

from app.config.redis_client import get_redis
from app.errors import AppException, ErrorCode

logger = logging.getLogger(__name__)


LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60

REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 60 * 60

FORGOT_PASSWORD_MAX_ATTEMPTS = 5
FORGOT_PASSWORD_WINDOW_SECONDS = 60 * 60

RESEND_VERIFICATION_MAX_ATTEMPTS = 5
RESEND_VERIFICATION_WINDOW_SECONDS = 60 * 60

VERIFY_CODE_MAX_ATTEMPTS = 5
RESET_CODE_MAX_ATTEMPTS = 5


async def enforce_and_increment(key: str, max_attempts: int, ttl_seconds: int) -> None:
    redis = await get_redis()
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, ttl_seconds)
        if current > max_attempts:
            raise AppException(ErrorCode.TOO_MANY_REQUESTS)
    except AppException:
        raise
    except Exception as e:
        logger.warning("Rate limit Redis falhou em %s: %s", key, e)


async def check_only(key: str, max_attempts: int) -> None:
    redis = await get_redis()
    try:
        raw = await redis.get(key)
        if raw is None:
            return
        current = int(raw)
        if current >= max_attempts:
            raise AppException(ErrorCode.TOO_MANY_REQUESTS)
    except AppException:
        raise
    except Exception as e:
        logger.warning("Rate limit check falhou em %s: %s", key, e)


async def increment_on_failure(key: str, ttl_seconds: int) -> None:
    redis = await get_redis()
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, ttl_seconds)
    except Exception as e:
        logger.warning("Rate limit increment falhou em %s: %s", key, e)


async def clear(key: str) -> None:
    redis = await get_redis()
    try:
        await redis.delete(key)
    except Exception as e:
        logger.warning("Rate limit clear falhou em %s: %s", key, e)
