from fastapi import APIRouter, Query

from ..api_models import MediaPlayBody
from ..screen_data import action_payload, media_payload
from ..system_api import play_jellyfin_item


router = APIRouter()


@router.get("/media")
async def api_media(q: str = Query(default=""), parent_id: str = Query(default="")):
    search_term = q.strip() or None
    media_parent = parent_id.strip() or None
    return media_payload(search_term, media_parent)


@router.post("/media/play/{item_id}")
async def api_media_play(item_id: str, body: MediaPlayBody):
    result = play_jellyfin_item(item_id, resume=body.resume)
    return action_payload("media_play", result, "Playback started", "Playback failed", refresh="remote")
