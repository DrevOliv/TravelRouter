import json

from .system_apis import (
    all_resume_seconds,
    ap_connected_devices,
    browse_import_source,
    current_wifi,
    get_playback_state,
    import_job_manager,
    jellyfin_image_url,
    jellyfin_items,
    jellyfin_views,
    list_import_devices,
    load_settings,
    scan_wifi,
    systemctl_status,
    tailscale_status,
    transfer_settings_summary,
)


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
        node_value = tailscale_ips[0] if tailscale_ips else (peer.get("DNSName") or peer_id)
        nodes.append(
            {
                "value": str(node_value).rstrip("."),
                "label": (peer.get("HostName") or peer.get("DNSName") or node_value).rstrip("."),
                "online": bool(peer.get("Online")),
            }
        )
    nodes.sort(key=lambda node: node["label"].lower())
    return nodes


def split_nmcli_row(row: str) -> list[str]:
    parts = []
    current = []
    escape = False
    for char in row:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == ":":
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return [part.replace("\\:", ":") for part in parts]


def parse_wifi_scan_rows(scan_result: dict) -> list[dict]:
    if not scan_result.get("ok"):
        return []

    networks = []
    seen = set()
    for row in scan_result.get("stdout", "").splitlines():
        if not row.strip():
            continue
        parts = split_nmcli_row(row)
        ssid = (parts[0] if len(parts) > 0 else "").strip() or "Hidden network"
        signal_text = (parts[1] if len(parts) > 1 else "").strip()
        security = (parts[2] if len(parts) > 2 else "").strip() or "Open"
        key = (ssid, security)
        if key in seen:
            continue
        seen.add(key)
        try:
            signal = int(signal_text)
        except ValueError:
            signal = 0
        networks.append(
            {
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "is_open": security.lower() in {"", "open", "--"},
            }
        )

    networks.sort(key=lambda network: (-network["signal"], network["ssid"].lower()))
    return networks


def current_exit_node_value(tailscale_data: dict, settings: dict) -> str:
    selected = tailscale_data.get("Self", {}).get("ExitNodeStatus") or {}
    if selected.get("ID"):
        peer = (tailscale_data.get("Peer") or {}).get(selected["ID"], {})
        return (peer.get("DNSName") or peer.get("HostName") or settings["tailscale"]["current_exit_node"]).rstrip(".")
    return settings["tailscale"]["current_exit_node"]


def action_payload(action: str, result: dict, success_message: str, error_message: str, detail: str = "", link: str = "", refresh: str | None = None) -> dict:
    return {
        "ok": result["ok"],
        "action": action,
        "message": success_message if result["ok"] else error_message,
        "detail": detail or result.get("stderr") or result.get("stdout") or "",
        "link": link or result.get("auth_url", ""),
        "refresh": refresh,
    }


def wifi_live_payload(upstream_interface: str) -> dict:
    wifi_scan = scan_wifi(upstream_interface)
    settings = load_settings()
    return {
        "wifi_scan": wifi_scan,
        "wifi_networks": parse_wifi_scan_rows(wifi_scan),
        "wifi_current": current_wifi(upstream_interface),
        "connected_devices": ap_connected_devices(settings["wifi"]["ap_interface"]),
    }


def home_payload() -> dict:
    settings = load_settings()
    wifi_live = wifi_live_payload(settings["wifi"]["upstream_interface"])
    tailscale = tailscale_status()
    tailscale_data = parse_tailscale_json(tailscale)
    services = {
        "hostapd": systemctl_status("hostapd"),
        "dnsmasq": systemctl_status("dnsmasq"),
        "tailscaled": systemctl_status("tailscaled"),
    }
    return {
        "settings": settings,
        **wifi_live,
        "tailscale": tailscale,
        "tailscale_data": tailscale_data,
        "exit_nodes": parse_exit_nodes(tailscale_data),
        "selected_exit_node": settings["tailscale"]["current_exit_node"],
        "exit_node_active": bool((tailscale_data.get("Self", {}).get("ExitNodeStatus") or {}).get("ID")) or bool(settings["tailscale"].get("exit_node_enabled")),
        "services": services,
    }


def settings_payload() -> dict:
    settings = load_settings()
    tailscale = tailscale_status()
    tailscale_data = parse_tailscale_json(tailscale)
    exit_nodes = parse_exit_nodes(tailscale_data)
    jellyfin_configured = bool(
        settings["jellyfin"]["server_url"] and settings["jellyfin"]["api_key"] and settings["jellyfin"]["user_id"]
    )
    return {
        "settings": settings,
        "tailscale": tailscale,
        "tailscale_data": tailscale_data,
        "exit_nodes": exit_nodes,
        "selected_exit_node": settings["tailscale"]["current_exit_node"],
        "exit_node_active": bool((tailscale_data.get("Self", {}).get("ExitNodeStatus") or {}).get("ID")) or bool(settings["tailscale"].get("exit_node_enabled")),
        "jellyfin": {
            "configured": jellyfin_configured,
            "ok": False,
            "error": "Checking Jellyfin server..." if jellyfin_configured else "Configure Jellyfin below.",
        },
    }


def media_payload(search_term: str | None, parent_id: str | None) -> dict:
    local_resume = all_resume_seconds()
    if not parent_id and not search_term:
        items = jellyfin_views()
    else:
        items = jellyfin_items(parent_id=parent_id, search_term=search_term)

    if items.get("ok"):
        normalized_items = []
        for item in items["data"].get("Items", []):
            item["LocalResumeSeconds"] = int(local_resume.get(item.get("Id", ""), 0) or 0)
            item["image_url"] = jellyfin_image_url(item["Id"])
            normalized_items.append(item)
        items["data"]["Items"] = normalized_items

    return {
        "search_term": search_term or "",
        "parent_id": parent_id or "",
        "items": items,
    }


def remote_payload() -> dict:
    return {"playback_state": get_playback_state()}


def import_payload(device_path: str | None = None, source_path: str | None = None) -> dict:
    devices = list_import_devices()
    selected_device = (device_path or "").strip()
    if not selected_device:
        mounted = next((device for device in devices if device.get("mounted")), None)
        selected_device = (mounted or (devices[0] if devices else {})).get("device_path", "")

    browser = browse_import_source(selected_device, source_path or "") if selected_device else {
        "ok": False,
        "error": "Insert and mount an SD card to browse photos.",
        "current_path": "",
        "directories": [],
        "files": [],
        "breadcrumbs": [],
    }
    return {
        "transfer": transfer_settings_summary(),
        "devices": devices,
        "selected_device": selected_device,
        "browser": browser,
        "jobs": import_job_manager.list_jobs(),
    }
