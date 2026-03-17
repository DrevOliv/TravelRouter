import json
import re
import shlex
import socket
import subprocess
from pathlib import Path

import requests

from .config_store import load_config, save_config
from .env import is_demo_mode


MPV_SOCKET = "/tmp/pi-travel-router-mpv.sock"
URL_PATTERN = re.compile(r"https://\S+")
JELLYFIN_TIMEOUT = (1.5, 5)
DNSMASQ_LEASES_PATH = Path("/var/lib/misc/dnsmasq.leases")


def demo_state() -> dict:
    return load_config()["demo"]


def update_demo(section: str, values: dict) -> dict:
    config = load_config()
    demo = config.setdefault("demo", {})
    demo.setdefault(section, {})
    demo[section].update(values)
    save_config(config)
    return demo[section]


def save_demo_state(state: dict) -> None:
    config = load_config()
    config["demo"] = state
    save_config(config)


def demo_command_result(command: str, stdout: str = "", stderr: str = "", ok: bool = True, auth_url: str = "") -> dict:
    return {
        "ok": ok,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "auth_url": auth_url,
    }


def run_command_output(command: list[str]) -> dict:
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

def run_command(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return False

    return True


def extract_url(text: str) -> str:
    if not text:
        return ""
    match = URL_PATTERN.search(text)
    return match.group(0).rstrip(".,)") if match else ""


def scan_wifi(interface: str) -> dict:
    if is_demo_mode():
        rows = []
        for network in demo_state()["wifi_networks"]:
            rows.append(f"{network['ssid']}:{network['signal']}:{network['security']}")
        return demo_command_result(f"demo wifi scan {interface}", stdout="\n".join(rows))
    
    run_command(["sudo", "nmcli", "device", "wifi", "rescan", "ifname", "wlan0"])

    return run_command_output(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", interface])


def connect_wifi(interface: str, ssid: str, password: str | None) -> dict: # DONE
    if is_demo_mode():
        state = demo_state()
        selected = next((network for network in state["wifi_networks"] if network["ssid"] == ssid), None)
        if not selected:
            return demo_command_result("demo wifi connect", stderr="Network not found", ok=False)
        update_demo(
            "wifi_current",
            {
                "connected": True,
                "ssid": selected["ssid"],
                "signal": str(selected["signal"]),
                "security": selected["security"],
            },
        )
        return demo_command_result("demo wifi connect", stdout=f"Connected to {ssid}")
    #command = ["nmcli", "device", "wifi", "connect", ssid, "ifname", interface]
    # Disconnect: sudo nmcli connection delete "Drevets"

    command = ["sudo", "nmcli", "dev", "wifi", "connect", ssid, "ifname", interface]
    if password:
        command.extend(["password", password])
    return run_command_output(command)


def disconnect_wifi(interface: str) -> dict:
    if is_demo_mode():
        update_demo(
            "wifi_current",
            {
                "connected": False,
                "ssid": "",
                "signal": "",
                "security": "",
            },
        )
        return demo_command_result("demo wifi disconnect", stdout=f"Disconnected {interface}")
    return run_command(["sudo", "nmcli", "device", "disconnect", interface])


def current_wifi(interface: str) -> dict: # DONE
    if is_demo_mode():
        current = demo_state()["wifi_current"]
        return {"ok": True, **current}
    result = run_command_output(
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


def ap_connected_devices(interface: str) -> list[dict]:
    if is_demo_mode():
        devices = demo_state().get("ap_clients", [])
        return sorted(devices, key=lambda device: ((device.get("name") or "").lower(), device.get("ip") or ""))

    lease_map = {}
    if DNSMASQ_LEASES_PATH.exists():
        try:
            for row in DNSMASQ_LEASES_PATH.read_text(encoding="utf-8").splitlines():
                parts = row.split()
                if len(parts) < 4:
                    continue
                _expires, mac, ip, hostname = parts[:4]
                lease_map[ip] = {
                    "ip": ip,
                    "mac": mac.upper(),
                    "name": "" if hostname == "*" else hostname,
                    "state": "lease",
                }
        except OSError:
            lease_map = {}

    result = run_command_output(["ip", "-j", "neigh", "show", "dev", interface])
    if not result["ok"]:
        return sorted(lease_map.values(), key=lambda device: ((device.get("name") or "").lower(), device.get("ip") or ""))

    try:
        neighbors = json.loads(result["stdout"] or "[]")
    except json.JSONDecodeError:
        neighbors = []

    devices = {}
    for entry in neighbors:
        ip = entry.get("dst", "")
        if not ip:
            continue
        state = " ".join(entry.get("state") or [])
        if state.upper() in {"FAILED", "INCOMPLETE", "NOARP"}:
            continue
        mac = (entry.get("lladdr") or lease_map.get(ip, {}).get("mac") or "").upper()
        name = lease_map.get(ip, {}).get("name") or ip
        devices[ip] = {
            "ip": ip,
            "mac": mac,
            "name": name,
            "state": state.lower() if state else "reachable",
        }

    for ip, lease in lease_map.items():
        devices.setdefault(
            ip,
            {
                "ip": ip,
                "mac": lease.get("mac", ""),
                "name": lease.get("name") or ip,
                "state": lease.get("state", "lease"),
            },
        )

    return sorted(devices.values(), key=lambda device: ((device.get("name") or "").lower(), device.get("ip") or ""))


def tailscale_status() -> dict:
    if is_demo_mode():
        config = load_config()
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
                    "DNSName": node["value"],
                    "Online": node["online"],
                    "ExitNodeOption": True,
                    "TailscaleIPs": [node["value"]],
                }
                for node in state["exit_nodes"]
            },
        }
        return demo_command_result("demo tailscale status", stdout=json.dumps(payload))
    return run_command_output(["tailscale", "status", "--json"])


def tailscale_up(exit_node: str | None = None) -> dict:
    if is_demo_mode():
        state = demo_state()["tailscale"]
        update_demo(
            "tailscale",
            {
                "logged_in": True,
                "backend_state": "Running",
                "current_exit_node": exit_node or state["current_exit_node"],
            },
        )
        stdout = f"Connected to exit node {exit_node}" if exit_node else "Tailscale is running"
        return demo_command_result("demo tailscale up", stdout=stdout)
    command = ["sudo", "tailscale", "up"]
    if exit_node:
        command.extend(["--exit-node", exit_node])
    return run_command_output(command)


def tailscale_login() -> dict:
    if is_demo_mode():
        state = demo_state()["tailscale"]
        update_demo("tailscale", {"logged_in": False, "backend_state": "NeedsLogin"})
        return demo_command_result(
            "demo tailscale login",
            stdout="Open the login URL to authenticate.",
            auth_url=state["auth_url"],
        )
    return run_command_output(["sudo", "tailscale", "up"])


def tailscale_down() -> dict:
    if is_demo_mode():
        update_demo("tailscale", {"logged_in": False, "backend_state": "Stopped", "current_exit_node": ""})
        return demo_command_result("demo tailscale down", stdout="Tailscale stopped")
    return run_command_output(["sudo", "tailscale", "down"])


def tailscale_disable_exit_node() -> dict:
    if is_demo_mode():
        update_demo("tailscale", {"backend_state": "Running"})
        return demo_command_result("demo tailscale disable exit node", stdout="Exit node disabled")
    return run_command_output(["sudo", "tailscale", "set", "--exit-node="])


def systemctl_status(unit: str) -> dict:
    if is_demo_mode():
        service_state = demo_state()["services"].get(unit, "inactive")
        return demo_command_result(f"demo systemctl is-active {unit}", stdout=service_state, ok=service_state == "active")
    return run_command_output(["systemctl", "is-active", unit])


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


def play_jellyfin_item(item_id: str, resume: bool = True) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"]:
        return {"ok": False, "stderr": "Jellyfin server URL and API key are required."}

    if is_demo_mode():
        config = load_config()
        demo_playback = config["demo"]["playback"]
        start_time = load_resume_seconds(item_id) if resume else 0
        demo_playback["active_item_id"] = item_id
        demo_playback["paused"] = False
        demo_playback["time_pos"] = start_time
        demo_playback["duration"] = max(int(demo_playback.get("duration", 6942) or 6942), start_time + 600)
        save_config(config)
        update_playback_state(item_id)
        return demo_command_result("demo mpv play", stdout="Playback started")

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
    if is_demo_mode():
        config = load_config()
        demo_playback = config["demo"]["playback"]
        active_item_id = demo_playback.get("active_item_id", "")
        return {
            "ok": bool(active_item_id),
            "error": "" if active_item_id else "No active playback session yet.",
            "audio_tracks": demo_playback.get("audio_tracks", []),
            "subtitle_tracks": demo_playback.get("subtitle_tracks", []),
            "paused": bool(demo_playback.get("paused")),
            "time_pos": int(demo_playback.get("time_pos", 0) or 0),
            "duration": int(demo_playback.get("duration", 0) or 0),
            "active_item_id": active_item_id,
            "resume_seconds": load_resume_seconds(active_item_id) if active_item_id else 0,
        }

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
    if is_demo_mode():
        config = load_config()
        tracks = config["demo"]["playback"]["audio_tracks"]
        for track in tracks:
            track["selected"] = track["id"] == track_id
        save_config(config)
        return demo_command_result("demo mpv set audio", stdout=f"Audio track {track_id} selected")
    return mpv_set_property("aid", track_id)


def set_subtitle_track(track_id: int | str) -> dict:
    if is_demo_mode():
        config = load_config()
        tracks = config["demo"]["playback"]["subtitle_tracks"]
        for track in tracks:
            track["selected"] = track["id"] == track_id
        save_config(config)
        label = "off" if track_id == "no" else str(track_id)
        return demo_command_result("demo mpv set subtitles", stdout=f"Subtitle track {label} selected")
    return mpv_set_property("sid", track_id)


def stop_playback() -> dict:
    if is_demo_mode():
        save_resume_position()
        config = load_config()
        config["demo"]["playback"]["active_item_id"] = ""
        config["demo"]["playback"]["paused"] = False
        config["demo"]["playback"]["time_pos"] = 0
        save_config(config)
        return demo_command_result("demo mpv stop", stdout="Playback stopped")
    save_resume_position()
    return mpv_command({"command": ["quit"]})


def pause_playback() -> dict:
    if is_demo_mode():
        config = load_config()
        current = bool(config["demo"]["playback"].get("paused"))
        config["demo"]["playback"]["paused"] = not current
        save_config(config)
        return demo_command_result("demo mpv pause", stdout="Playback toggled")
    return mpv_command({"command": ["cycle", "pause"]})


def seek_relative(seconds: int) -> dict:
    if is_demo_mode():
        config = load_config()
        playback = config["demo"]["playback"]
        duration = int(playback.get("duration", 0) or 0)
        current = int(playback.get("time_pos", 0) or 0)
        target = max(0, current + seconds)
        if duration:
            target = min(duration, target)
        playback["time_pos"] = target
        save_config(config)
        return demo_command_result("demo mpv seek", stdout=f"Seeked to {target}s")
    return mpv_command({"command": ["seek", seconds, "relative"]})


def load_settings() -> dict:
    return load_config()


def update_settings(section: str, values: dict) -> dict:
    config = load_config()
    config.setdefault(section, {})
    config[section].update(values)
    save_config(config)
    return config
