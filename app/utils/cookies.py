from fastapi import Response
from app.config.settings import get_settings


ACCESS_COOKIE = "tdl_access"
REFRESH_COOKIE = "tdl_refresh"


def _cookie_kwargs() -> dict[str, object]:
    s = get_settings()
    kwargs: dict[str, object] = {
        "httponly": True,
        "secure": s.cookie_secure,
        "samesite": s.cookie_samesite,
        "path": "/",
    }
    if s.cookie_domain:
        kwargs["domain"] = s.cookie_domain
    return kwargs


def set_access_cookie(response: Response, token: str, max_age_seconds: int | None) -> None:
    kwargs = _cookie_kwargs()
    if max_age_seconds is not None:
        kwargs["max_age"] = max_age_seconds
    response.set_cookie(key=ACCESS_COOKIE, value=token, **kwargs)


def set_refresh_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=max_age_seconds,
        **_cookie_kwargs(),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, **_cookie_kwargs())
    response.delete_cookie(REFRESH_COOKIE, **_cookie_kwargs())
