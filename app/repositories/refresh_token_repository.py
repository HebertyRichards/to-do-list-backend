from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke(self, token: RefreshToken, replaced_by_jti: str | None = None) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        token.replaced_by_jti = replaced_by_jti
        await self.db.flush()

    async def get_latest_active_for_user(self, user_id: int) -> RefreshToken | None:
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .order_by(RefreshToken.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.db.execute(stmt)
