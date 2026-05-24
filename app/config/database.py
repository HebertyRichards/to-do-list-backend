import re
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config.settings import get_settings


settings = get_settings()


def _prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    connect_args: dict = {}
    if "sslmode=" in url:
        connect_args["ssl"] = True
        url = re.sub(r"[?&]sslmode=[^&\s]+", "", url)
        url = re.sub(r"[?&]channel_binding=[^&\s]+", "", url)
        url = re.sub(r"\?&", "?", url)
        url = url.rstrip("?&")
    return url, connect_args


_db_url, _connect_args = _prepare_asyncpg_url(settings.database_url)

engine = create_async_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
