import json

from flask import Blueprint, redirect, render_template, request, url_for

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
    portal_browser_status,
    scan_wifi,
    seek_relative,
    set_audio_track,
    start_portal_browser,
    set_subtitle_track,
    stop_portal_browser,
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
    return render_template("action.html", title="Wi-Fi Connect", result=result)


@bp.route("/portal")
def captive_portal():
    portal = portal_browser_status(request.host.split(":")[0])
    return render_template("portal.html", portal=portal)


@bp.route("/portal/start", methods=["POST"])
def captive_portal_start():
    result = start_portal_browser()
    return render_template("action.html", title="Start Captive Portal Browser", result=result)


@bp.route("/portal/stop", methods=["POST"])
def captive_portal_stop():
    stop_portal_browser()
    portal = portal_browser_status(request.host.split(":")[0])
    return render_template("portal.html", portal=portal)



@bp.route("/settings/wifi", methods=["POST"])
def wifi_settings():
    update_settings(
        "wifi",
        {
            "upstream_interface": request.form.get("upstream_interface", "wlan0").strip(),
            "ap_interface": request.form.get("ap_interface", "wlan1").strip(),
        },
    )
    return redirect(url_for("router.index"))


@bp.route("/tailscale/up", methods=["POST"])
def vpn_up():
    exit_node = request.form.get("exit_node", "").strip() or None
    result = tailscale_up(exit_node)
    if exit_node:
        update_settings("tailscale", {"current_exit_node": exit_node})
    return render_template("action.html", title="Tailscale Up", result=result)


@bp.route("/tailscale/down", methods=["POST"])
def vpn_down():
    result = tailscale_down()
    return render_template("action.html", title="Tailscale Down", result=result)


@bp.route("/tailscale/exit-node/disable", methods=["POST"])
def vpn_exit_node_disable():
    result = tailscale_disable_exit_node()
    update_settings("tailscale", {"current_exit_node": ""})
    return render_template("action.html", title="Disable Exit Node", result=result)


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
    return redirect(url_for("router.settings_page"))


@bp.route("/settings")
def settings_page():
    settings = load_settings()
    tailscale = tailscale_status()
    tailscale_data = parse_tailscale_json(tailscale)
    exit_nodes = parse_exit_nodes(tailscale_data)
    jellyfin_info = jellyfin_system_info()
    return render_template(
        "settings.html",
        settings=settings,
        tailscale=tailscale,
        tailscale_data=tailscale_data,
        exit_nodes=exit_nodes,
        selected_exit_node=current_exit_node_value(tailscale_data, settings),
        jellyfin_info=jellyfin_info,
    )


@bp.route("/settings/tailscale/login", methods=["POST"])
def settings_tailscale_login():
    result = tailscale_login()
    return render_template("action.html", title="Tailscale Login", result=result)


@bp.route("/settings/tailscale", methods=["POST"])
def settings_tailscale():
    use_exit_node = request.form.get("use_exit_node") == "on"
    exit_node = request.form.get("exit_node", "").strip()

    if use_exit_node and not exit_node:
        result = {"ok": False, "stdout": "", "stderr": "Choose an exit node before enabling it.", "command": "tailscale"}
        return render_template("action.html", title="Tailscale Settings", result=result)

    if use_exit_node:
        result = tailscale_up(exit_node)
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": exit_node})
    else:
        result = tailscale_disable_exit_node()
        if result["ok"]:
            update_settings("tailscale", {"current_exit_node": ""})
    return render_template("action.html", title="Tailscale Settings", result=result)


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
    return render_template("action.html", title="Play Media", result=result)


@bp.route("/remote")
def remote():
    playback_state = get_playback_state()
    return render_template("remote.html", playback_state=playback_state)


@bp.route("/remote/pause", methods=["POST"])
def remote_pause():
    return render_template("action.html", title="Pause / Resume", result=pause_playback())


@bp.route("/remote/stop", methods=["POST"])
def remote_stop():
    return render_template("action.html", title="Stop Playback", result=stop_playback())


@bp.route("/remote/rewind", methods=["POST"])
def remote_rewind():
    return render_template("action.html", title="Rewind Playback", result=seek_relative(-30))


@bp.route("/remote/forward", methods=["POST"])
def remote_forward():
    return render_template("action.html", title="Forward Playback", result=seek_relative(30))


@bp.route("/remote/audio", methods=["POST"])
def remote_audio():
    track_id = request.form.get("track_id", "").strip()
    if not track_id:
        result = {"ok": False, "stdout": "", "stderr": "No audio track selected", "command": "mpv-ipc"}
        return render_template("action.html", title="Change Audio Track", result=result)
    result = set_audio_track(int(track_id))
    return render_template("action.html", title="Change Audio Track", result=result)


@bp.route("/remote/subtitles", methods=["POST"])
def remote_subtitles():
    track_id = request.form.get("track_id", "no").strip()
    value = "no" if track_id == "no" else int(track_id)
    result = set_subtitle_track(value)
    return render_template("action.html", title="Change Subtitle Track", result=result)
