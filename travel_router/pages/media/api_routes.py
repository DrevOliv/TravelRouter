from fastapi import APIRouter, Query

from ...media import media_payload
from .models import MediaResponse


api_router = APIRouter()


@api_router.get(
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
