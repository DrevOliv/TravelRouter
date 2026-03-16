from fastapi import APIRouter

from ..api_models import MetaResponse
from ..env import is_demo_mode


router = APIRouter()


@router.get(
    "/meta",
    response_model=MetaResponse,
    tags=["meta"],
    summary="Get app metadata",
    description="Returns environment-level metadata used by the frontend, such as whether demo mode is enabled.",
)
async def api_meta():
    return {"demo_mode": is_demo_mode()}
