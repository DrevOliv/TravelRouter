from fastapi import APIRouter, Request

from ..api_models import ActionResponse, AuthLoginBody, PasswordChangeBody
from ..auth import SESSION_KEY, change_password, verify_password


router = APIRouter()


@router.post(
    "/auth/login",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log in",
    description="Authenticates the admin user and starts a session.",
)
async def api_auth_login(body: AuthLoginBody, request: Request):
    if not verify_password(body.password):
        return {"ok": False, "action": "auth_login", "message": "Login failed", "detail": "Incorrect password.", "link": "", "refresh": None}

    request.session[SESSION_KEY] = True
    return {"ok": True, "action": "auth_login", "message": "Logged in", "detail": "", "link": "", "refresh": None}


@router.post(
    "/auth/logout",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Log out",
    description="Ends the current admin session.",
)
async def api_auth_logout(request: Request):
    request.session.clear()
    return {"ok": True, "action": "auth_logout", "message": "Logged out", "detail": "", "link": "", "refresh": None}


@router.post(
    "/auth/password",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Change password",
    description="Changes the admin password for future logins.",
)
async def api_auth_password(body: PasswordChangeBody):
    if body.new_password != body.confirm_password:
        return {"ok": False, "action": "auth_password", "message": "Password change failed", "detail": "New passwords do not match.", "link": "", "refresh": None}

    ok, detail = change_password(body.new_password)
    return {
        "ok": ok,
        "action": "auth_password",
        "message": "Password updated" if ok else "Password change failed",
        "detail": detail if not ok else "",
        "link": "",
        "refresh": "settings" if ok else None,
    }
