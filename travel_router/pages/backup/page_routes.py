from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ...auth import is_authenticated
from ..system_api import shell_response


page_router = APIRouter()


@page_router.get("/backup")
async def backup_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return shell_response()
