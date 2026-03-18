import requests

from ..config_store import load_config


JELLYFIN_TIMEOUT = (1.5, 5)


def jellyfin_headers() -> dict:
    config = load_config()["jellyfin"]
    return {
        "X-Emby-Token": config["api_key"],
        "X-Emby-Authorization": (
            'MediaBrowser Client="PiTravelRouter", Device="{}", DeviceId="pi-travel-router", Version="1.0.0"'
        ).format(config["device_name"]),
    }


def jellyfin_url(path: str) -> str:
    config = load_config()["jellyfin"]
    base = config["server_url"].rstrip("/")
    return f"{base}{path}"


def format_jellyfin_error(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.Timeout):
        return "Jellyfin server timed out."
    if isinstance(exc, requests.ConnectionError):
        return "Jellyfin server is unreachable."
    response = getattr(exc, "response", None)
    if response is not None:
        return f"Jellyfin returned HTTP {response.status_code}."
    return str(exc) or "Jellyfin request failed."


def jellyfin_system_info() -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"]:
        return {"ok": False, "configured": False, "reachable": False, "error": "Jellyfin server URL and API key are required."}

    try:
        response = requests.get(
            jellyfin_url("/System/Info/Public"),
            headers=jellyfin_headers(),
            timeout=JELLYFIN_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "configured": True, "reachable": False, "error": format_jellyfin_error(exc)}

    return {"ok": True, "configured": True, "reachable": True, "data": response.json()}


def jellyfin_items(parent_id: str | None = None, search_term: str | None = None) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"] or not config["user_id"]:
        return {"ok": False, "configured": False, "reachable": False, "error": "Jellyfin server URL, API key, and user ID are required."}

    params = {
        "Recursive": "true" if search_term else "false",
        "IncludeItemTypes": "Movie,Series,Season,Episode,Video",
        "Fields": "Overview,PrimaryImageAspectRatio,UserData",
        "SortBy": "SortName",
        "SortOrder": "Ascending",
        "Limit": "100",
    }
    if parent_id:
        params["ParentId"] = parent_id
    if search_term:
        params["SearchTerm"] = search_term

    try:
        response = requests.get(
            jellyfin_url(f"/Users/{config['user_id']}/Items"),
            headers=jellyfin_headers(),
            params=params,
            timeout=JELLYFIN_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "configured": True, "reachable": False, "error": format_jellyfin_error(exc)}

    return {"ok": True, "configured": True, "reachable": True, "data": response.json()}


def jellyfin_views() -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"] or not config["user_id"]:
        return {"ok": False, "configured": False, "reachable": False, "error": "Jellyfin server URL, API key, and user ID are required."}

    try:
        response = requests.get(
            jellyfin_url(f"/Users/{config['user_id']}/Views"),
            headers=jellyfin_headers(),
            timeout=JELLYFIN_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "configured": True, "reachable": False, "error": format_jellyfin_error(exc)}

    return {"ok": True, "configured": True, "reachable": True, "data": response.json()}


def jellyfin_image_url(item_id: str) -> str:
    config = load_config()["jellyfin"]
    return jellyfin_url(
        f"/Items/{item_id}/Images/Primary?fillHeight=520&fillWidth=360&quality=90&api_key={config['api_key']}"
    )
