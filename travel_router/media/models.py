from typing import Any

from pydantic import BaseModel, Field


class JellyfinConfig(BaseModel):
    server_url: str = Field("", description="Configured Jellyfin server URL.")
    api_key: str = Field("", description="Configured Jellyfin API key.")
    user_id: str = Field("", description="Configured Jellyfin user ID.")
    device_name: str = Field("", description="Configured Jellyfin device name.")


class JellyfinSettingsBody(BaseModel):
    server_url: str = Field("", description="Base URL of the Jellyfin server.")
    api_key: str = Field("", description="Jellyfin API key used for browsing and playback.")
    user_id: str = Field("", description="Jellyfin user ID for library access.")
    device_name: str = Field("Pi Travel Router", description="Client device name reported to Jellyfin.")


class MediaPlayBody(BaseModel):
    resume: bool = Field(True, description="Resume playback from the saved position if one exists.")


class JellyfinSummary(BaseModel):
    configured: bool = Field(..., description="Whether enough Jellyfin settings exist to attempt a connection.")
    ok: bool = Field(..., description="Whether the live Jellyfin check succeeded.")
    error: str = Field("", description="Status or error message shown before/after the live check.")


class JellyfinStatusResponse(BaseModel):
    ok: bool = Field(..., description="Whether the Jellyfin status request succeeded.")
    configured: bool = Field(..., description="Whether the Jellyfin server settings are populated.")
    reachable: bool = Field(..., description="Whether the Jellyfin server was reachable.")
    error: str | None = Field(None, description="Error message when the server is unavailable.")
    data: dict[str, Any] | None = Field(None, description="Raw Jellyfin system info response.")


class JellyfinUserData(BaseModel):
    PlaybackPositionTicks: int | None = Field(None, description="Resume position reported by Jellyfin, in ticks.")


class JellyfinItem(BaseModel):
    Id: str = Field(..., description="Jellyfin item ID.")
    Name: str = Field(..., description="Display name.")
    Type: str = Field(..., description="Jellyfin item type such as Movie, Series, or BoxSet.")
    UserData: JellyfinUserData | None = Field(None, description="Per-user playback metadata.")
    LocalResumeSeconds: int = Field(0, description="Locally saved resume position in seconds.")
    image_url: str = Field(..., description="Primary artwork URL.")


class JellyfinItemsData(BaseModel):
    Items: list[JellyfinItem] = Field(default_factory=list, description="Returned Jellyfin items.")


class JellyfinItemsResponse(BaseModel):
    ok: bool = Field(..., description="Whether the Jellyfin browse request succeeded.")
    configured: bool | None = Field(None, description="Whether Jellyfin is configured enough to attempt the request.")
    reachable: bool | None = Field(None, description="Whether the Jellyfin server was reachable.")
    error: str | None = Field(None, description="Error message when the request fails.")
    data: JellyfinItemsData | None = Field(None, description="Item collection when the request succeeds.")
