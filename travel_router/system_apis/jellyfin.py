import requests
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..config_store import load_config


JELLYFIN_TIMEOUT = (1.5, 5)
JELLYFIN_DEVICE_ID = "pi-travel-router"
JELLYFIN_STREAM_BITRATE = 4_000_000


def jellyfin_headers() -> dict:
    config = load_config()["jellyfin"]
    return {
        "X-Emby-Token": config["api_key"],
        "X-Emby-Authorization": (
            'MediaBrowser Client="PiTravelRouter", Device="{}", DeviceId="{}", Version="1.0.0"'
        ).format(config["device_name"], JELLYFIN_DEVICE_ID),
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


def jellyfin_device_profile() -> dict:
    return {
        "Name": "PiTravelRouter",
        "MaxStaticBitrate": JELLYFIN_STREAM_BITRATE,
        "MaxStreamingBitrate": JELLYFIN_STREAM_BITRATE,
        "DirectPlayProfiles": [
            {
                "Container": "mkv,mp4,webm,mov",
                "Type": "Video",
                "VideoCodec": "h264,hevc,h265",
                "AudioCodec": "aac,mp3,opus,flac",
            }
        ],
        "TranscodingProfiles": [
            {
                "Container": "ts",
                "Type": "Video",
                "VideoCodec": "h264",
                "AudioCodec": "aac",
                "Protocol": "Http",
                "MaxAudioChannels": "2",
                "Bitrate": JELLYFIN_STREAM_BITRATE,
            }
        ],
        "SubtitleProfiles": [
            {"Format": "srt", "Method": "External"},
        ],
    }


def with_query_value(url: str, key: str, value: str) -> str:
    if not value:
        return url

    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunsplit(parsed._replace(query=urlencode(query)))


def absolute_jellyfin_url(path_or_url: str) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    if path_or_url.startswith("/"):
        return jellyfin_url(path_or_url)
    return jellyfin_url(f"/{path_or_url}")


def jellyfin_stream_url(item_id: str) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"] or not config["user_id"]:
        return {
            "ok": False,
            "url": "",
            "mode": "",
            "detail": "Jellyfin server URL, API key, and user ID are required.",
        }

    payload = {
        "UserId": config["user_id"],
        "DeviceProfile": jellyfin_device_profile(),
    }

    try:
        response = requests.post(
            jellyfin_url(f"/Items/{item_id}/PlaybackInfo"),
            headers=jellyfin_headers(),
            json=payload,
            timeout=JELLYFIN_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "url": "", "mode": "", "detail": format_jellyfin_error(exc)}

    data = response.json()
    media_sources = data.get("MediaSources") or []
    if not media_sources:
        return {"ok": False, "url": "", "mode": "", "detail": "Jellyfin did not return any playable media sources."}

    media_source = media_sources[0]
    media_source_id = str(media_source.get("Id") or "")
    play_session_id = str(data.get("PlaySessionId") or media_source.get("PlaySessionId") or "")

    if media_source.get("SupportsDirectPlay"):
        stream_url = jellyfin_url(f"/Videos/{item_id}/stream")
        stream_url = with_query_value(stream_url, "static", "true")
        stream_url = with_query_value(stream_url, "api_key", config["api_key"])
        stream_url = with_query_value(stream_url, "MediaSourceId", media_source_id)
        stream_url = with_query_value(stream_url, "PlaySessionId", play_session_id)
        return {
            "ok": True,
            "url": stream_url,
            "mode": "direct-play",
            "detail": "Playback started using direct play.",
        }

    direct_stream_url = absolute_jellyfin_url(str(media_source.get("DirectStreamUrl") or ""))
    if media_source.get("SupportsDirectStream") and direct_stream_url:
        direct_stream_url = with_query_value(direct_stream_url, "api_key", config["api_key"])
        direct_stream_url = with_query_value(direct_stream_url, "PlaySessionId", play_session_id)
        return {
            "ok": True,
            "url": direct_stream_url,
            "mode": "direct-stream",
            "detail": "Playback started using Jellyfin direct stream.",
        }

    transcode_url = absolute_jellyfin_url(str(media_source.get("TranscodingUrl") or ""))
    if transcode_url:
        transcode_url = with_query_value(transcode_url, "api_key", config["api_key"])
        transcode_url = with_query_value(transcode_url, "PlaySessionId", play_session_id)
        return {
            "ok": True,
            "url": transcode_url,
            "mode": "transcode",
            "detail": "Playback started using Jellyfin transcode.",
        }

    if direct_stream_url:
        direct_stream_url = with_query_value(direct_stream_url, "api_key", config["api_key"])
        direct_stream_url = with_query_value(direct_stream_url, "PlaySessionId", play_session_id)
        return {
            "ok": True,
            "url": direct_stream_url,
            "mode": "direct-stream",
            "detail": "Playback started using Jellyfin direct stream.",
        }

    return {
        "ok": False,
        "url": "",
        "mode": "",
        "detail": "Jellyfin did not return a usable playback URL.",
    }
