from ..common.parsers import parse_exit_nodes, parse_tailscale_json
from ..system_apis import jellyfin_system_info, load_settings, tailscale_status


def resolve_saved_exit_node(selected: str) -> str:
    selected = selected.strip()
    if not selected:
        return ""

    status = tailscale_status()
    tailscale_data = parse_tailscale_json(status)
    exit_nodes = parse_exit_nodes(tailscale_data)
    for node in exit_nodes:
        if node["value"] == selected or node["label"] == selected:
            return node["value"]

    peers = tailscale_data.get("Peer") or {}
    for peer in peers.values():
        dns_name = str(peer.get("DNSName") or "").rstrip(".")
        host_name = str(peer.get("HostName") or "").rstrip(".")
        tailscale_ips = peer.get("TailscaleIPs") or []
        candidate_ip = str(tailscale_ips[0]).rstrip(".") if tailscale_ips else ""
        if selected in {dns_name, host_name} and candidate_ip:
            return candidate_ip

    return selected


def settings_payload() -> dict:
    settings = load_settings()
    jellyfin_configured = bool(
        settings["jellyfin"]["server_url"] and settings["jellyfin"]["api_key"] and settings["jellyfin"]["user_id"]
    )
    return {
        "settings": settings,
        "jellyfin": {
            "configured": jellyfin_configured,
            "ok": False,
            "error": "Checking Jellyfin server..." if jellyfin_configured else "Configure Jellyfin below.",
        },
    }
