import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.redis_client import close_redis, init_redis
from app.config.settings import get_settings
from app.errors import AppException, register_exception_handlers
from app.routes.auth_routes import auth_routes
from app.routes.category_routes import category_routes
from app.routes.group_routes import group_routes
from app.routes.habit_routes import habit_routes
from app.routes.notification_routes import notification_routes
from app.routes.subtask_routes import subtask_routes
from app.routes.task_routes import task_routes
from app.routes.user_routes import user_routes
from app.utils import rate_limit
from app.ws.routes import ws_routes

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()


app = FastAPI(
    title="To-Do List API",
    version="1.1",
    lifespan=lifespan,
)

_RATE_LIMIT_EXEMPT_PATHS = {"/health"}


def _client_ip(request: Request) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
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
app.include_router(habit_routes)
app.include_router(group_routes)
app.include_router(notification_routes)
app.include_router(ws_routes)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
