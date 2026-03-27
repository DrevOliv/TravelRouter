from typing import Any

from pydantic import BaseModel, Field


class WifiConnectBody(BaseModel):
    ssid: str = Field(..., description="SSID of the upstream Wi-Fi network to connect to.")
    password: str = Field("", description="Password for the upstream Wi-Fi network. Leave empty for open networks.")


class AuthLoginBody(BaseModel):
    password: str = Field(..., description="Admin password used to log in to the control panel.")


class PasswordChangeBody(BaseModel):
    new_password: str = Field(..., description="New admin password.")
    confirm_password: str = Field(..., description="Repeat of the new admin password.")


class WifiSettingsBody(BaseModel):
    upstream_interface: str = Field("wlan0", description="Interface used to join upstream Wi-Fi networks.")
    ap_interface: str = Field("wlan1", description="Interface used for the private access point.")


class ApSsidBody(BaseModel):
    ap_ssid: str = Field("PiTravelHub", description="SSID broadcast by the private travel-router access point.")


class ApPasswordBody(BaseModel):
    ap_password: str = Field("ChangeThisPassword", description="Password used for the private travel-router access point.")


class TailscaleSettingsBody(BaseModel):
    use_exit_node: bool = Field(False, description="Enable routing traffic through a Tailscale exit node.")
    exit_node: str = Field("", description="Selected Tailscale exit node DNS name or IP.")


class ExitNodeSelectionBody(BaseModel):
    exit_node: str = Field("", description="Preferred Tailscale exit node DNS name or IP to save in settings.")


class ExitNodeToggleBody(BaseModel):
    enabled: bool = Field(..., description="Turn the saved exit node on or off.")


class JellyfinSettingsBody(BaseModel):
    server_url: str = Field("", description="Base URL of the Jellyfin server.")
    api_key: str = Field("", description="Jellyfin API key used for browsing and playback.")
    user_id: str = Field("", description="Jellyfin user ID for library access.")
    device_name: str = Field("Pi Travel Router", description="Client device name reported to Jellyfin.")


class MediaPlayBody(BaseModel):
    resume: bool = Field(True, description="Resume playback from the saved position if one exists.")


class TrackBody(BaseModel):
    track_id: int = Field(..., description="Track ID to activate.")


class SubtitleBody(BaseModel):
    track_id: str = Field("no", description='Subtitle track ID, or `"no"` to disable subtitles.')


class ActionResponse(BaseModel):
    ok: bool = Field(..., description="Whether the action succeeded.")
    action: str = Field(..., description="Frontend action identifier.")
    message: str = Field(..., description="Short human-readable outcome message.")
    detail: str = Field("", description="Longer detail or command output.")
    link: str = Field("", description="Optional follow-up URL, for example a Tailscale login link.")
    refresh: str | None = Field(None, description="Suggested screen to refresh after success.")


class MetaResponse(BaseModel):
    demo_mode: bool = Field(..., description="Whether the app is currently running in demo mode.")


class CommandResult(BaseModel):
    ok: bool = Field(..., description="Whether the underlying command or system call succeeded.")
    stdout: str = Field("", description="Standard output or equivalent response text.")
    stderr: str = Field("", description="Standard error or equivalent failure text.")
    command: str = Field("", description="Command string or synthetic operation label.")
    auth_url: str = Field("", description="Optional authentication URL returned by the command.")


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


class TransferConfig(BaseModel):
    host: str = Field("", description="TrueNAS SSH host or IP.")
    port: int = Field(22, description="TrueNAS SSH port.")
    username: str = Field("", description="TrueNAS SSH username.")
    auth_mode: str = Field("ssh_key", description="Authentication mode used for rsync over SSH.")
    password: str = Field("", description="SSH password when password auth is selected.")
    private_key_path: str = Field("", description="Path to the SSH private key on the Raspberry Pi when key auth is selected.")
    last_destination_path: str = Field("", description="Most recently used destination path for import jobs.")


class AppSettings(BaseModel):
    wifi: WifiConfig
    tailscale: TailscaleConfig
    jellyfin: JellyfinConfig
    transfer: TransferConfig


class ExitNode(BaseModel):
    value: str = Field(..., description="Node identifier sent back when selecting this exit node.")
    label: str = Field(..., description="Human-readable exit node label.")
    online: bool = Field(..., description="Whether the exit node is currently online.")


class JellyfinSummary(BaseModel):
    configured: bool = Field(..., description="Whether enough Jellyfin settings exist to attempt a connection.")
    ok: bool = Field(..., description="Whether the live Jellyfin check succeeded.")
    error: str = Field("", description="Status or error message shown before/after the live check.")


class HomeResponse(BaseModel):
    settings: AppSettings
    wifi_scan: CommandResult
    wifi_networks: list[WifiNetwork]
    wifi_current: WifiCurrent
    connected_devices: list[ConnectedDevice]
    tailscale: CommandResult
    tailscale_data: dict[str, Any] = Field(..., description="Parsed subset of `tailscale status --json` used on the Home screen.")
    exit_nodes: list[ExitNode]
    selected_exit_node: str = Field("", description="Currently selected exit node value.")
    exit_node_active: bool = Field(False, description="Whether exit-node routing is currently enabled.")
    services: dict[str, CommandResult]


class WifiLiveResponse(BaseModel):
    wifi_scan: CommandResult
    wifi_networks: list[WifiNetwork]
    wifi_current: WifiCurrent
    connected_devices: list[ConnectedDevice]


class SettingsResponse(BaseModel):
    settings: AppSettings
    tailscale: CommandResult
    tailscale_data: dict[str, Any] = Field(..., description="Parsed subset of `tailscale status --json`.")
    exit_nodes: list[ExitNode]
    selected_exit_node: str = Field("", description="Currently selected exit node value.")
    exit_node_active: bool = Field(False, description="Whether exit-node routing is currently enabled.")
    jellyfin: JellyfinSummary


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


class MediaResponse(BaseModel):
    search_term: str = Field("", description="Current search term.")
    parent_id: str = Field("", description="Current Jellyfin parent/library folder ID.")
    items: JellyfinItemsResponse


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


class RemoteResponse(BaseModel):
    playback_state: PlaybackState


class TransferSettingsBody(BaseModel):
    host: str = Field("", description="TrueNAS SSH host or IP.")
    port: int = Field(22, description="TrueNAS SSH port.")
    username: str = Field("", description="TrueNAS SSH username.")
    auth_mode: str = Field("ssh_key", description="Authentication mode: `ssh_key` or `password`.")
    password: str = Field("", description="SSH password when password auth is selected.")
    private_key_path: str = Field("", description="Path to an SSH private key on the Raspberry Pi when key auth is selected.")


class ImportMountBody(BaseModel):
    device_path: str = Field(..., description="Block-device path for the removable SD card partition, for example `/dev/mmcblk0p1`.")


class ImportUploadFolderBody(BaseModel):
    device_path: str = Field(..., description="Mounted or mountable removable SD card device path.")
    source_path: str = Field("", description="Folder path on the SD card, relative to the mounted card root.")
    destination_path: str = Field("", description="Full destination path on TrueNAS where the import should be uploaded.")


class ImportUploadFilesBody(BaseModel):
    device_path: str = Field(..., description="Mounted or mountable removable SD card device path.")
    source_path: str = Field("", description="Current source folder on the SD card, relative to the mounted card root.")
    selected_files: list[str] = Field(default_factory=list, description="Selected photo file names from the current source folder.")
    destination_path: str = Field("", description="Full destination path on TrueNAS where the selected photos should be uploaded.")


class ImportDevice(BaseModel):
    device_path: str = Field(..., description="Device path for the removable media partition.")
    name: str = Field("", description="Kernel device name, such as `mmcblk0p1`.")
    label: str = Field("", description="Human-readable device label or fallback name.")
    size: str = Field("", description="Reported size string from the system.")
    fstype: str = Field("", description="Filesystem type detected on the removable media.")
    mounted: bool = Field(False, description="Whether the partition is currently mounted.")
    mount_path: str = Field("", description="Current mount path if mounted.")


class ImportEntry(BaseModel):
    name: str = Field(..., description="File or directory name.")
    relative_path: str = Field("", description="Path relative to the mounted SD card root.")
    size_bytes: int = Field(0, description="Size in bytes for files, or 0 for directories.")


class ImportBreadcrumb(BaseModel):
    name: str = Field(..., description="Display label for this breadcrumb.")
    path: str = Field("", description="Relative path used when navigating back to this breadcrumb.")


class ImportBrowser(BaseModel):
    ok: bool = Field(..., description="Whether browsing the currently selected SD card path succeeded.")
    error: str = Field("", description="Error shown when the SD card is unavailable or the path is invalid.")
    current_path: str = Field("", description="Current browsed folder relative to the mounted SD card root.")
    directories: list[ImportEntry] = Field(default_factory=list, description="Child directories in the current folder.")
    files: list[ImportEntry] = Field(default_factory=list, description="Photo files in the current folder.")
    breadcrumbs: list[ImportBreadcrumb] = Field(default_factory=list, description="Breadcrumb navigation for the current folder.")


class TransferSummary(BaseModel):
    host: str = Field("", description="Configured TrueNAS SSH host.")
    port: int = Field(22, description="Configured TrueNAS SSH port.")
    username: str = Field("", description="Configured TrueNAS SSH username.")
    auth_mode: str = Field("ssh_key", description="Configured SSH auth mode.")
    private_key_path: str = Field("", description="Configured private key path when key auth is used.")
    last_destination_path: str = Field("", description="Most recently used destination path on the Import page.")
    configured: bool = Field(False, description="Whether enough connection data exists to run transfer jobs.")
    has_password: bool = Field(False, description="Whether a password is currently stored for password-auth mode.")


class ImportJob(BaseModel):
    id: str = Field(..., description="Unique upload job identifier.")
    kind: str = Field(..., description="Upload type: `folder` or `files`.")
    device_path: str = Field(..., description="Removable SD card device path used by this job.")
    source_path: str = Field("", description="Source folder on the SD card relative to the mounted root.")
    source_name: str = Field("", description="Human-readable source folder name.")
    selected_files: list[str] = Field(default_factory=list, description="Selected files for file-based jobs.")
    destination_path: str = Field("", description="Destination path on TrueNAS.")
    status: str = Field("", description="High-level job status such as queued, running, verifying, completed, failed, or cancelled.")
    phase: str = Field("", description="Current task phase shown in the UI.")
    total_files: int = Field(0, description="Total number of files in the job.")
    total_bytes: int = Field(0, description="Total bytes to upload for the job.")
    bytes_sent: int = Field(0, description="Bytes sent so far.")
    speed_bps: int = Field(0, description="Current transfer speed in bytes per second.")
    progress_percent: int = Field(0, description="Current progress percentage.")
    retries: int = Field(0, description="How many retry attempts have been used so far.")
    error: str = Field("", description="Latest error or waiting-state message for the job.")
    last_output: str = Field("", description="Latest rsync or worker progress line.")
    created_at: str = Field("", description="ISO timestamp when the job was created.")
    updated_at: str = Field("", description="ISO timestamp when the job last changed.")
    next_retry_at: str = Field("", description="ISO timestamp for the next retry attempt, if any.")
    cancel_requested: bool = Field(False, description="Whether cancellation has been requested for the job.")


class ImportResponse(BaseModel):
    transfer: TransferSummary
    devices: list[ImportDevice] = Field(default_factory=list, description="Detected removable SD card partitions.")
    selected_device: str = Field("", description="Currently selected SD card device path in the Import screen.")
    browser: ImportBrowser
    jobs: list[ImportJob] = Field(default_factory=list, description="Current upload queue and recent job history.")


class ImportJobsResponse(BaseModel):
    jobs: list[ImportJob] = Field(default_factory=list, description="Current upload queue and recent job history.")
