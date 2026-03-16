import json
import re
import shlex
import socket
import subprocess
from pathlib import Path

import requests

from .config_store import load_config, save_config


MPV_SOCKET = "/tmp/pi-travel-router-mpv.sock"
URL_PATTERN = re.compile(r"https://\S+")


def run_command(command: list[str]) -> dict:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"Missing command: {command[0]}",
            "command": " ".join(shlex.quote(part) for part in command),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Command timed out",
            "command": " ".join(shlex.quote(part) for part in command),
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    auth_url = extract_url(stdout) or extract_url(stderr)

    return {
        "ok": completed.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "command": " ".join(shlex.quote(part) for part in command),
        "auth_url": auth_url,
    }


def extract_url(text: str) -> str:
    if not text:
        return ""
    match = URL_PATTERN.search(text)
    return match.group(0).rstrip(".,)") if match else ""


def scan_wifi(interface: str) -> dict:
    return run_command(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", interface])


def connect_wifi(interface: str, ssid: str, password: str | None) -> dict:
    command = ["nmcli", "device", "wifi", "connect", ssid, "ifname", interface]
    if password:
        command.extend(["password", password])
    return run_command(command)


def current_wifi(interface: str) -> dict:
    result = run_command(
        [
            "nmcli",
            "-t",
            "-f",
            "ACTIVE,SSID,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list",
            "ifname",
            interface,
        ]
    )
    if not result["ok"]:
        return {"ok": False, "error": result["stderr"] or result["stdout"] or "Unable to read Wi-Fi state."}

    for line in result["stdout"].splitlines():
        parts = line.split(":")
        if not parts or parts[0] != "yes":
            continue
        ssid = parts[1] if len(parts) > 1 else ""
        signal = parts[2] if len(parts) > 2 else ""
        security = parts[3] if len(parts) > 3 else ""
        return {
            "ok": True,
            "connected": True,
            "ssid": ssid or "Hidden network",
            "signal": signal or "unknown",
            "security": security or "open",
        }

    return {"ok": True, "connected": False, "ssid": "", "signal": "", "security": ""}


def tailscale_status() -> dict:
    return run_command(["tailscale", "status", "--json"])


def tailscale_up(exit_node: str | None = None) -> dict:
    command = ["sudo", "tailscale", "up"]
    if exit_node:
        command.extend(["--exit-node", exit_node])
    return run_command(command)


def tailscale_login() -> dict:
    return run_command(["sudo", "tailscale", "up"])


def tailscale_down() -> dict:
    return run_command(["sudo", "tailscale", "down"])


def tailscale_disable_exit_node() -> dict:
    return run_command(["sudo", "tailscale", "set", "--exit-node="])


def systemctl_status(unit: str) -> dict:
    return run_command(["systemctl", "is-active", unit])


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


def jellyfin_system_info() -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"]:
        return {"ok": False, "error": "Jellyfin server URL and API key are required."}

    try:
        response = requests.get(
            jellyfin_url("/System/Info/Public"),
            headers=jellyfin_headers(),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "data": response.json()}


def jellyfin_items(parent_id: str | None = None, search_term: str | None = None) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"] or not config["user_id"]:
        return {"ok": False, "error": "Jellyfin server URL, API key, and user ID are required."}

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
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "data": response.json()}


def jellyfin_views() -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"] or not config["user_id"]:
        return {"ok": False, "error": "Jellyfin server URL, API key, and user ID are required."}

    try:
        response = requests.get(
            jellyfin_url(f"/Users/{config['user_id']}/Views"),
            headers=jellyfin_headers(),
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, "data": response.json()}


def jellyfin_image_url(item_id: str) -> str:
    config = load_config()["jellyfin"]
    return jellyfin_url(
        f"/Items/{item_id}/Images/Primary?fillHeight=520&fillWidth=360&quality=90&api_key={config['api_key']}"
    )


def play_jellyfin_item(item_id: str, resume: bool = True) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"]:
        return {"ok": False, "stderr": "Jellyfin server URL and API key are required."}

    save_resume_position()
    play_url = jellyfin_url(f"/Videos/{item_id}/stream")
    if "?" in play_url:
        play_url = f"{play_url}&static=true&api_key={config['api_key']}"
    else:
        play_url = f"{play_url}?static=true&api_key={config['api_key']}"

    start_time = load_resume_seconds(item_id) if resume else 0
    Path(MPV_SOCKET).unlink(missing_ok=True)
    subprocess.run(
        ["pkill", "-f", f"mpv --input-ipc-server={MPV_SOCKET}"],
        capture_output=True,
        text=True,
        check=False,
    )
    result = _spawn_mpv(play_url, start_time)
    if result["ok"]:
        update_playback_state(item_id)
    return result


def _spawn_mpv(play_url: str, start_time: int = 0) -> dict:
    command = [
        "mpv",
        "--fs",
        "--hwdec=auto",
        f"--input-ipc-server={MPV_SOCKET}",
        "--idle=yes",
    ]
    print("-------- MPV Command: \n", " ".join(command))
    if start_time > 0:
        command.append(f"--start={start_time}")
    command.append(play_url)
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "Missing command: mpv", "command": "mpv"}

    return {"ok": True, "stdout": "Playback started", "stderr": "", "command": "mpv"}


def mpv_command(payload: dict) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(MPV_SOCKET)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        response = sock.recv(4096).decode("utf-8").strip()
    except OSError as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "command": "mpv-ipc"}
    finally:
        sock.close()

    return {"ok": True, "stdout": response, "stderr": "", "command": "mpv-ipc"}


def mpv_get_property(property_name: str) -> dict:
    result = mpv_command({"command": ["get_property", property_name]})
    if not result["ok"]:
        return result

    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"ok": False, "stdout": "", "stderr": "Invalid mpv response", "command": "mpv-ipc"}

    if payload.get("error") != "success":
        return {"ok": False, "stdout": "", "stderr": payload.get("error", "mpv error"), "command": "mpv-ipc"}

    return {"ok": True, "data": payload.get("data"), "stdout": result["stdout"], "stderr": "", "command": "mpv-ipc"}


def mpv_set_property(property_name: str, value) -> dict:
    result = mpv_command({"command": ["set_property", property_name, value]})
    if not result["ok"]:
        return result
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"ok": False, "stdout": "", "stderr": "Invalid mpv response", "command": "mpv-ipc"}
    if payload.get("error") != "success":
        return {"ok": False, "stdout": "", "stderr": payload.get("error", "mpv error"), "command": "mpv-ipc"}
    return result


def load_resume_seconds(item_id: str) -> int:
    playback = load_config().get("playback", {})
    try:
        return int(playback.get("resume_seconds", {}).get(item_id, 0))
    except (TypeError, ValueError):
        return 0


def update_playback_state(item_id: str | None = None, resume_seconds: int | None = None) -> None:
    config = load_config()
    playback = config.setdefault("playback", {})
    playback.setdefault("resume_seconds", {})
    if item_id is not None:
        playback["active_item_id"] = item_id
    if item_id and resume_seconds is not None:
        if resume_seconds > 15:
            playback["resume_seconds"][item_id] = int(resume_seconds)
        else:
            playback["resume_seconds"].pop(item_id, None)
    save_config(config)


def all_resume_seconds() -> dict:
    return load_config().get("playback", {}).get("resume_seconds", {})


def save_resume_position() -> dict:
    config = load_config()
    active_item_id = config.get("playback", {}).get("active_item_id", "")
    if not active_item_id:
        return {"ok": True, "stdout": "No active item", "stderr": "", "command": "resume-save"}

    time_pos = mpv_get_property("time-pos")
    duration = mpv_get_property("duration")
    if not time_pos["ok"]:
        return time_pos

    seconds = int(float(time_pos.get("data") or 0))
    total = int(float(duration.get("data") or 0)) if duration["ok"] and duration.get("data") else 0
    if total and seconds >= max(total - 60, 0):
        seconds = 0
    update_playback_state(active_item_id, seconds)
    return {"ok": True, "stdout": f"Saved resume at {seconds}s", "stderr": "", "command": "resume-save"}


def get_playback_state() -> dict:
    tracks = mpv_get_property("track-list")
    pause_state = mpv_get_property("pause")
    time_pos = mpv_get_property("time-pos")
    duration = mpv_get_property("duration")
    playback = load_config().get("playback", {})
    active_item_id = playback.get("active_item_id", "")

    if not tracks["ok"]:
        return {
            "ok": False,
            "error": tracks["stderr"],
            "active_item_id": active_item_id,
            "resume_seconds": load_resume_seconds(active_item_id) if active_item_id else 0,
        }

    audio_tracks = []
    subtitle_tracks = []
    for track in tracks.get("data") or []:
        entry = {
            "id": track.get("id"),
            "lang": track.get("lang") or "und",
            "title": track.get("title") or track.get("codec") or f"Track {track.get('id')}",
            "selected": bool(track.get("selected")),
        }
        if track.get("type") == "audio":
            audio_tracks.append(entry)
        elif track.get("type") == "sub":
            subtitle_tracks.append(entry)

    return {
        "ok": True,
        "audio_tracks": audio_tracks,
        "subtitle_tracks": subtitle_tracks,
        "paused": bool(pause_state.get("data")) if pause_state["ok"] else None,
        "time_pos": int(float(time_pos.get("data") or 0)) if time_pos["ok"] and time_pos.get("data") is not None else 0,
        "duration": int(float(duration.get("data") or 0)) if duration["ok"] and duration.get("data") is not None else 0,
        "active_item_id": active_item_id,
        "resume_seconds": load_resume_seconds(active_item_id) if active_item_id else 0,
    }


def set_audio_track(track_id: int) -> dict:
    return mpv_set_property("aid", track_id)


def set_subtitle_track(track_id: int | str) -> dict:
    return mpv_set_property("sid", track_id)


def stop_playback() -> dict:
    save_resume_position()
    return mpv_command({"command": ["quit"]})


def pause_playback() -> dict:
    return mpv_command({"command": ["cycle", "pause"]})


def seek_relative(seconds: int) -> dict:
    return mpv_command({"command": ["seek", seconds, "relative"]})


def load_settings() -> dict:
    return load_config()


def update_settings(section: str, values: dict) -> dict:
    config = load_config()
    config.setdefault(section, {})
    config[section].update(values)
    save_config(config)
    return config
