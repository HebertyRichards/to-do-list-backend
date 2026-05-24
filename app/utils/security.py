import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict, overload
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config.settings import get_settings
from app.errors import AppException, ErrorCode

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AccessPayload(TypedDict):
    sub: str
    iat: int
    exp: int
    type: Literal["access"]


class RefreshPayload(TypedDict):
    sub: str
    iat: int
    exp: int
    type: Literal["refresh"]


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def generate_group_key() -> str:
    return secrets.token_urlsafe(32)


def hash_group_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_group_key(key: str, key_hash: str) -> bool:
    return secrets.compare_digest(hash_group_key(key), key_hash)


def generate_slug() -> str:
    return secrets.token_urlsafe(8)


def generate_jti() -> str:
    return secrets.token_hex(16)


def create_access_token(subject: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    payload: AccessPayload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_days)
    payload: RefreshPayload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


@overload
def decode_token(token: str, expected_type: Literal["access"]) -> AccessPayload: ...
@overload
def decode_token(token: str, expected_type: Literal["refresh"]) -> RefreshPayload: ...
@overload
def decode_token(token: str, expected_type: None = None) -> AccessPayload | RefreshPayload: ...


def decode_token(
    token: str,
    expected_type: Literal["access", "refresh"] | None = None,
) -> AccessPayload | RefreshPayload:
    settings = get_settings()
    try:
        payload: AccessPayload | RefreshPayload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise AppException(ErrorCode.TOKEN_EXPIRED)
    except JWTError:
        raise AppException(ErrorCode.TOKEN_INVALID)

    if expected_type and payload.get("type") != expected_type:
        raise AppException(ErrorCode.TOKEN_INVALID)
    return payload
