from fastapi import APIRouter

from ..common.models import ActionResponse
from ..common.responses import action_payload
from ..playback import play_jellyfin_item
from ..settings_store import update_settings
from .models import JellyfinSettingsBody, JellyfinStatusResponse, MediaPlayBody
from .system_api import jellyfin_system_info


router = APIRouter()


@router.get(
    "/settings/jellyfin-status",
    response_model=JellyfinStatusResponse,
    tags=["media"],
    summary="Check Jellyfin server status",
    description="Performs a live Jellyfin server check used by the Settings screen after it loads.",
)
async def api_settings_jellyfin_status():
    return jellyfin_system_info()


@router.post(
    "/settings/jellyfin",
    response_model=ActionResponse,
    tags=["media"],
    summary="Save Jellyfin settings",
    description="Stores the Jellyfin server connection details used by the Media and Remote screens.",
)
async def api_jellyfin_settings(body: JellyfinSettingsBody):
    update_settings(
        "jellyfin",
        {
            "server_url": body.server_url.strip(),
            "api_key": body.api_key.strip(),
            "user_id": body.user_id.strip(),
            "device_name": body.device_name.strip(),
        },
    )
    return {"ok": True, "action": "jellyfin_settings", "message": "Jellyfin settings saved", "detail": "", "link": "", "refresh": "settings"}


@router.post(
    "/media/play/{item_id}",
    response_model=ActionResponse,
    tags=["media"],
    summary="Start playback",
    description="Starts Jellyfin playback for the selected item on the Raspberry Pi output.",
)
async def api_media_play(item_id: str, body: MediaPlayBody):
    result = play_jellyfin_item(item_id, resume=body.resume)
    return action_payload("media_play", result, "Playback started", "Playback failed", refresh="remote")
