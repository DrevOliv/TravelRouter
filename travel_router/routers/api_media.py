from fastapi import APIRouter, Query

from ..api_models import ActionResponse, MediaPlayBody, MediaResponse
from ..screen_data import action_payload, media_payload
from ..system_api import play_jellyfin_item


router = APIRouter()


@router.get(
    "/media",
    response_model=MediaResponse,
    tags=["media"],
    summary="Browse Jellyfin media",
    description="Returns the Media screen payload including the current library view or search results.",
)
async def api_media(q: str = Query(default=""), parent_id: str = Query(default="")):
    search_term = q.strip() or None
    media_parent = parent_id.strip() or None
    return media_payload(search_term, media_parent)


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
