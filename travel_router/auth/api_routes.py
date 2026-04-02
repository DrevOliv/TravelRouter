from fastapi import APIRouter, Request

from ..common.models import ActionResponse
from .models import AuthLoginBody, PasswordChangeBody
from .system_api import login, logout, update_password


public_api_router = APIRouter()
protected_api_router = APIRouter()


@public_api_router.post(
    "/auth/login",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log in",
    description="Authenticates the admin user and starts a session.",
)
async def api_auth_login(body: AuthLoginBody, request: Request):
    return login(request, body.password)


@public_api_router.post(
    "/auth/logout",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log out",
    description="Ends the current admin session.",
)
async def api_auth_logout(request: Request):
    return logout(request)


@protected_api_router.post(
    "/auth/password",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Change password",
    description="Changes the admin password for future logins.",
)
async def api_auth_password(body: PasswordChangeBody):
    return update_password(body.new_password, body.confirm_password)
