import json

from ..command_runner import demo_command_result, run_command
from ..env import is_demo_mode
from ..settings_store import demo_state, load_settings, update_demo


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


def tailscale_status() -> dict:
    if is_demo_mode():
        config = load_settings()
        state = config["demo"]["tailscale"]
        active_exit_node = state["current_exit_node"] if config["tailscale"].get("exit_node_enabled") else ""
        payload = {
            "BackendState": state["backend_state"],
            "Self": {
                "HostName": state["host_name"],
                "ExitNodeStatus": {"ID": active_exit_node} if active_exit_node else {},
            },
            "Peer": {
                node["value"]: {
                    "HostName": node["label"],
                    "DNSName": node.get("dns_name", node["value"]),
                    "Online": node["online"],
                    "ExitNodeOption": True,
                    "TailscaleIPs": [node["value"]],
                }
                for node in state["exit_nodes"]
            },
        }
        return demo_command_result("demo tailscale status", stdout=json.dumps(payload))

    return run_command(["tailscale", "status", "--json"])


def tailscale_up(exit_node: str | None = None) -> dict:
    if is_demo_mode():
        state = demo_state()["tailscale"]
        update_demo(
            "tailscale",
            {
                "backend_state": "Running",
                "current_exit_node": exit_node or state["current_exit_node"],
            },
        )
        stdout = f"Connected to exit node {exit_node}" if exit_node else "Tailscale is running"
        return demo_command_result("demo tailscale up", stdout=stdout)

    command = ["sudo", "tailscale", "set"]
    if exit_node:
        command.extend(["--exit-node", exit_node, "--exit-node-allow-lan-access"])
    return run_command(command)


def tailscale_disable_exit_node() -> dict:
    if is_demo_mode():
        update_demo("tailscale", {"backend_state": "Running"})
        return demo_command_result("demo tailscale disable exit node", stdout="Exit node disabled")

    return run_command(["sudo", "tailscale", "set", "--exit-node="])


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
