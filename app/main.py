import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.config.redis_client import init_redis, close_redis
from app.errors import register_exception_handlers
from app.routes.auth_routes import auth_routes
from app.routes.user_routes import user_routes
from app.routes.category_routes import category_routes
from app.routes.task_routes import task_routes
from app.routes.subtask_routes import subtask_routes
from app.routes.group_routes import group_routes
from app.routes.notification_routes import notification_routes
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
    version="0.1.0",
    lifespan=lifespan,
)

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
app.include_router(group_routes)
app.include_router(notification_routes)
app.include_router(ws_routes)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
