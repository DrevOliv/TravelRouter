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
    "demo": {
        "wifi_networks": [
            {"ssid": "Hotel Aurora", "signal": 88, "security": "WPA2", "is_open": False},
            {"ssid": "Cafe Nomad", "signal": 67, "security": "Open", "is_open": True},
            {"ssid": "Airport Lounge", "signal": 73, "security": "WPA2", "is_open": False},
            {"ssid": "Train WiFi", "signal": 41, "security": "WPA2", "is_open": False},
        ],
        "wifi_current": {
            "connected": False,
            "ssid": "",
            "signal": "",
            "security": "",
        },
        "tailscale": {
            "logged_in": False,
            "backend_state": "NeedsLogin",
            "host_name": "pi-travel-router-demo",
            "current_exit_node": "",
            "auth_url": "https://login.tailscale.com/demo",
            "exit_nodes": [
                {"value": "stockholm-exit.demo.ts.net", "label": "Stockholm Exit", "online": True},
                {"value": "london-exit.demo.ts.net", "label": "London Exit", "online": True},
                {"value": "newyork-exit.demo.ts.net", "label": "New York Exit", "online": False},
            ],
        },
        "services": {
            "hostapd": "active",
            "dnsmasq": "active",
            "tailscaled": "active",
        },
        "playback": {
            "active_item_id": "",
            "paused": False,
            "time_pos": 0,
            "duration": 6942,
            "audio_tracks": [
                {"id": 1, "lang": "eng", "title": "English 5.1", "selected": True},
                {"id": 2, "lang": "jpn", "title": "Japanese Stereo", "selected": False},
            ],
            "subtitle_tracks": [
                {"id": 1, "lang": "eng", "title": "English", "selected": False},
                {"id": 2, "lang": "swe", "title": "Swedish", "selected": False},
            ],
        },
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
