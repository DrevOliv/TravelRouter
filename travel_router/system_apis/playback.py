import json
import socket
import subprocess
from pathlib import Path

from ..config_store import load_config, save_config
from ..env import is_demo_mode
from .jellyfin import jellyfin_stream_url
from .run_command import command_result, demo_command_result


MPV_SOCKET = "/tmp/pi-travel-router-mpv.sock"


def play_jellyfin_item(item_id: str, resume: bool = True) -> dict:
    config = load_config()["jellyfin"]
    if not config["server_url"] or not config["api_key"]:
        return command_result("jellyfin play", stderr="Jellyfin server URL and API key are required.", ok=False)

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
    stream_plan = jellyfin_stream_url(item_id)
    if not stream_plan["ok"]:
        return command_result("jellyfin play", stderr=stream_plan["detail"], ok=False)

    start_time = load_resume_seconds(item_id) if resume else 0
    Path(MPV_SOCKET).unlink(missing_ok=True)
    subprocess.run(
        ["pkill", "-f", f"mpv --input-ipc-server={MPV_SOCKET}"],
        capture_output=True,
        text=True,
        check=False,
    )
    result = _spawn_mpv(stream_plan["url"], start_time)
    if result["ok"]:
        result["stdout"] = stream_plan["detail"]
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
    if start_time > 0:
        command.append(f"--start={start_time}")
    command.append(play_url)
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return command_result("mpv", stderr="Missing command: mpv", ok=False)

    return command_result("mpv", stdout="Playback started")


def mpv_command(payload: dict) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(MPV_SOCKET)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        response = sock.recv(4096).decode("utf-8").strip()
    except OSError as exc:
        return command_result("mpv-ipc", stderr=str(exc), ok=False)
    finally:
        sock.close()

    return command_result("mpv-ipc", stdout=response)


def mpv_get_property(property_name: str) -> dict:
    result = mpv_command({"command": ["get_property", property_name]})
    if not result["ok"]:
        return result

    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return command_result("mpv-ipc", stderr="Invalid mpv response", ok=False)

    if payload.get("error") != "success":
        return command_result("mpv-ipc", stderr=payload.get("error", "mpv error"), ok=False)

    response = command_result("mpv-ipc", stdout=result["stdout"])
    response["data"] = payload.get("data")
    return response


def mpv_set_property(property_name: str, value) -> dict:
    result = mpv_command({"command": ["set_property", property_name, value]})
    if not result["ok"]:
        return result
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return command_result("mpv-ipc", stderr="Invalid mpv response", ok=False)
    if payload.get("error") != "success":
        return command_result("mpv-ipc", stderr=payload.get("error", "mpv error"), ok=False)
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
        return command_result("resume-save", stdout="No active item")

    time_pos = mpv_get_property("time-pos")
    duration = mpv_get_property("duration")
    if not time_pos["ok"]:
        return time_pos

    seconds = int(float(time_pos.get("data") or 0))
    total = int(float(duration.get("data") or 0)) if duration["ok"] and duration.get("data") else 0
    if total and seconds >= max(total - 60, 0):
        seconds = 0
    update_playback_state(active_item_id, seconds)
    return command_result("resume-save", stdout=f"Saved resume at {seconds}s")


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
