from pydantic import BaseModel, Field


class WifiConnectBody(BaseModel):
    ssid: str = Field(..., description="SSID of the upstream Wi-Fi network to connect to.")
    password: str = Field("", description="Password for the upstream Wi-Fi network. Leave empty for open networks.")


class WifiSettingsBody(BaseModel):
    upstream_interface: str = Field("wlan0", description="Interface used to join upstream Wi-Fi networks.")
    ap_interface: str = Field("wlan1", description="Interface used for the private access point.")


class ApSsidBody(BaseModel):
    ap_ssid: str = Field("PiTravelHub", description="SSID broadcast by the private travel-router access point.")


class ApPasswordBody(BaseModel):
    ap_password: str = Field("ChangeThisPassword", description="Password used for the private travel-router access point.")


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
