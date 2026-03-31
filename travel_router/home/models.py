from pydantic import BaseModel, Field

from ..common.models import AppSettings, CommandResult, ConnectedDevice, ExitNode, WifiCurrent, WifiNetwork


class WifiConnectBody(BaseModel):
    ssid: str = Field(..., description="SSID of the upstream Wi-Fi network to connect to.")
    password: str = Field("", description="Password for the upstream Wi-Fi network. Leave empty for open networks.")


class HomeResponse(BaseModel):
    settings: AppSettings
    wifi_scan: CommandResult
    wifi_networks: list[WifiNetwork]
    wifi_current: WifiCurrent
    connected_devices: list[ConnectedDevice]
    exit_nodes: list[ExitNode]
    selected_exit_node: str = Field("", description="Currently selected exit node value.")
    exit_node_active: bool = Field(False, description="Whether exit-node routing is currently enabled.")


class WifiLiveResponse(BaseModel):
    wifi_scan: CommandResult
    wifi_networks: list[WifiNetwork]
    wifi_current: WifiCurrent
    connected_devices: list[ConnectedDevice]
