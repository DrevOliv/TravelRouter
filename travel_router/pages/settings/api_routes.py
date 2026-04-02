from fastapi import APIRouter

from .models import SettingsResponse
from .system_api import settings_payload


api_router = APIRouter()


@api_router.get(
    "/settings",
    response_model=SettingsResponse,
    tags=["settings"],
    summary="Get settings screen data",
    description="Returns configuration data for the Settings screen plus the current Jellyfin connection summary.",
)
async def api_settings():
    return settings_payload()
