from fastapi import APIRouter

from ..api_models import (
    ActionResponse,
    JellyfinSettingsBody,
    JellyfinStatusResponse,
    SettingsResponse,
    TailscaleSettingsBody,
    WifiSettingsBody,
)
from ..screen_data import action_payload, settings_payload
from ..system_api import (
    jellyfin_system_info,
    tailscale_disable_exit_node,
    tailscale_login,
    tailscale_up,
    update_settings,
)


router = APIRouter()


@router.get(
    "/settings",
    response_model=SettingsResponse,
    tags=["settings"],
    summary="Get settings screen data",
    description="Returns configuration data for Wi-Fi, Tailscale, and Jellyfin, plus available exit nodes and current Tailscale status.",
)
async def api_settings():
    return settings_payload()


@router.get(
    "/settings/jellyfin-status",
    response_model=JellyfinStatusResponse,
    tags=["settings"],
    summary="Check Jellyfin server status",
    description="Performs a live Jellyfin server check used by the Settings screen after it loads.",
)
async def api_settings_jellyfin_status():
    return jellyfin_system_info()


@router.post(
    "/settings/wifi",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Save Wi-Fi interface settings",
    description="Updates which interfaces are used for upstream Wi-Fi and the private access point.",
)
async def api_wifi_settings(body: WifiSettingsBody):
    update_settings("wifi", {"upstream_interface": body.upstream_interface.strip(), "ap_interface": body.ap_interface.strip()})
    return {"ok": True, "action": "wifi_settings", "message": "Wi-Fi interfaces saved", "detail": "", "link": "", "refresh": "settings"}


@router.post(
    "/settings/tailscale/login",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Start Tailscale login",
    description="Starts a Tailscale login flow and may return an authentication URL in the response.",
)
async def api_tailscale_login():
    result = tailscale_login()
    detail = "Open the login link to finish authentication." if result.get("auth_url") else result.get("stderr") or result.get("stdout") or ""
    return action_payload("tailscale_login", result, "Tailscale login started", "Tailscale login failed", detail=detail, refresh="settings")


@router.post(
    "/settings/tailscale",
    response_model=ActionResponse,
    tags=["settings"],
    summary="Update Tailscale exit node settings",
    description="Enables or disables exit node usage and applies the selected exit node.",
    responses={400: {"model": ActionResponse, "description": "No exit node was selected while exit node mode was enabled."}},
)
async def api_tailscale_settings(body: TailscaleSettingsBody):
    enabled = body.use_exit_node
    selected = body.exit_node.strip()
    if enabled and not selected:
        return {"ok": False, "action": "tailscale_settings", "message": "Choose an exit node first", "detail": "", "link": "", "refresh": None}

    if enabled:
        result = tailscale_up(selected)
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": selected})
    else:
        result = tailscale_disable_exit_node()
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": ""})

    return action_payload("tailscale_settings", result, "Tailscale settings saved", "Tailscale settings failed", refresh="settings")


@router.post(
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
