import hashlib
import logging
import secrets as _secrets
import uuid
from datetime import datetime, timezone

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.redis_client import get_redis
from app.config.settings import get_settings
from app.errors import AppException, ErrorCode
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schemas import (
    CurrentUser,
    ForgotPasswordInput,
    ForgotPasswordResponse,
    LoginInput,
    RegisterInput,
    ResendVerificationInput,
    ResetPasswordInput,
    SessionInfo,
    VerifyEmailInput,
)
from app.services.email_service import EmailService
from app.utils.cookies import (
    ACCESS_COOKIE,
    clear_auth_cookies,
    set_access_cookie,
    set_refresh_cookie,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

_RESET_TTL = 600
_VERIFY_TTL = 3600


def _make_code() -> str:
    return f"{_secrets.randbelow(1000000):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.users = UserRepository(db)
        self.settings = get_settings()
        self.email = EmailService()

    async def register(self, data: RegisterInput) -> CurrentUser:
        if await self.users.get_by_email(data.email):
            raise AppException(ErrorCode.EMAIL_ALREADY_REGISTERED)
        if await self.users.get_by_username(data.username):
            raise AppException(ErrorCode.USERNAME_TAKEN)

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
        )
        user = await self.users.create(user)
        await self.db.commit()

        await self._issue_verification_code(user)
        return CurrentUser.model_validate(user)

    async def verify_email(self, data: VerifyEmailInput, response: Response) -> SessionInfo:
        user = await self.users.get_by_email(data.email)
        if user is None:
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)
        if user.verified_at is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_VERIFIED)

        redis = await get_redis()
        stored = await redis.get(f"email_verify:{user.id}")
        if stored is None:
            raise AppException(ErrorCode.VERIFY_CODE_EXPIRED)

        stored_hash = stored if isinstance(stored, str) else stored.decode()
        if stored_hash != _hash_code(data.code):
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        await redis.delete(f"email_verify:{user.id}")
        user.verified_at = datetime.now(timezone.utc)
        session = await self._issue_session(user, response, remember_me=True)
        await self.db.commit()
        return session

    async def resend_verification(self, data: ResendVerificationInput) -> None:
        user = await self.users.get_by_email(data.email)
        if user is None:
            return
        if user.verified_at is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_VERIFIED)
        await self._issue_verification_code(user)

    async def login(self, data: LoginInput, response: Response) -> SessionInfo:
        user = await self.users.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

        if user.verified_at is None:
            raise AppException(ErrorCode.EMAIL_NOT_VERIFIED)

        session = await self._issue_session(user, response, remember_me=data.remember_me)
        await self.db.commit()
        return session

    async def refresh(self, refresh_token: str | None, response: Response) -> SessionInfo:
        if not refresh_token:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        payload = decode_token(refresh_token, expected_type="refresh")
        sub = payload.get("sub")
        if not sub:
            raise AppException(ErrorCode.TOKEN_INVALID)

        try:
            user_id = uuid.UUID(sub)
        except (ValueError, TypeError) as err:
            raise AppException(ErrorCode.TOKEN_INVALID) from err

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        new_session = await self._issue_session(user, response, remember_me=True)
        await self.db.commit()
        return new_session

    async def get_session(self, request: Request) -> SessionInfo:
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        payload = decode_token(token, expected_type="access")
        try:
            user_id = uuid.UUID(payload["sub"])
            access_expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (KeyError, ValueError, TypeError) as err:
            raise AppException(ErrorCode.TOKEN_INVALID) from err

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        session_expires_at = access_expires_at
        refresh_token = request.cookies.get(ACCESS_COOKIE.replace("access", "refresh"))
        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token, expected_type="refresh")
                session_expires_at = datetime.fromtimestamp(int(refresh_payload["exp"]), tz=timezone.utc)
            except Exception:
                logger.debug("Refresh token inválido, usando expiração do access token")

        return SessionInfo(
            user=CurrentUser.model_validate(user),
            session_expires_at=session_expires_at,
            access_expires_at=access_expires_at,
        )

    async def forgot_password(self, data: ForgotPasswordInput) -> ForgotPasswordResponse:
        user = await self.users.get_by_email(data.email)
        if user is None:
            return ForgotPasswordResponse(message="Se o email estiver cadastrado, você receberá um código.")

        code = _make_code()
        redis = await get_redis()
        await redis.setex(f"pwd_reset:{user.id}", _RESET_TTL, _hash_code(code))

        await self.email.send_password_reset_code(data.email, code)

        return ForgotPasswordResponse(message="Se o email estiver cadastrado, você receberá um código.")

    async def reset_password(self, data: ResetPasswordInput, response: Response) -> None:
        user = await self.users.get_by_email(data.email)
        if user is None:
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        redis = await get_redis()
        stored = await redis.get(f"pwd_reset:{user.id}")
        if stored is None:
            raise AppException(ErrorCode.VERIFY_CODE_EXPIRED)

        stored_hash = stored if isinstance(stored, str) else stored.decode()
        if stored_hash != _hash_code(data.code):
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        await redis.delete(f"pwd_reset:{user.id}")
        user.hashed_password = hash_password(data.new_password)
        clear_auth_cookies(response)
        await self.db.commit()

    async def logout(self, request: Request, response: Response) -> None:
        user_id: uuid.UUID | None = None
        for cookie_name, expected in (
            (ACCESS_COOKIE, "access"),
            (ACCESS_COOKIE.replace("access", "refresh"), "refresh"),
        ):
            token = request.cookies.get(cookie_name)
            if not token:
                continue
            try:
                payload = decode_token(token, expected_type=expected)
                sub = payload.get("sub")
                if sub:
                    user_id = uuid.UUID(sub)
                    break
            except Exception:
                continue

        clear_auth_cookies(response)

        if user_id is not None:
            try:
                redis = await get_redis()
                await redis.delete(f"pwd_reset:{user_id}", f"email_verify:{user_id}")
            except Exception as e:
                logger.warning("Redis cleanup falhou no logout: %s", e)

    async def _issue_verification_code(self, user: User) -> None:
        code = _make_code()
        redis = await get_redis()
        await redis.setex(f"email_verify:{user.id}", _VERIFY_TTL, _hash_code(code))
        await self.email.send_email_verification_code(user.email, code)

    async def _issue_session(self, user: User, response: Response, remember_me: bool) -> SessionInfo:
        now = datetime.now(timezone.utc)
        access_token, access_exp = create_access_token(subject=str(user.id))

        if remember_me:
            refresh_token, refresh_exp = create_refresh_token(subject=str(user.id))
            refresh_max_age = int((refresh_exp - now).total_seconds())
            set_refresh_cookie(response, refresh_token, refresh_max_age)
            session_expires_at = refresh_exp
            set_access_cookie(response, access_token, int((access_exp - now).total_seconds()))
        else:
            session_expires_at = access_exp
            set_access_cookie(response, access_token, None)

        return SessionInfo(
            user=CurrentUser.model_validate(user),
            session_expires_at=session_expires_at,
            access_expires_at=access_exp,
        )
