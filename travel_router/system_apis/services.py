from ..env import is_demo_mode
from .command import demo_command_result, run_command
from .config import demo_state


def systemctl_status(unit: str) -> dict:
    if is_demo_mode():
        service_state = demo_state()["services"].get(unit, "inactive")
        return demo_command_result(f"demo systemctl is-active {unit}", stdout=service_state, ok=service_state == "active")
    return run_command(["systemctl", "is-active", unit])
