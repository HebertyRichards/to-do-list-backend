from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.models import User
from app.schemas.auth_schemas import (
    CurrentUser,
    DeleteAccountInput,
    ForgotPasswordInput,
    ForgotPasswordResponse,
    LoginInput,
    RegisterInput,
    ResendVerificationInput,
    ResetPasswordInput,
    SessionInfo,
    VerifyEmailInput,
)
from app.services.auth_service import AuthService
from app.utils.cookies import REFRESH_COOKIE
from app.utils.dependencies import get_current_user

auth_routes = APIRouter(prefix="/auth", tags=["auth"])


@auth_routes.post("/register", response_model=CurrentUser, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterInput,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(),
):
    return await service.register(data, background_tasks)


@auth_routes.post("/verify-email", response_model=SessionInfo)
async def verify_email(data: VerifyEmailInput, response: Response, service: AuthService = Depends()):
    return await service.verify_email(data, response)


@auth_routes.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
async def resend_verification(
    data: ResendVerificationInput,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(),
):
    await service.resend_verification(data, background_tasks)


@auth_routes.post("/login", response_model=SessionInfo)
async def login(data: LoginInput, response: Response, service: AuthService = Depends()):
    return await service.login(data, response)


@auth_routes.post("/refresh", response_model=SessionInfo)
async def refresh(request: Request, response: Response, service: AuthService = Depends()):
    token = request.cookies.get(REFRESH_COOKIE)
    return await service.refresh(token, response)


@auth_routes.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: AuthService = Depends()):
    await service.logout(request, response)


@auth_routes.get("/session", response_model=SessionInfo)
async def session(request: Request, service: AuthService = Depends()):
    return await service.get_session(request)


@auth_routes.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    data: ForgotPasswordInput,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(),
):
    return await service.forgot_password(data, background_tasks)


@auth_routes.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(data: ResetPasswordInput, response: Response, service: AuthService = Depends()):
    await service.reset_password(data, response)


@auth_routes.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountInput,
    response: Response,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(),
):
    await service.delete_account(user, data, response)
