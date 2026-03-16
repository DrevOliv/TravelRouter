from fastapi import APIRouter

from ..api_models import ActionResponse, HomeResponse, WifiConnectBody, WifiLiveResponse
from ..screen_data import action_payload, home_payload, wifi_live_payload
from ..system_api import connect_wifi, load_settings


router = APIRouter()


@router.get(
    "/home",
    response_model=HomeResponse,
    tags=["home"],
    summary="Get home dashboard data",
    description="Returns the Home screen payload including current upstream Wi-Fi, scanned networks, service states, and Wi-Fi interface settings.",
)
async def api_home():
    return home_payload()


@router.get(
    "/home/wifi-live",
    response_model=WifiLiveResponse,
    tags=["home"],
    summary="Get live Wi-Fi dashboard data",
    description="Returns only the current upstream Wi-Fi state and nearby scanned networks for lightweight Home screen polling.",
)
async def api_home_wifi_live():
    settings = load_settings()
    return wifi_live_payload(settings["wifi"]["upstream_interface"])


@router.post(
    "/wifi/connect",
    response_model=ActionResponse,
    tags=["home"],
    summary="Connect to upstream Wi-Fi",
    description="Attempts to connect the upstream Wi-Fi interface to the specified SSID.",
    responses={400: {"model": ActionResponse, "description": "Connection request was rejected or failed validation."}},
)
async def api_wifi_connect(body: WifiConnectBody):
    settings = load_settings()
    result = connect_wifi(settings["wifi"]["upstream_interface"], body.ssid.strip(), body.password.strip() or None)
    clean_ssid = body.ssid.strip() or "network"
    return action_payload("wifi_connect", result, f"Connected to {clean_ssid}", "Wi-Fi connection failed", refresh="home")
