from fastapi import APIRouter

from ...auth import PasswordChangeBody, update_password
from ...common.models import ActionResponse
from ...common.responses import action_payload
from ...media import jellyfin_system_info
from ...media.models import JellyfinStatusResponse
from ...settings_store import load_settings, update_settings
from ...tailscale import resolve_saved_exit_node, tailscale_disable_exit_node, tailscale_up
from ...wifi import apply_ap_password, apply_ap_ssid
from .models import (
    ApPasswordBody,
    ApSsidBody,
    ExitNodeSelectionBody,
    ExitNodeToggleBody,
    JellyfinSettingsBody,
    SettingsResponse,
    WifiSettingsBody,
)
from .system_api import settings_payload


api_router = APIRouter()


@api_router.get(
    "/settings",
    response_model=SettingsResponse,
    tags=["settings"],
    summary="Get settings screen data",
    description="Returns configuration data for the Settings screen plus the current Jellyfin connection summary.",
)
async def api_settings():
    return settings_payload()


@api_router.get(
    "/settings/jellyfin-status",
    response_model=JellyfinStatusResponse,
    tags=["settings"],
    summary="Check Jellyfin server status",
    description="Performs a live Jellyfin server check used by the Settings screen after it loads.",
)
async def api_settings_jellyfin_status():
    return jellyfin_system_info()


@api_router.post(
    "/settings/wifi",
    response_model=ActionResponse,
    tags=["settings"],
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


@api_router.post(
    "/settings/wifi/ap-ssid",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Save private Wi-Fi SSID",
    description="Updates the private AP SSID on the existing NetworkManager access-point profile.",
)
async def api_wifi_ap_ssid(body: ApSsidBody):
    ap_ssid = body.ap_ssid.strip()
    if not ap_ssid:
        return {"ok": False, "action": "wifi_ap_ssid", "message": "SSID cannot be empty", "detail": "", "link": "", "refresh": None}
    result = apply_ap_ssid(ap_ssid)
    return action_payload("wifi_ap_ssid", result, "Private Wi-Fi SSID saved", "Private Wi-Fi SSID failed", refresh="settings")


@api_router.post(
    "/settings/wifi/ap-password",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Save private Wi-Fi password",
    description="Updates the private AP password on the existing NetworkManager access-point profile.",
)
async def api_wifi_ap_password(body: ApPasswordBody):
    result = apply_ap_password(body.ap_password.strip())
    return action_payload("wifi_ap_password", result, "Private Wi-Fi password saved", "Private Wi-Fi password failed", refresh="settings")


@api_router.post(
    "/settings/tailscale/selection",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Save preferred exit node",
    description="Saves the preferred Tailscale exit node in app settings without turning it on immediately.",
    responses={400: {"model": ActionResponse, "description": "No exit node was provided."}},
)
async def api_tailscale_selection(body: ExitNodeSelectionBody):
    selected = body.exit_node.strip()
    if not selected:
        return {"ok": False, "action": "tailscale_selection", "message": "Choose an exit node first", "detail": "", "link": "", "refresh": None}

    update_settings("tailscale", {"current_exit_node": selected, "exit_node_enabled": False})
    return {"ok": True, "action": "tailscale_selection", "message": "Exit node saved", "detail": "", "link": "", "refresh": "home"}


@api_router.post(
    "/settings/tailscale/toggle",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Toggle preferred exit node",
    description="Turns the saved exit node on or off without changing which node is saved.",
    responses={400: {"model": ActionResponse, "description": "No preferred exit node is saved yet."}},
)
async def api_tailscale_toggle(body: ExitNodeToggleBody):
    settings = load_settings()
    selected = resolve_saved_exit_node(settings["tailscale"]["current_exit_node"])
    if body.enabled:
        if not selected:
            return {"ok": False, "action": "tailscale_toggle", "message": "Save an exit node first", "detail": "", "link": "", "refresh": None}
        result = tailscale_up(selected)
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": selected, "exit_node_enabled": True})
    else:
        result = tailscale_disable_exit_node()
        if result["ok"]:
            update_settings("tailscale", {"exit_node_enabled": False})

    return action_payload("tailscale_toggle", result, "Exit node updated", "Exit node update failed", refresh="home")


@api_router.post(
    "/settings/jellyfin",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Save Jellyfin settings",
    description="Stores the Jellyfin server connection details used by the Media and Remote screens.",
)
async def api_jellyfin_settings(body: JellyfinSettingsBody):
    update_settings(
        "jellyfin",
        {
            "server_url": body.server_url.strip(),
            "api_key": body.api_key.strip(),
            "user_id": body.user_id.strip(),
            "device_name": body.device_name.strip(),
        },
    )
    return {"ok": True, "action": "jellyfin_settings", "message": "Jellyfin settings saved", "detail": "", "link": "", "refresh": "settings"}


@api_router.post(
    "/auth/password",
    response_model=ActionResponse,
    tags=["auth"],
    summary="Change password",
    description="Changes the admin password for future logins.",
)
async def api_auth_password(body: PasswordChangeBody):
    return update_password(body.new_password, body.confirm_password)
