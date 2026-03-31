from typing import Any

from pydantic import BaseModel, Field


class ActionResponse(BaseModel):
    ok: bool = Field(..., description="Whether the action succeeded.")
    action: str = Field(..., description="Frontend action identifier.")
    message: str = Field(..., description="Short human-readable outcome message.")
    detail: str = Field("", description="Longer detail or command output.")
    link: str = Field("", description="Optional follow-up URL.")
    refresh: str | None = Field(None, description="Suggested screen to refresh after success.")


class CommandResult(BaseModel):
    ok: bool = Field(..., description="Whether the underlying command or system call succeeded.")
    stdout: str = Field("", description="Standard output or equivalent response text.")
    stderr: str = Field("", description="Standard error or equivalent failure text.")
    command: str = Field("", description="Command string or synthetic operation label.")
    auth_url: str = Field("", description="Optional URL extracted from the command output.")


class WifiNetwork(BaseModel):
    ssid: str = Field(..., description="Network SSID.")
    signal: int = Field(..., description="Signal strength percentage.")
    security: str = Field(..., description="Security mode reported by NetworkManager.")
    is_open: bool = Field(..., description="Whether the network appears to be open.")


class WifiCurrent(BaseModel):
    ok: bool = Field(..., description="Whether reading Wi-Fi state succeeded.")
    connected: bool = Field(False, description="Whether the Pi is currently connected to an upstream Wi-Fi network.")
    ssid: str = Field("", description="Current upstream SSID.")
    signal: str = Field("", description="Current upstream signal percentage as a string.")
    security: str = Field("", description="Current upstream security mode.")
    error: str | None = Field(None, description="Error message when Wi-Fi state could not be read.")


class ConnectedDevice(BaseModel):
    name: str = Field("", description="Best available device label, usually a hostname or a friendly fallback.")
    ip: str = Field("", description="IPv4 or IPv6 address seen on the private AP.")
    mac: str = Field("", description="MAC address if available.")
    state: str = Field("", description="Neighbor or lease state for the connected device.")


class WifiConfig(BaseModel):
    upstream_interface: str = Field(..., description="Interface used for upstream Wi-Fi.")
    ap_interface: str = Field(..., description="Interface used for the private access point.")
    ap_ssid: str = Field(..., description="SSID broadcast by the private access point.")
    ap_password: str = Field(..., description="Password used by the private access point.")


class TailscaleConfig(BaseModel):
    advertise_exit_node: bool = Field(False, description="Legacy config flag; not used by the current UI.")
    current_exit_node: str = Field("", description="Currently selected Tailscale exit node.")
    exit_node_enabled: bool = Field(False, description="Whether the saved exit node should be actively used.")


class JellyfinConfig(BaseModel):
    server_url: str = Field("", description="Configured Jellyfin server URL.")
    api_key: str = Field("", description="Configured Jellyfin API key.")
    user_id: str = Field("", description="Configured Jellyfin user ID.")
    device_name: str = Field("", description="Configured Jellyfin device name.")


class AppSettings(BaseModel):
    wifi: WifiConfig
    tailscale: TailscaleConfig
    jellyfin: JellyfinConfig


class ExitNode(BaseModel):
    value: str = Field(..., description="Node identifier sent back when selecting this exit node.")
    label: str = Field(..., description="Human-readable exit node label.")
    online: bool = Field(..., description="Whether the exit node is currently online.")


class JellyfinSummary(BaseModel):
    configured: bool = Field(..., description="Whether enough Jellyfin settings exist to attempt a connection.")
    ok: bool = Field(..., description="Whether the live Jellyfin check succeeded.")
    error: str = Field("", description="Status or error message shown before/after the live check.")


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


class JellyfinStatusResponse(BaseModel):
    ok: bool = Field(..., description="Whether the Jellyfin status request succeeded.")
    configured: bool = Field(..., description="Whether the Jellyfin server settings are populated.")
    reachable: bool = Field(..., description="Whether the Jellyfin server was reachable.")
    error: str | None = Field(None, description="Error message when the server is unavailable.")
    data: dict[str, Any] | None = Field(None, description="Raw Jellyfin system info response.")
