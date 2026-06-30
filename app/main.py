import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config.database import engine
from app.config.logging_config import setup_logging
from app.config.redis_client import close_redis, get_redis, init_redis, is_redis_available
from app.config.settings import get_settings
from app.errors import AppException, register_exception_handlers
from app.routes.auth_routes import auth_routes
from app.routes.category_routes import category_routes
from app.routes.comment_routes import comment_routes
from app.routes.group_routes import group_routes
from app.routes.habit_routes import habit_routes
from app.routes.notification_routes import notification_routes
from app.routes.subtask_routes import subtask_routes
from app.routes.task_routes import task_routes
from app.routes.user_routes import user_routes
from app.services.daily_reminder_service import daily_reminder_loop
from app.utils import rate_limit
from app.ws.manager import notification_manager
from app.ws.routes import ws_routes

settings = get_settings()

setup_logging(settings.log_level, json_logs=settings.log_json or settings.is_production)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    background_tasks = [
        asyncio.create_task(daily_reminder_loop()),
        asyncio.create_task(notification_manager.pubsub_listener()),
    ]
    yield
    for task in background_tasks:
        task.cancel()
    for task in background_tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await close_redis()


app = FastAPI(
    title="To-Do List API",
    version="1.1",
    lifespan=lifespan,
)

_RATE_LIMIT_EXEMPT_PATHS = {"/health", "/ready"}


def _client_ip(request: Request) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            n = settings.trusted_proxy_count
            if parts and n >= 1 and len(parts) >= n:
                return parts[-n]
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in _RATE_LIMIT_EXEMPT_PATHS:
        return await call_next(request)
    try:
        await rate_limit.enforce_global(_client_ip(request))
    except AppException as exc:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": {"code": exc.code.value, "message": exc.message}},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization", "Cookie"],
)

register_exception_handlers(app)

app.include_router(auth_routes)
app.include_router(user_routes)
app.include_router(category_routes)
app.include_router(task_routes)
app.include_router(subtask_routes)
app.include_router(comment_routes)
app.include_router(habit_routes)
app.include_router(group_routes)
app.include_router(notification_routes)
app.include_router(ws_routes)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["meta"])
async def ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "dependency": "database"})

    if settings.redis_enabled:
        if not is_redis_available():
            return JSONResponse(status_code=503, content={"status": "unavailable", "dependency": "redis"})
        try:
            await (await get_redis()).ping()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable", "dependency": "redis"})

    return {"status": "ready"}
