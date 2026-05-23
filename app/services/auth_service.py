from datetime import datetime, timedelta, timezone
from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.settings import get_settings
from app.errors import AppException, ErrorCode
from app.models import RefreshToken, User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schemas import (
    CurrentUser,
    LoginInput,
    RegisterInput,
    SessionInfo,
)
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
    generate_jti,
    hash_password,
    verify_password,
)


class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = RefreshTokenRepository(db)
        self.settings = get_settings()

    async def register(self, data: RegisterInput, response: Response) -> SessionInfo:
        if await self.users.get_by_email(data.email):
            raise AppException(ErrorCode.EMAIL_ALREADY_REGISTERED)
        if await self.users.get_by_username(data.username):
            raise AppException(ErrorCode.USERNAME_TAKEN)

        user = User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
        )
        user = await self.users.create(user)
        session = await self._issue_session(user, response, session_started_at=None)
        await self.db.commit()
        return session

    async def login(self, data: LoginInput, response: Response) -> SessionInfo:
        user = await self.users.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

        session = await self._issue_session(user, response, session_started_at=None)
        await self.db.commit()
        return session

    async def refresh(self, refresh_token: str, response: Response) -> SessionInfo:
        if not refresh_token:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        payload = decode_token(refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        sub = payload.get("sub")
        sea = payload.get("sea")

        if not jti or not sub or not sea:
            raise AppException(ErrorCode.TOKEN_INVALID)

        existing = await self.tokens.get_by_jti(jti)
        if existing is None:
            raise AppException(ErrorCode.TOKEN_INVALID)

        if existing.revoked_at is not None:
            await self.tokens.revoke_all_for_user(existing.user_id)
            await self.db.commit()
            clear_auth_cookies(response)
            raise AppException(ErrorCode.REFRESH_REUSE_DETECTED)

        session_expires_at = datetime.fromtimestamp(int(sea), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        if now >= session_expires_at:
            await self.tokens.revoke(existing)
            await self.db.commit()
            clear_auth_cookies(response)
            raise AppException(ErrorCode.SESSION_EXPIRED)

        user = await self.users.get_by_id(int(sub))
        if user is None:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        new_session = await self._issue_session(
            user,
            response,
            session_started_at=existing.session_started_at,
            session_expires_at_override=session_expires_at,
            previous_jti=jti,
        )
        await self.tokens.revoke(existing, replaced_by_jti=new_session.access_expires_at.isoformat())
        await self.db.commit()
        return new_session

    async def get_session(self, request: Request) -> SessionInfo:
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        payload = decode_token(token, expected_type="access")
        try:
            user_id = int(payload["sub"])
            access_expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (KeyError, ValueError, TypeError):
            raise AppException(ErrorCode.TOKEN_INVALID)

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AppException(ErrorCode.UNAUTHENTICATED)

        active_token = await self.tokens.get_latest_active_for_user(user_id)
        session_expires_at = active_token.session_expires_at if active_token else access_expires_at

        return SessionInfo(
            user=CurrentUser.model_validate(user),
            session_expires_at=session_expires_at,
            access_expires_at=access_expires_at,
        )

    async def logout(self, refresh_token: str | None, response: Response) -> None:
        if refresh_token:
            try:
                payload = decode_token(refresh_token, expected_type="refresh")
                jti = payload.get("jti")
                if jti:
                    existing = await self.tokens.get_by_jti(jti)
                    if existing and existing.revoked_at is None:
                        await self.tokens.revoke(existing)
                        await self.db.commit()
            except AppException:
                pass
        clear_auth_cookies(response)

    async def _issue_session(
        self,
        user: User,
        response: Response,
        session_started_at: datetime | None,
        session_expires_at_override: datetime | None = None,
        previous_jti: str | None = None,
    ) -> SessionInfo:
        now = datetime.now(timezone.utc)
        started = session_started_at or now
        session_expires_at = session_expires_at_override or (
            started + timedelta(days=self.settings.refresh_token_days)
        )

        access_token, access_exp = create_access_token(subject=str(user.id))
        jti = generate_jti()
        refresh_token, refresh_exp = create_refresh_token(
            subject=str(user.id),
            jti=jti,
            session_expires_at=session_expires_at,
        )

        token_row = RefreshToken(
            user_id=user.id,
            jti=jti,
            session_started_at=started,
            session_expires_at=session_expires_at,
            expires_at=refresh_exp,
        )
        await self.tokens.create(token_row)

        access_max_age = int((access_exp - now).total_seconds())
        refresh_max_age = int((refresh_exp - now).total_seconds())
        set_access_cookie(response, access_token, access_max_age)
        set_refresh_cookie(response, refresh_token, refresh_max_age)

        return SessionInfo(
            user=CurrentUser.model_validate(user),
            session_expires_at=session_expires_at,
            access_expires_at=access_exp,
        )
