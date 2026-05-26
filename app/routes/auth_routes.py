from fastapi import APIRouter, Depends, Request, Response, status

from app.schemas.auth_schemas import (
    ForgotPasswordInput,
    ForgotPasswordResponse,
    LoginInput,
    RegisterInput,
    ResetPasswordInput,
    SessionInfo,
)
from app.services.auth_service import AuthService
from app.utils.cookies import REFRESH_COOKIE

auth_routes = APIRouter(prefix="/auth", tags=["auth"])


@auth_routes.post("/register", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterInput, response: Response, service: AuthService = Depends()):
    return await service.register(data, response)


@auth_routes.post("/login", response_model=SessionInfo)
async def login(data: LoginInput, response: Response, service: AuthService = Depends()):
    return await service.login(data, response)


@auth_routes.post("/refresh", response_model=SessionInfo)
async def refresh(request: Request, response: Response, service: AuthService = Depends()):
    token = request.cookies.get(REFRESH_COOKIE)
    return await service.refresh(token, response)


@auth_routes.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: AuthService = Depends()):
    token = request.cookies.get(REFRESH_COOKIE)
    await service.logout(token, response)


@auth_routes.get("/session", response_model=SessionInfo)
async def session(request: Request, service: AuthService = Depends()):
    return await service.get_session(request)


@auth_routes.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(data: ForgotPasswordInput, service: AuthService = Depends()):
    return await service.forgot_password(data)


@auth_routes.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: ResetPasswordInput, response: Response, service: AuthService = Depends()):
    await service.reset_password(data, response)
