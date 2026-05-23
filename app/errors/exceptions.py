from typing import Any
from app.errors.codes import ErrorCode, ERROR_CATALOG


class AppException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        spec = ERROR_CATALOG[code]
        self.code = code
        self.http_status = spec.http_status
        self.message = message or spec.message
        self.details = details or {}
        super().__init__(self.message)
