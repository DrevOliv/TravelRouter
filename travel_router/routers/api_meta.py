from fastapi import APIRouter

from ..env import is_demo_mode


router = APIRouter()


@router.get("/meta")
async def api_meta():
    return {"demo_mode": is_demo_mode()}
