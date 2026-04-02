from pydantic import BaseModel, Field


class TrackBody(BaseModel):
    track_id: int = Field(..., description="Track ID to activate.")


class SubtitleBody(BaseModel):
    track_id: str = Field("no", description='Subtitle track ID, or `"no"` to disable subtitles.')


class PlaybackTrack(BaseModel):
    id: int = Field(..., description="Track ID reported by the playback backend.")
    lang: str = Field(..., description="Language code.")
    title: str = Field(..., description="Track display title.")
    selected: bool = Field(..., description="Whether this track is currently active.")


class PlaybackState(BaseModel):
    ok: bool = Field(..., description="Whether playback is currently active and readable.")
    error: str | None = Field(None, description="Error shown when no live playback session exists.")
    audio_tracks: list[PlaybackTrack] = Field(default_factory=list, description="Available audio tracks.")
    subtitle_tracks: list[PlaybackTrack] = Field(default_factory=list, description="Available subtitle tracks.")
    paused: bool | None = Field(None, description="Whether playback is currently paused.")
    time_pos: int = Field(0, description="Current playback position in seconds.")
    duration: int = Field(0, description="Current item duration in seconds.")
    active_item_id: str = Field("", description="Currently active Jellyfin item ID.")
    resume_seconds: int = Field(0, description="Saved resume position for the active item.")
