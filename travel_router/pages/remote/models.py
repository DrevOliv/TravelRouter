from pydantic import BaseModel, Field

from ...playback.models import PlaybackState


class RemoteResponse(BaseModel):
    playback_state: PlaybackState
