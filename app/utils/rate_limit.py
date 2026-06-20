import logging

from app.config.redis_client import get_redis, require_redis
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

CHANGE_EMAIL_MAX_ATTEMPTS = 5
CHANGE_EMAIL_WINDOW_SECONDS = 60 * 60
CHANGE_EMAIL_CODE_MAX_ATTEMPTS = 5

CHANGE_PASSWORD_MAX_ATTEMPTS = 5
CHANGE_PASSWORD_WINDOW_SECONDS = 60 * 60
CHANGE_PASSWORD_CODE_MAX_ATTEMPTS = 5

GLOBAL_MAX_REQUESTS = 100
GLOBAL_WINDOW_SECONDS = 60


async def enforce_global(identifier: str) -> None:
    redis = await get_redis()
    key = f"rl:global:{identifier}"
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, GLOBAL_WINDOW_SECONDS)
    except Exception as e:
        logger.warning("Rate limit global falhou em %s: %s", key, e)
        return
    if current > GLOBAL_MAX_REQUESTS:
        raise AppException(ErrorCode.TOO_MANY_REQUESTS)


async def enforce_and_increment(key: str, max_attempts: int, ttl_seconds: int, *, fail_open: bool = False) -> None:
    redis = await get_redis() if fail_open else await require_redis()
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, ttl_seconds)
    except Exception as e:
        if fail_open:
            logger.warning("Rate limit best-effort falhou em %s: %s", key, e)
            return
        logger.error("Rate limit indisponivel em %s: %s", key, e)
        raise AppException(ErrorCode.SERVICE_UNAVAILABLE) from e
    if current > max_attempts:
        raise AppException(ErrorCode.TOO_MANY_REQUESTS)


async def check_only(key: str, max_attempts: int) -> None:
    redis = await require_redis()
    try:
        raw = await redis.get(key)
    except Exception as e:
        logger.error("Rate limit check indisponivel em %s: %s", key, e)
        raise AppException(ErrorCode.SERVICE_UNAVAILABLE) from e
    if raw is None:
        return
    if int(raw) >= max_attempts:
        raise AppException(ErrorCode.TOO_MANY_REQUESTS)


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
