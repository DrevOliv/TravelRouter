from fastapi import APIRouter, Request

from ...auth import AuthLoginBody, login, logout
from ...common.models import ActionResponse


api_router = APIRouter()


@api_router.post(
    "/auth/login",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log in",
    description="Authenticates the admin user and starts a session.",
)
async def api_auth_login(body: AuthLoginBody, request: Request):
    return login(request, body.password)


@api_router.post(
    "/auth/logout",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log out",
    description="Ends the current admin session.",
)
async def api_auth_logout(request: Request):
    return logout(request)
