from fastapi import APIRouter, Response

from ..common.models import ActionResponse
from ..common.responses import action_payload
from ..settings_store import load_settings, update_settings
from .models import ApPasswordBody, ApSsidBody, WifiConnectBody, WifiSettingsBody
from .system_api import apply_ap_password, apply_ap_ssid, connect_wifi, disconnect_wifi, wifi_qr_svg


router = APIRouter()


@router.get(
    "/home/ap-qr",
    tags=["wifi"],
    summary="Get access-point Wi-Fi QR code",
    description="Returns an SVG QR code for joining the private travel-router Wi-Fi network.",
)
async def api_home_ap_qr():
    settings = load_settings()
    svg = wifi_qr_svg(settings["wifi"]["ap_ssid"], settings["wifi"]["ap_password"])
    return Response(content=svg, media_type="image/svg+xml")


@router.post(
    "/wifi/connect",
    response_model=ActionResponse,
    tags=["wifi"],
    summary="Connect to upstream Wi-Fi",
    description="Attempts to connect the upstream Wi-Fi interface to the specified SSID.",
    responses={400: {"model": ActionResponse, "description": "Connection request was rejected or failed validation."}},
)
async def api_wifi_connect(body: WifiConnectBody):
    settings = load_settings()
    result = connect_wifi(settings["wifi"]["upstream_interface"], body.ssid.strip(), body.password.strip() or None)
    clean_ssid = body.ssid.strip() or "network"
    return action_payload("wifi_connect", result, f"Connected to {clean_ssid}", "Wi-Fi connection failed", refresh="home")


@router.post(
    "/wifi/disconnect",
    response_model=ActionResponse,
    tags=["wifi"],
    summary="Disconnect upstream Wi-Fi",
    description="Disconnects the upstream Wi-Fi interface from its current network.",
)
async def api_wifi_disconnect():
    settings = load_settings()
    result = disconnect_wifi(settings["wifi"]["upstream_interface"])
    return action_payload("wifi_disconnect", result, "Wi-Fi disconnected", "Wi-Fi disconnect failed", refresh="home")


@router.post(
    "/settings/wifi",
    response_model=ActionResponse,
    tags=["wifi"],
    summary="Save Wi-Fi interface settings",
    description="Updates which interfaces are used for upstream Wi-Fi and the private access point.",
)
async def api_wifi_settings(body: WifiSettingsBody):
    update_settings(
        "wifi",
        {
            "upstream_interface": body.upstream_interface.strip(),
            "ap_interface": body.ap_interface.strip(),
        },
    )
    return {"ok": True, "action": "wifi_settings", "message": "Wi-Fi interfaces saved", "detail": "", "link": "", "refresh": "settings"}


@router.post(
    "/settings/wifi/ap-ssid",
    response_model=ActionResponse,
    tags=["wifi"],
    summary="Save private Wi-Fi SSID",
    description="Updates the private AP SSID on the existing NetworkManager access-point profile.",
)
async def api_wifi_ap_ssid(body: ApSsidBody):
    ap_ssid = body.ap_ssid.strip()
    if not ap_ssid:
        return {"ok": False, "action": "wifi_ap_ssid", "message": "SSID cannot be empty", "detail": "", "link": "", "refresh": None}
    result = apply_ap_ssid(ap_ssid)
    return action_payload("wifi_ap_ssid", result, "Private Wi-Fi SSID saved", "Private Wi-Fi SSID failed", refresh="settings")


@router.post(
    "/settings/wifi/ap-password",
    response_model=ActionResponse,
    tags=["wifi"],
    summary="Save private Wi-Fi password",
    description="Updates the private AP password on the existing NetworkManager access-point profile.",
)
async def api_wifi_ap_password(body: ApPasswordBody):
    result = apply_ap_password(body.ap_password.strip())
    return action_payload("wifi_ap_password", result, "Private Wi-Fi password saved", "Private Wi-Fi password failed", refresh="settings")
