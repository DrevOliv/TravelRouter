import json

from ..env import is_demo_mode
from run_command import demo_command_result, run_command
from .config import demo_state, load_settings, update_demo


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
    command = ["sudo", "tailscale", "up"]
    if exit_node:
        command.extend(["--exit-node", exit_node])
    return run_command(command)


def tailscale_disable_exit_node() -> dict:
    if is_demo_mode():
        update_demo("tailscale", {"backend_state": "Running"})
        return demo_command_result("demo tailscale disable exit node", stdout="Exit node disabled")
    return run_command(["sudo", "tailscale", "set", "--exit-node="])
