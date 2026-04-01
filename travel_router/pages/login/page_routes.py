from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ...auth import is_authenticated
from ..system_api import login_response


page_router = APIRouter()


@page_router.get("/login")
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=303)
    return login_response()
