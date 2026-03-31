from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..auth_core import is_authenticated
from .system_api import login_response, shell_response


router = APIRouter()


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
