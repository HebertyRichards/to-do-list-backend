import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors.codes import ERROR_CATALOG, ErrorCode
from app.errors.exceptions import AppException

logger = logging.getLogger(__name__)


def _payload(code: ErrorCode, message: str, details: dict | None = None) -> dict:
    body = {"error": {"code": code.value, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


async def app_exception_handler(request: Request, exc: AppException):
    if exc.http_status >= 500:
        logger.error(f"[{exc.code.value}] {exc.message} path={request.url.path}")
    return JSONResponse(
        status_code=exc.http_status,
        content=_payload(exc.code, exc.message, exc.details),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_payload(
            ErrorCode.VALIDATION_ERROR,
            ERROR_CATALOG[ErrorCode.VALIDATION_ERROR].message,
            {"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Erro nao tratado em {request.url.path}: {exc}")
    spec = ERROR_CATALOG[ErrorCode.INTERNAL_SERVER_ERROR]
    return JSONResponse(
        status_code=spec.http_status,
        content=_payload(ErrorCode.INTERNAL_SERVER_ERROR, spec.message),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
