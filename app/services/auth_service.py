import hashlib
import hmac
import logging
import secrets as _secrets
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.redis_client import get_redis, require_redis
from app.config.settings import get_settings
from app.errors import AppException, ErrorCode
from app.models import Group, GroupMember, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schemas import (
    CurrentUser,
    DeleteAccountInput,
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
from app.utils import rate_limit
from app.utils.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
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
from app.ws.manager import notification_manager

logger = logging.getLogger(__name__)

_RESET_TTL = 600
_VERIFY_TTL = 3600
_REFRESH_DENYLIST_TTL = 30 * 24 * 60 * 60


def _make_code() -> str:
    return f"{_secrets.randbelow(1000000):06d}"


def _hash_code(code: str) -> str:
    secret = get_settings().jwt_secret.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()


def _denylist_key(jti: str) -> str:
    return f"refresh_denylist:{jti}"


class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.users = UserRepository(db)
        self.settings = get_settings()
        self.email = EmailService()

    async def register(self, data: RegisterInput, background_tasks: BackgroundTasks) -> CurrentUser:
        await rate_limit.enforce_and_increment(
            f"rl:register:{data.email}",
            rate_limit.REGISTER_MAX_ATTEMPTS,
            rate_limit.REGISTER_WINDOW_SECONDS,
        )

        if await self.users.get_by_username(data.username):
            raise AppException(ErrorCode.USERNAME_TAKEN)
        if await self.users.get_by_email(data.email):
            background_tasks.add_task(self.email.send_account_exists_notice, data.email)
            return CurrentUser(
                email=data.email,
                username=data.username,
                avatar_url=None,
                onboarded=False,
            )

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
            timezone=data.timezone,
        )
        user = await self.users.create(user)
        await self.db.commit()

        await self._issue_verification_code(user, background_tasks)
        return CurrentUser.model_validate(user)

    async def verify_email(self, data: VerifyEmailInput, response: Response) -> SessionInfo:
        user = await self.users.get_by_email(data.email)
        if user is None:
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)
        if user.verified_at is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_VERIFIED)

        attempts_key = f"rl:verify_code:{user.id}"
        await rate_limit.check_only(attempts_key, rate_limit.VERIFY_CODE_MAX_ATTEMPTS)

        redis = await require_redis()
        stored = await redis.get(f"email_verify:{user.id}")
        if stored is None:
            raise AppException(ErrorCode.VERIFY_CODE_EXPIRED)

        stored_hash = stored if isinstance(stored, str) else stored.decode()
        if not hmac.compare_digest(stored_hash, _hash_code(data.code)):
            await rate_limit.increment_on_failure(attempts_key, _VERIFY_TTL)
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        await redis.delete(f"email_verify:{user.id}")
        await rate_limit.clear(attempts_key)
        user.verified_at = datetime.now(timezone.utc)
        session = await self._issue_session(user, response, remember_me=False)
        await self.db.commit()
        return session

    async def resend_verification(self, data: ResendVerificationInput, background_tasks: BackgroundTasks) -> None:
        await rate_limit.enforce_and_increment(
            f"rl:resend:{data.email}",
            rate_limit.RESEND_VERIFICATION_MAX_ATTEMPTS,
            rate_limit.RESEND_VERIFICATION_WINDOW_SECONDS,
        )
        user = await self.users.get_by_email(data.email)
        if user is None:
            return
        if user.verified_at is not None:
            raise AppException(ErrorCode.EMAIL_ALREADY_VERIFIED)
        await self._issue_verification_code(user, background_tasks)

    async def login(self, data: LoginInput, response: Response) -> SessionInfo:
        # Best-effort: o login deve continuar funcionando mesmo com o Redis fora.
        # Nesse cenario perde-se a protecao de forca bruta, mas a autenticacao segue.
        await rate_limit.enforce_and_increment(
            f"rl:login:{data.email}",
            rate_limit.LOGIN_MAX_ATTEMPTS,
            rate_limit.LOGIN_WINDOW_SECONDS,
            fail_open=True,
        )

        user = await self.users.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

        if user.verified_at is None:
            raise AppException(ErrorCode.EMAIL_NOT_VERIFIED)

        await rate_limit.clear(f"rl:login:{data.email}")
        session = await self._issue_session(user, response, remember_me=data.remember_me)
        await self.db.commit()
        return session

    async def refresh(self, refresh_token: str | None, response: Response) -> SessionInfo:
        if not refresh_token:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        payload = decode_token(refresh_token, expected_type="refresh")
        sub = payload.get("sub")
        jti = payload.get("jti")
        sid = payload.get("sid")
        if not sub or not jti or not sid:
            raise AppException(ErrorCode.TOKEN_INVALID)

        try:
            user_id = uuid.UUID(sub)
        except (ValueError, TypeError) as err:
            raise AppException(ErrorCode.TOKEN_INVALID) from err

        redis = await get_redis()
        try:
            reused = await redis.exists(_denylist_key(jti))
        except Exception as e:
            logger.warning("Denylist de refresh indisponivel (jti=%s): %s", jti, e)
            reused = 0
        if reused:
            response.headers["Clear-Site-Data"] = '"cache", "storage"'
            clear_auth_cookies(response)
            raise AppException(ErrorCode.REFRESH_REUSE_DETECTED)

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        if user.pwd_changed_at is not None:
            pwd_changed_ts = int(user.pwd_changed_at.timestamp())
            if int(sid) < pwd_changed_ts:
                response.headers["Clear-Site-Data"] = '"cache", "storage"'
                clear_auth_cookies(response)
                raise AppException(ErrorCode.REFRESH_REUSE_DETECTED)

        try:
            await redis.setex(_denylist_key(jti), _REFRESH_DENYLIST_TTL, "1")
        except Exception as e:
            logger.warning("Falha ao gravar denylist de refresh (jti=%s): %s", jti, e)

        session_started_at = datetime.fromtimestamp(int(sid), tz=timezone.utc)
        new_session = await self._issue_session(user, response, remember_me=True, session_started_at=session_started_at)
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
        refresh_token = request.cookies.get(REFRESH_COOKIE)
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

    async def forgot_password(
        self, data: ForgotPasswordInput, background_tasks: BackgroundTasks
    ) -> ForgotPasswordResponse:
        await rate_limit.enforce_and_increment(
            f"rl:forgot:{data.email}",
            rate_limit.FORGOT_PASSWORD_MAX_ATTEMPTS,
            rate_limit.FORGOT_PASSWORD_WINDOW_SECONDS,
        )

        msg = ForgotPasswordResponse(message="Se o email estiver cadastrado, você receberá um código.")
        user = await self.users.get_by_email(data.email)
        if user is None:
            return msg

        code = _make_code()
        redis = await require_redis()
        await redis.setex(f"pwd_reset:{user.id}", _RESET_TTL, _hash_code(code))

        background_tasks.add_task(self.email.send_password_reset_code, data.email, code)
        return msg

    async def reset_password(self, data: ResetPasswordInput, response: Response) -> None:
        user = await self.users.get_by_email(data.email)
        if user is None:
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        attempts_key = f"rl:reset_code:{user.id}"
        await rate_limit.check_only(attempts_key, rate_limit.RESET_CODE_MAX_ATTEMPTS)

        redis = await require_redis()
        stored = await redis.get(f"pwd_reset:{user.id}")
        if stored is None:
            raise AppException(ErrorCode.VERIFY_CODE_EXPIRED)

        stored_hash = stored if isinstance(stored, str) else stored.decode()
        if not hmac.compare_digest(stored_hash, _hash_code(data.code)):
            await rate_limit.increment_on_failure(attempts_key, _RESET_TTL)
            raise AppException(ErrorCode.VERIFY_CODE_INVALID)

        await redis.delete(f"pwd_reset:{user.id}")
        await rate_limit.clear(attempts_key)
        user.hashed_password = hash_password(data.new_password)
        user.pwd_changed_at = datetime.now(timezone.utc)
        clear_auth_cookies(response)
        await self.db.commit()

    async def delete_account(self, user: User, data: DeleteAccountInput, response: Response) -> None:
        if not verify_password(data.password, user.hashed_password):
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

        owned_groups_stmt = select(Group).where(Group.admin_user_id == user.id)
        owned_groups = list((await self.db.execute(owned_groups_stmt)).scalars().all())

        notifications: list[tuple[uuid.UUID, str, str]] = []
        for group in owned_groups:
            members_stmt = select(GroupMember.user_id).where(
                GroupMember.group_id == group.id,
                GroupMember.user_id != user.id,
            )
            member_ids = list((await self.db.execute(members_stmt)).scalars().all())
            for uid in member_ids:
                notifications.append((uid, group.slug, group.name))

        await self.users.delete(user)
        await self.db.commit()
        clear_auth_cookies(response)

        for uid, slug, name in notifications:
            await notification_manager.push(
                uid,
                {"type": "group_deleted", "group_slug": slug, "group_name": name},
            )

    async def logout(self, request: Request, response: Response) -> None:
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        if refresh_token:
            try:
                payload = decode_token(refresh_token, expected_type="refresh")
                jti = payload.get("jti")
                if jti:
                    redis = await get_redis()
                    await redis.setex(_denylist_key(jti), _REFRESH_DENYLIST_TTL, "1")
            except Exception as e:
                logger.warning("Falha ao revogar refresh no logout: %s", e)

        clear_auth_cookies(response)

    async def _issue_verification_code(self, user: User, background_tasks: BackgroundTasks) -> None:
        code = _make_code()
        redis = await require_redis()
        await redis.setex(f"email_verify:{user.id}", _VERIFY_TTL, _hash_code(code))
        background_tasks.add_task(self.email.send_email_verification_code, user.email, code)

    async def _issue_session(
        self,
        user: User,
        response: Response,
        remember_me: bool,
        session_started_at: datetime | None = None,
    ) -> SessionInfo:
        now = datetime.now(timezone.utc)
        access_token, access_exp = create_access_token(subject=str(user.id))

        if remember_me:
            refresh_token, refresh_exp, _jti, _sid = create_refresh_token(
                subject=str(user.id), session_started_at=session_started_at
            )
            refresh_max_age = max(int((refresh_exp - now).total_seconds()), 0)
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
