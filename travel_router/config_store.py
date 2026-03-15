import json
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"


DEFAULT_CONFIG = {
    "wifi": {
        "upstream_interface": "wlan0",
        "ap_interface": "wlan1",
    },
    "tailscale": {
        "advertise_exit_node": False,
        "current_exit_node": "",
    },
    "jellyfin": {
        "server_url": "",
        "api_key": "",
        "user_id": "",
        "device_name": "Pi Travel Router",
    },
    "playback": {
        "active_item_id": "",
        "resume_seconds": {},
    },
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for section, values in stored.items():
        if isinstance(values, dict) and section in merged:
            merged[section].update(values)
        else:
            merged[section] = values
    return merged


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
