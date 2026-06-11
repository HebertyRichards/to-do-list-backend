import uuid
from zoneinfo import ZoneInfo

from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.errors import AppException, ErrorCode
from app.models import User
from app.repositories.user_repository import UserRepository
from app.utils.cookies import ACCESS_COOKIE
from app.utils.security import decode_token


async def _user_from_token(token: str, db: AsyncSession) -> User:
    payload = decode_token(token, expected_type="access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as err:
        raise AppException(ErrorCode.TOKEN_INVALID) from err

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise AppException(ErrorCode.UNAUTHENTICATED)
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        raise AppException(ErrorCode.UNAUTHENTICATED)
    return await _user_from_token(token, db)


async def get_current_user_ws(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = websocket.cookies.get(ACCESS_COOKIE)
    if not token:
        raise AppException(ErrorCode.UNAUTHENTICATED)
    return await _user_from_token(token, db)


def get_request_timezone(request: Request) -> str | None:
    """Fuso enviado pelo cliente em cada requisição (header X-Timezone, nome IANA).

    Permite que o "hoje" siga o dispositivo do usuário em vez de um valor fixo.
    Retorna None se ausente ou inválido, deixando o chamador cair no fallback.
    """
    tz = request.headers.get("x-timezone")
    if not tz:
        return None
    try:
        ZoneInfo(tz)
    except Exception:
        return None
    return tz
