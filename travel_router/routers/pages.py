from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..auth import is_authenticated


router = APIRouter()
STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"
LOGIN_INDEX = Path(__file__).resolve().parent.parent / "static" / "login.html"


def shell_response() -> FileResponse:
    return FileResponse(
        STATIC_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def login_response() -> FileResponse:
    return FileResponse(
        LOGIN_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/")
async def index(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return shell_response()


@router.get("/settings")
async def settings_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return shell_response()


@router.get("/media")
async def media_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return shell_response()


@router.get("/remote")
async def remote_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return shell_response()


@router.get("/login")
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=303)
    return login_response()
