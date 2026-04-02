from fastapi import APIRouter

from ..common.models import ActionResponse
from ..common.responses import action_payload
from ..settings_store import load_settings, update_settings
from .models import ExitNodeSelectionBody, ExitNodeToggleBody
from .system_api import resolve_saved_exit_node, tailscale_disable_exit_node, tailscale_up


router = APIRouter()


@router.post(
    "/settings/tailscale/selection",
    response_model=ActionResponse,
    tags=["tailscale"],
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


@router.post(
    "/settings/tailscale/toggle",
    response_model=ActionResponse,
    tags=["tailscale"],
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
