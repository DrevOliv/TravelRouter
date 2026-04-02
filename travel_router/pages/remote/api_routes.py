from fastapi import APIRouter

from .models import RemoteResponse
from .system_api import remote_payload


api_router = APIRouter()


@api_router.get(
    "/remote",
    response_model=RemoteResponse,
    tags=["remote"],
    summary="Get remote playback state",
    description="Returns the current playback state, audio tracks, subtitle tracks, and resume information for the Remote screen.",
)
async def api_remote():
    return remote_payload()
