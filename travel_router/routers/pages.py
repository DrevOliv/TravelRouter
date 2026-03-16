from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()
STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


@router.get("/")
async def index():
    return FileResponse(STATIC_INDEX)


@router.get("/settings")
async def settings_page():
    return FileResponse(STATIC_INDEX)


@router.get("/media")
async def media_page():
    return FileResponse(STATIC_INDEX)


@router.get("/remote")
async def remote_page():
    return FileResponse(STATIC_INDEX)
