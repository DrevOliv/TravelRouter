import json


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
