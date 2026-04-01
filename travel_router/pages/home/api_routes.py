from fastapi import APIRouter, Response

from ...common.models import ActionResponse
from ...common.responses import action_payload
from ...settings_store import load_settings
from ...wifi import connect_wifi, disconnect_wifi, wifi_qr_svg
from .models import HomeResponse, WifiConnectBody, WifiLiveResponse
from .system_api import home_payload, wifi_live_payload


api_router = APIRouter()


@api_router.get(
    "/home",
    response_model=HomeResponse,
    tags=["home"],
    summary="Get home dashboard data",
    description="Returns the Home screen payload including current upstream Wi-Fi, scanned networks, connected devices, exit-node choices, and Wi-Fi interface settings.",
)
async def api_home():
    return home_payload()


@api_router.get(
    "/home/wifi-live",
    response_model=WifiLiveResponse,
    tags=["home"],
    summary="Get live Wi-Fi dashboard data",
    description="Returns only the current upstream Wi-Fi state and nearby scanned networks for lightweight Home screen polling.",
)
async def api_home_wifi_live():
    settings = load_settings()
    return wifi_live_payload(settings["wifi"]["upstream_interface"])


@api_router.get(
    "/home/ap-qr",
    tags=["home"],
    summary="Get access-point Wi-Fi QR code",
    description="Returns an SVG QR code for joining the private travel-router Wi-Fi network.",
)
async def api_home_ap_qr():
    settings = load_settings()
    svg = wifi_qr_svg(settings["wifi"]["ap_ssid"], settings["wifi"]["ap_password"])
    return Response(content=svg, media_type="image/svg+xml")


@api_router.post(
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


@api_router.post(
    "/wifi/disconnect",
    response_model=ActionResponse,
    tags=["home"],
    summary="Disconnect upstream Wi-Fi",
    description="Disconnects the upstream Wi-Fi interface from its current network.",
)
async def api_wifi_disconnect():
    settings = load_settings()
    result = disconnect_wifi(settings["wifi"]["upstream_interface"])
    return action_payload("wifi_disconnect", result, "Wi-Fi disconnected", "Wi-Fi disconnect failed", refresh="home")
