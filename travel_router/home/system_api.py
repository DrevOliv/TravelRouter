from ..common.parsers import parse_exit_nodes, parse_tailscale_json, parse_wifi_scan_rows
from ..system_apis import ap_connected_devices, current_wifi, load_settings, scan_wifi, tailscale_status


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
    tailscale_data = parse_tailscale_json(tailscale_status())
    return {
        "settings": settings,
        **wifi_live,
        "exit_nodes": parse_exit_nodes(tailscale_data),
        "selected_exit_node": settings["tailscale"]["current_exit_node"],
        "exit_node_active": bool((tailscale_data.get("Self", {}).get("ExitNodeStatus") or {}).get("ID"))
        or bool(settings["tailscale"].get("exit_node_enabled")),
    }
