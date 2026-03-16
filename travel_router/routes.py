import json

from flask import Blueprint, redirect, render_template, request, session, url_for

from .system_api import (
    all_resume_seconds,
    connect_wifi,
    current_wifi,
    get_playback_state,
    jellyfin_items,
    jellyfin_image_url,
    jellyfin_system_info,
    jellyfin_views,
    load_settings,
    pause_playback,
    play_jellyfin_item,
    scan_wifi,
    seek_relative,
    set_audio_track,
    set_subtitle_track,
    stop_playback,
    systemctl_status,
    tailscale_disable_exit_node,
    tailscale_login,
    tailscale_down,
    tailscale_status,
    tailscale_up,
    update_settings,
)


bp = Blueprint("router", __name__)


def remember_feedback(action: str, ok: bool, message: str, detail: str = "", link: str = "") -> None:
    session["ui_feedback"] = {
        "action": action,
        "ok": ok,
        "message": message,
        "detail": detail,
        "link": link,
    }


def wants_json() -> bool:
    accept = request.headers.get("Accept", "")
    return "application/json" in accept or request.headers.get("X-Requested-With") == "fetch"


def json_or_redirect(action: str, ok: bool, message: str, detail: str = "", link: str = "", default_endpoint: str = "router.index"):
    if wants_json():
        return {
            "ok": ok,
            "action": action,
            "message": message,
            "detail": detail,
            "link": link,
        }
    remember_feedback(action, ok, message, detail, link)
    return redirect_back(default_endpoint)


def redirect_back(default_endpoint: str):
    target = request.referrer
    if target:
        return redirect(target)
    return redirect(url_for(default_endpoint))


def parse_tailscale_json(result: dict) -> dict:
    if not result["ok"] or not result["stdout"]:
        return {}
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {}


def parse_exit_nodes(tailscale_data: dict) -> list[dict]:
    peers = tailscale_data.get("Peer") or {}
    nodes = []
    for peer_id, peer in peers.items():
        if not peer.get("ExitNodeOption"):
            continue
        tailscale_ips = peer.get("TailscaleIPs") or []
        node_value = peer.get("DNSName") or (tailscale_ips[0] if tailscale_ips else peer_id)
        nodes.append(
            {
                "value": node_value.rstrip("."),
                "label": (peer.get("HostName") or peer.get("DNSName") or node_value).rstrip("."),
                "online": bool(peer.get("Online")),
            }
        )
    nodes.sort(key=lambda node: node["label"].lower())
    return nodes


def current_exit_node_value(tailscale_data: dict, settings: dict) -> str:
    selected = tailscale_data.get("Self", {}).get("ExitNodeStatus") or {}
    if selected.get("ID"):
        peer = (tailscale_data.get("Peer") or {}).get(selected["ID"], {})
        return (peer.get("DNSName") or peer.get("HostName") or settings["tailscale"]["current_exit_node"]).rstrip(".")
    return settings["tailscale"]["current_exit_node"]


@bp.route("/")
def index():
    settings = load_settings()
    wifi_scan = scan_wifi(settings["wifi"]["upstream_interface"])
    wifi_current = current_wifi(settings["wifi"]["upstream_interface"])
    services = {
        "hostapd": systemctl_status("hostapd"),
        "dnsmasq": systemctl_status("dnsmasq"),
        "tailscaled": systemctl_status("tailscaled"),
    }
    return render_template(
        "index.html",
        settings=settings,
        wifi_scan=wifi_scan,
        wifi_current=wifi_current,
        services=services,
    )


@bp.route("/wifi/connect", methods=["POST"])
def wifi_connect():
    settings = load_settings()
    result = connect_wifi(
        settings["wifi"]["upstream_interface"],
        request.form.get("ssid", "").strip(),
        request.form.get("password", "").strip() or None,
    )
    ssid = request.form.get("ssid", "").strip() or "network"
    return json_or_redirect(
        "wifi_connect",
        result["ok"],
        f"Connected to {ssid}" if result["ok"] else "Wi-Fi connection failed",
        result["stderr"] or result["stdout"],
        default_endpoint="router.index",
    )


@bp.route("/settings/wifi", methods=["POST"])
def wifi_settings():
    update_settings(
        "wifi",
        {
            "upstream_interface": request.form.get("upstream_interface", "wlan0").strip(),
            "ap_interface": request.form.get("ap_interface", "wlan1").strip(),
        },
    )
    return json_or_redirect("wifi_settings", True, "Wi-Fi interfaces saved", default_endpoint="router.settings_page")


@bp.route("/tailscale/up", methods=["POST"])
def vpn_up():
    exit_node = request.form.get("exit_node", "").strip() or None
    result = tailscale_up(exit_node)
    if exit_node:
        update_settings("tailscale", {"current_exit_node": exit_node})
    return json_or_redirect(
        "tailscale_up",
        result["ok"],
        "Tailscale updated" if result["ok"] else "Tailscale update failed",
        result["stderr"] or result["stdout"],
        default_endpoint="router.settings_page",
    )


@bp.route("/tailscale/down", methods=["POST"])
def vpn_down():
    result = tailscale_down()
    return json_or_redirect("tailscale_down", result["ok"], "Tailscale disconnected" if result["ok"] else "Tailscale disconnect failed", result["stderr"] or result["stdout"], default_endpoint="router.settings_page")


@bp.route("/tailscale/exit-node/disable", methods=["POST"])
def vpn_exit_node_disable():
    result = tailscale_disable_exit_node()
    update_settings("tailscale", {"current_exit_node": ""})
    return json_or_redirect("tailscale_disable", result["ok"], "Exit node disabled" if result["ok"] else "Failed to disable exit node", result["stderr"] or result["stdout"], default_endpoint="router.settings_page")


@bp.route("/settings/jellyfin", methods=["POST"])
def jellyfin_settings():
    update_settings(
        "jellyfin",
        {
            "server_url": request.form.get("server_url", "").strip(),
            "api_key": request.form.get("api_key", "").strip(),
            "user_id": request.form.get("user_id", "").strip(),
            "device_name": request.form.get("device_name", "Pi Travel Router").strip(),
        },
    )
    return json_or_redirect("jellyfin_settings", True, "Jellyfin settings saved", default_endpoint="router.settings_page")


@bp.route("/settings")
def settings_page():
    settings = load_settings()
    tailscale = tailscale_status()
    tailscale_data = parse_tailscale_json(tailscale)
    exit_nodes = parse_exit_nodes(tailscale_data)
    jellyfin_configured = bool(
        settings["jellyfin"]["server_url"] and settings["jellyfin"]["api_key"] and settings["jellyfin"]["user_id"]
    )
    jellyfin_info = {
        "ok": False,
        "configured": jellyfin_configured,
        "reachable": False,
        "error": "Checking Jellyfin server..." if jellyfin_configured else "Configure Jellyfin below.",
    }
    return render_template(
        "settings.html",
        settings=settings,
        tailscale=tailscale,
        tailscale_data=tailscale_data,
        exit_nodes=exit_nodes,
        selected_exit_node=current_exit_node_value(tailscale_data, settings),
        jellyfin_info=jellyfin_info,
    )


@bp.route("/api/jellyfin/status")
def jellyfin_status_api():
    return jellyfin_system_info()


@bp.route("/settings/tailscale/login", methods=["POST"])
def settings_tailscale_login():
    result = tailscale_login()
    return json_or_redirect(
        "tailscale_login",
        result["ok"],
        "Tailscale login started" if result["ok"] else "Tailscale login failed",
        "Open the login link to finish authentication." if result.get("auth_url") else result["stderr"] or result["stdout"],
        result.get("auth_url", ""),
        default_endpoint="router.settings_page",
    )


@bp.route("/settings/tailscale", methods=["POST"])
def settings_tailscale():
    use_exit_node = request.form.get("use_exit_node") == "on"
    exit_node = request.form.get("exit_node", "").strip()

    if use_exit_node and not exit_node:
        return json_or_redirect("tailscale_settings", False, "Choose an exit node first", default_endpoint="router.settings_page")

    if use_exit_node:
        result = tailscale_up(exit_node)
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": exit_node})
    else:
        result = tailscale_disable_exit_node()
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": ""})
    return json_or_redirect(
        "tailscale_settings",
        result["ok"],
        "Tailscale settings saved" if result["ok"] else "Tailscale settings failed",
        result["stderr"] or result["stdout"],
        default_endpoint="router.settings_page",
    )


@bp.route("/media")
def media():
    settings = load_settings()
    search_term = request.args.get("q", "").strip() or None
    parent_id = request.args.get("parent_id", "").strip() or None
    local_resume = all_resume_seconds()
    if not parent_id and not search_term:
        items = jellyfin_views()
    else:
        items = jellyfin_items(parent_id=parent_id, search_term=search_term)

    if items.get("ok"):
        for item in items["data"].get("Items", []):
            item["LocalResumeSeconds"] = int(local_resume.get(item.get("Id", ""), 0) or 0)

    return render_template(
        "media.html",
        settings=settings,
        items=items,
        jellyfin_image_url=jellyfin_image_url,
        search_term=search_term or "",
        parent_id=parent_id or "",
    )


@bp.route("/media/play/<item_id>", methods=["POST"])
def media_play(item_id: str):
    resume = request.form.get("resume", "true").lower() == "true"
    result = play_jellyfin_item(item_id, resume=resume)
    return json_or_redirect("media_play", result["ok"], "Playback started" if result["ok"] else "Playback failed", result["stderr"] or result["stdout"], default_endpoint="router.media")


@bp.route("/remote")
def remote():
    playback_state = get_playback_state()
    return render_template("remote.html", playback_state=playback_state)


@bp.route("/remote/pause", methods=["POST"])
def remote_pause():
    result = pause_playback()
    return json_or_redirect("remote_pause", result["ok"], "Playback toggled" if result["ok"] else "Pause failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")


@bp.route("/remote/stop", methods=["POST"])
def remote_stop():
    result = stop_playback()
    return json_or_redirect("remote_stop", result["ok"], "Playback stopped" if result["ok"] else "Stop failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")


@bp.route("/remote/rewind", methods=["POST"])
def remote_rewind():
    result = seek_relative(-30)
    return json_or_redirect("remote_rewind", result["ok"], "Rewound 30 seconds" if result["ok"] else "Rewind failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")


@bp.route("/remote/forward", methods=["POST"])
def remote_forward():
    result = seek_relative(30)
    return json_or_redirect("remote_forward", result["ok"], "Skipped forward 30 seconds" if result["ok"] else "Skip failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")


@bp.route("/remote/audio", methods=["POST"])
def remote_audio():
    track_id = request.form.get("track_id", "").strip()
    if not track_id:
        return json_or_redirect("remote_audio", False, "No audio track selected", default_endpoint="router.remote")
    result = set_audio_track(int(track_id))
    return json_or_redirect("remote_audio", result["ok"], "Audio track changed" if result["ok"] else "Audio track change failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")


@bp.route("/remote/subtitles", methods=["POST"])
def remote_subtitles():
    track_id = request.form.get("track_id", "no").strip()
    value = "no" if track_id == "no" else int(track_id)
    result = set_subtitle_track(value)
    return json_or_redirect("remote_subtitles", result["ok"], "Subtitle settings updated" if result["ok"] else "Subtitle change failed", result["stderr"] or result["stdout"], default_endpoint="router.remote")
