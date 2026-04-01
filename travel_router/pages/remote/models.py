from pydantic import BaseModel, Field

from ...playback.models import PlaybackState


class TrackBody(BaseModel):
    track_id: int = Field(..., description="Track ID to activate.")


class SubtitleBody(BaseModel):
    track_id: str = Field("no", description='Subtitle track ID, or `"no"` to disable subtitles.')


class RemoteResponse(BaseModel):
    playback_state: PlaybackState
