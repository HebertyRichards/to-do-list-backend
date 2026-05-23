import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config.settings import get_settings
from app.errors import AppException, ErrorCode

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


def generate_jti() -> str:
    return secrets.token_hex(16)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def create_refresh_token(subject: str, jti: str, session_expires_at: datetime) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = min(
        now + timedelta(days=settings.refresh_token_days),
        session_expires_at,
    )
    payload = {
        "sub": subject,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "refresh",
        "sea": int(session_expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AppException(ErrorCode.TOKEN_EXPIRED)
    except JWTError:
        raise AppException(ErrorCode.TOKEN_INVALID)

    if expected_type and payload.get("type") != expected_type:
        raise AppException(ErrorCode.TOKEN_INVALID)
    return payload
