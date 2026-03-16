from pydantic import BaseModel


class WifiConnectBody(BaseModel):
    ssid: str
    password: str = ""


class WifiSettingsBody(BaseModel):
    upstream_interface: str = "wlan0"
    ap_interface: str = "wlan1"


class TailscaleSettingsBody(BaseModel):
    use_exit_node: bool = False
    exit_node: str = ""


class JellyfinSettingsBody(BaseModel):
    server_url: str = ""
    api_key: str = ""
    user_id: str = ""
    device_name: str = "Pi Travel Router"


class MediaPlayBody(BaseModel):
    resume: bool = True


class TrackBody(BaseModel):
    track_id: int


class SubtitleBody(BaseModel):
    track_id: str = "no"
