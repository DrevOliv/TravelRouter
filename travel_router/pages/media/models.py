from pydantic import BaseModel, Field

from ...media.models import JellyfinItemsResponse


class MediaPlayBody(BaseModel):
    resume: bool = Field(True, description="Resume playback from the saved position if one exists.")


class MediaResponse(BaseModel):
    search_term: str = Field("", description="Current search term.")
    parent_id: str = Field("", description="Current Jellyfin parent/library folder ID.")
    items: JellyfinItemsResponse
