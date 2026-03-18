from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()
STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


def shell_response() -> FileResponse:
    return FileResponse(
        STATIC_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/")
async def index():
    return shell_response()


@router.get("/settings")
async def settings_page():
    return shell_response()


@router.get("/media")
async def media_page():
    return shell_response()


@router.get("/remote")
async def remote_page():
    return shell_response()
