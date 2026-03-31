from pydantic import BaseModel, Field

from ..common.models import AppSettings, JellyfinStatusResponse, JellyfinSummary


class WifiSettingsBody(BaseModel):
    upstream_interface: str = Field("wlan0", description="Interface used to join upstream Wi-Fi networks.")
    ap_interface: str = Field("wlan1", description="Interface used for the private access point.")


class ApSsidBody(BaseModel):
    ap_ssid: str = Field("PiTravelHub", description="SSID broadcast by the private travel-router access point.")


class ApPasswordBody(BaseModel):
    ap_password: str = Field("ChangeThisPassword", description="Password used for the private travel-router access point.")


class ExitNodeSelectionBody(BaseModel):
    exit_node: str = Field("", description="Preferred Tailscale exit node DNS name or IP to save in settings.")


class ExitNodeToggleBody(BaseModel):
    enabled: bool = Field(..., description="Turn the saved exit node on or off.")


class JellyfinSettingsBody(BaseModel):
    server_url: str = Field("", description="Base URL of the Jellyfin server.")
    api_key: str = Field("", description="Jellyfin API key used for browsing and playback.")
    user_id: str = Field("", description="Jellyfin user ID for library access.")
    device_name: str = Field("Pi Travel Router", description="Client device name reported to Jellyfin.")


class SettingsResponse(BaseModel):
    settings: AppSettings
    jellyfin: JellyfinSummary
