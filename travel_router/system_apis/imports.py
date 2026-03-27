from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config_store import load_config
from ..env import is_demo_mode
from .command import command_result, demo_command_result, run_command
from .config import demo_state, load_settings, update_demo, update_settings


PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".webp",
    ".tif",
    ".tiff",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".raf",
    ".rw2",
}
PROGRESS_PATTERN = re.compile(r"^\s*([\d,]+)\s+(\d+)%\s+([0-9.]+)([kMGT]?)(?:i?B|B)/s")
RETRY_LIMIT = 5
RETRY_DELAYS = [15, 30, 60, 120, 300]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def app_state_root() -> Path:
    preferred = Path("/var/lib/pi-travel-router")
    if preferred.exists() and os.access(preferred, os.W_OK | os.X_OK):
        return preferred

    fallback = Path(__file__).resolve().parent.parent.parent / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def import_mount_root() -> Path:
    root = app_state_root() / "import_mounts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_runtime_root() -> Path:
    root = app_state_root() / "import_runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_manifest_root() -> Path:
    root = import_runtime_root() / "manifests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_jobs_path() -> Path:
    return import_runtime_root() / "import_jobs.json"


def known_hosts_path() -> Path:
    path = import_runtime_root() / "known_hosts"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    return path


def normalize_relative_path(raw_path: str | None) -> str:
    value = (raw_path or "").replace("\\", "/").strip().strip("/")
    if not value:
        return ""

    parts = [part for part in value.split("/") if part and part not in {".", ".."}]
    return "/".join(parts)


def join_remote_path(base: str, child: str) -> str:
    clean_base = (base or "").strip().rstrip("/")
    clean_child = child.strip().strip("/")
    if clean_base and clean_child:
        return f"{clean_base}/{clean_child}"
    return clean_base or clean_child


def ensure_import_dirs() -> None:
    import_mount_root()
    import_runtime_root()
    import_manifest_root()
    known_hosts_path()


def transfer_settings_summary() -> dict:
    transfer = load_settings().get("transfer", {})
    auth_mode = (transfer.get("auth_mode") or "ssh_key").strip() or "ssh_key"
    has_password = bool(transfer.get("password"))
    has_key = bool(transfer.get("private_key_path"))
    configured = bool(
        transfer.get("host", "").strip()
        and transfer.get("username", "").strip()
        and ((auth_mode == "password" and has_password) or (auth_mode == "ssh_key" and has_key))
    )
    return {
        "host": transfer.get("host", "").strip(),
        "port": int(transfer.get("port", 22) or 22),
        "username": transfer.get("username", "").strip(),
        "auth_mode": auth_mode,
        "private_key_path": transfer.get("private_key_path", "").strip(),
        "last_destination_path": transfer.get("last_destination_path", "").strip(),
        "configured": configured,
        "has_password": has_password,
    }


def sanitize_device_label(device: dict) -> str:
    return (
        device.get("label")
        or device.get("model")
        or device.get("name")
        or Path(device.get("device_path", "")).name
        or "Removable storage"
    )


def _parse_lsblk_entry(entry: dict, inherited_removable: bool = False) -> list[dict]:
    removable = inherited_removable or bool(entry.get("rm")) or bool(entry.get("hotplug")) or entry.get("tran") in {"usb", "mmc"}
    children = entry.get("children") or []
    entries = []

    if removable and entry.get("type") in {"part", "disk"} and (entry.get("type") == "part" or not children):
        entries.append(
            {
                "device_path": entry.get("path") or "",
                "name": entry.get("name") or "",
                "label": entry.get("label") or "",
                "model": entry.get("model") or "",
                "size": entry.get("size") or "",
                "fstype": entry.get("fstype") or "",
                "mounted": bool(entry.get("mountpoint")),
                "mount_path": entry.get("mountpoint") or "",
            }
        )

    for child in children:
        entries.extend(_parse_lsblk_entry(child, removable))
    return entries


def list_import_devices() -> list[dict]:
    if is_demo_mode():
        devices = []
        for device in demo_state().get("imports", {}).get("devices", []):
            devices.append(
                {
                    "device_path": device.get("device_path", ""),
                    "name": Path(device.get("device_path", "")).name,
                    "label": device.get("label", "") or Path(device.get("device_path", "")).name,
                    "size": device.get("size", ""),
                    "fstype": device.get("fstype", ""),
                    "mounted": bool(device.get("mounted")),
                    "mount_path": device.get("mount_path", ""),
                }
            )
        return sorted(devices, key=lambda item: item.get("label", "").lower())

    result = run_command(["lsblk", "-J", "-o", "NAME,PATH,RM,HOTPLUG,TYPE,SIZE,LABEL,FSTYPE,MOUNTPOINT,MODEL,TRAN"])
    if not result["ok"]:
        return []
    try:
        payload = json.loads(result["stdout"] or "{}")
    except json.JSONDecodeError:
        return []

    devices = []
    for entry in payload.get("blockdevices") or []:
        devices.extend(_parse_lsblk_entry(entry))
    return sorted([device for device in devices if device.get("device_path")], key=lambda item: item.get("label", "").lower())


def get_import_device(device_path: str) -> dict | None:
    for device in list_import_devices():
        if device.get("device_path") == device_path:
            return device
    return None


def managed_mount_path(device_path: str) -> Path:
    return import_mount_root() / Path(device_path).name


def resolve_device_mount(device_path: str) -> str:
    if is_demo_mode():
        device = get_import_device(device_path)
        return device.get("mount_path", "") if device else ""

    result = run_command(["findmnt", "-nr", "-S", device_path, "-o", "TARGET"])
    if result["ok"] and result["stdout"]:
        return result["stdout"].splitlines()[0].strip()

    device = get_import_device(device_path)
    return device.get("mount_path", "") if device else ""


def mount_import_device(device_path: str) -> dict:
    if is_demo_mode():
        state = demo_state().get("imports", {})
        devices = state.get("devices", [])
        mount_path = f"/demo/imports/{Path(device_path).name}"
        updated = []
        found = False
        for device in devices:
            if device.get("device_path") == device_path:
                found = True
                updated.append({**device, "mounted": True, "mount_path": mount_path})
            else:
                updated.append(device)
        if not found:
            return demo_command_result("demo import mount", stderr="Device not found", ok=False)
        update_demo("imports", {"devices": updated})
        return demo_command_result("demo import mount", stdout=f"Mounted {device_path}")

    device = get_import_device(device_path)
    if not device:
        return command_result("mount import device", stderr="Removable device not found", ok=False)

    existing_mount = resolve_device_mount(device_path)
    if existing_mount:
        return command_result("mount import device", stdout=f"Already mounted at {existing_mount}")

    target = managed_mount_path(device_path)
    target.mkdir(parents=True, exist_ok=True)
    return run_command(["sudo", "mount", "-o", "ro", device_path, str(target)], timeout=30)


def unmount_import_device(device_path: str) -> dict:
    if is_demo_mode():
        state = demo_state().get("imports", {})
        devices = state.get("devices", [])
        updated = []
        found = False
        for device in devices:
            if device.get("device_path") == device_path:
                found = True
                updated.append({**device, "mounted": False, "mount_path": ""})
            else:
                updated.append(device)
        if not found:
            return demo_command_result("demo import unmount", stderr="Device not found", ok=False)
        update_demo("imports", {"devices": updated})
        return demo_command_result("demo import unmount", stdout=f"Unmounted {device_path}")

    mount_path = resolve_device_mount(device_path)
    if not mount_path:
        return command_result("unmount import device", stdout="Device is not mounted")
    result = run_command(["sudo", "umount", mount_path], timeout=30)
    target = managed_mount_path(device_path)
    if result["ok"] and target.exists():
        try:
            target.rmdir()
        except OSError:
            pass
    return result


def photo_file(name: str) -> bool:
    return Path(name).suffix.lower() in PHOTO_EXTENSIONS


def safe_browse_path(root: Path, relative_path: str) -> Path:
    candidate = (root / normalize_relative_path(relative_path)).resolve()
    candidate.relative_to(root.resolve())
    return candidate


def import_breadcrumbs(relative_path: str) -> list[dict]:
    crumbs = [{"name": "SD card", "path": ""}]
    parts = [part for part in normalize_relative_path(relative_path).split("/") if part]
    current = []
    for part in parts:
        current.append(part)
        crumbs.append({"name": part, "path": "/".join(current)})
    return crumbs


def browse_import_source(device_path: str, relative_path: str = "") -> dict:
    relative_path = normalize_relative_path(relative_path)
    if is_demo_mode():
        state = demo_state().get("imports", {})
        device = get_import_device(device_path)
        if not device or not device.get("mounted"):
            return {"ok": False, "error": "Mount the SD card first.", "current_path": "", "directories": [], "files": [], "breadcrumbs": []}

        tree = state.get("tree", {})
        branch = tree.get(relative_path)
        if branch is None:
            return {"ok": False, "error": "Folder not found.", "current_path": relative_path, "directories": [], "files": [], "breadcrumbs": import_breadcrumbs(relative_path)}

        directories = [
            {"name": name, "relative_path": normalize_relative_path(f"{relative_path}/{name}"), "size_bytes": 0}
            for name in branch.get("directories", [])
        ]
        files = [
            {"name": item["name"], "relative_path": item["name"], "size_bytes": int(item.get("size_bytes", 0))}
            for item in branch.get("files", [])
            if photo_file(item.get("name", ""))
        ]
        return {
            "ok": True,
            "error": "",
            "current_path": relative_path,
            "directories": directories,
            "files": files,
            "breadcrumbs": import_breadcrumbs(relative_path),
        }

    mount_path = resolve_device_mount(device_path)
    if not mount_path:
        return {"ok": False, "error": "Mount the SD card first.", "current_path": "", "directories": [], "files": [], "breadcrumbs": []}

    root = Path(mount_path).resolve()
    try:
        current = safe_browse_path(root, relative_path)
    except (OSError, ValueError):
        return {"ok": False, "error": "Invalid folder path.", "current_path": "", "directories": [], "files": [], "breadcrumbs": []}

    if not current.exists() or not current.is_dir():
        return {"ok": False, "error": "Folder not found.", "current_path": relative_path, "directories": [], "files": [], "breadcrumbs": import_breadcrumbs(relative_path)}

    directories = []
    files = []
    for child in sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if child.name.startswith("."):
            continue
        relative = str(child.relative_to(root)).replace(os.sep, "/")
        if child.is_dir():
            directories.append({"name": child.name, "relative_path": relative, "size_bytes": 0})
            continue
        if child.is_file() and photo_file(child.name):
            try:
                size_bytes = int(child.stat().st_size)
            except OSError:
                size_bytes = 0
            files.append({"name": child.name, "relative_path": child.name, "size_bytes": size_bytes})

    return {
        "ok": True,
        "error": "",
        "current_path": relative_path,
        "directories": directories,
        "files": files,
        "breadcrumbs": import_breadcrumbs(relative_path),
    }


def _folder_stats_demo(relative_path: str) -> tuple[int, int]:
    tree = demo_state().get("imports", {}).get("tree", {})
    total_files = 0
    total_bytes = 0
    for path, branch in tree.items():
        if path == relative_path or path.startswith(f"{relative_path}/"):
            for item in branch.get("files", []):
                if photo_file(item.get("name", "")):
                    total_files += 1
                    total_bytes += int(item.get("size_bytes", 0))
    return total_files, total_bytes


def folder_import_stats(device_path: str, relative_path: str) -> dict:
    relative_path = normalize_relative_path(relative_path)
    if not relative_path:
        return {"ok": False, "error": "Choose a folder first."}

    if is_demo_mode():
        total_files, total_bytes = _folder_stats_demo(relative_path)
        return {
            "ok": total_files > 0,
            "error": "" if total_files > 0 else "No photos found in that folder.",
            "source_name": Path(relative_path).name,
            "total_files": total_files,
            "total_bytes": total_bytes,
        }

    mount_path = resolve_device_mount(device_path)
    if not mount_path:
        return {"ok": False, "error": "Mount the SD card first."}
    root = Path(mount_path).resolve()
    try:
        folder_path = safe_browse_path(root, relative_path)
    except (OSError, ValueError):
        return {"ok": False, "error": "Folder not found."}
    if not folder_path.exists() or not folder_path.is_dir():
        return {"ok": False, "error": "Folder not found."}

    total_files = 0
    total_bytes = 0
    for child in folder_path.rglob("*"):
        if child.is_file() and photo_file(child.name):
            total_files += 1
            try:
                total_bytes += int(child.stat().st_size)
            except OSError:
                pass

    return {
        "ok": total_files > 0,
        "error": "" if total_files > 0 else "No photos found in that folder.",
        "source_name": folder_path.name,
        "total_files": total_files,
        "total_bytes": total_bytes,
    }


def file_import_stats(device_path: str, source_dir: str, selected_files: list[str]) -> dict:
    source_dir = normalize_relative_path(source_dir)
    files = [Path(name).name for name in selected_files if Path(name).name]
    if not files:
        return {"ok": False, "error": "Choose at least one photo."}

    if is_demo_mode():
        tree = demo_state().get("imports", {}).get("tree", {})
        branch = tree.get(source_dir, {})
        file_map = {item["name"]: int(item.get("size_bytes", 0)) for item in branch.get("files", [])}
        valid = [name for name in files if name in file_map and photo_file(name)]
        total_bytes = sum(file_map[name] for name in valid)
        return {
            "ok": bool(valid),
            "error": "" if valid else "No valid photos selected.",
            "source_name": Path(source_dir).name or "SD card",
            "selected_files": valid,
            "total_files": len(valid),
            "total_bytes": total_bytes,
        }

    mount_path = resolve_device_mount(device_path)
    if not mount_path:
        return {"ok": False, "error": "Mount the SD card first."}
    root = Path(mount_path).resolve()
    try:
        folder_path = safe_browse_path(root, source_dir)
    except (OSError, ValueError):
        return {"ok": False, "error": "Folder not found."}
    if not folder_path.exists() or not folder_path.is_dir():
        return {"ok": False, "error": "Folder not found."}

    valid = []
    total_bytes = 0
    for name in files:
        file_path = (folder_path / name).resolve()
        try:
            file_path.relative_to(folder_path.resolve())
        except ValueError:
            continue
        if not file_path.is_file() or not photo_file(file_path.name):
            continue
        valid.append(file_path.name)
        try:
            total_bytes += int(file_path.stat().st_size)
        except OSError:
            pass

    return {
        "ok": bool(valid),
        "error": "" if valid else "No valid photos selected.",
        "source_name": Path(source_dir).name or "SD card",
        "selected_files": valid,
        "total_files": len(valid),
        "total_bytes": total_bytes,
    }


def _run_secure_command(command: list[str], env: dict | None = None, timeout: int = 20) -> dict:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError:
        return command_result(" ".join(shlex.quote(part) for part in command), stderr=f"Missing command: {command[0]}", ok=False)
    except subprocess.TimeoutExpired:
        return command_result(" ".join(shlex.quote(part) for part in command), stderr="Command timed out", ok=False)

    return command_result(
        " ".join(shlex.quote(part) for part in command),
        stdout=(completed.stdout or "").strip(),
        stderr=(completed.stderr or "").strip(),
        ok=completed.returncode == 0,
    )


def build_ssh_context(settings: dict) -> tuple[list[str], dict]:
    transfer = settings.get("transfer", {}) if "transfer" in settings else settings
    auth_mode = (transfer.get("auth_mode") or "ssh_key").strip() or "ssh_key"
    base = [
        "ssh",
        "-p",
        str(int(transfer.get("port", 22) or 22)),
        "-o",
        f"UserKnownHostsFile={known_hosts_path()}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=6",
    ]
    if auth_mode == "ssh_key" and transfer.get("private_key_path", "").strip():
        base.extend(["-i", transfer["private_key_path"].strip()])

    env = os.environ.copy()
    if auth_mode == "password":
        env["SSHPASS"] = transfer.get("password", "")
        return ["sshpass", "-e", *base], env
    return base, env


def build_rsync_ssh_command(settings: dict) -> tuple[str, dict]:
    ssh_command, env = build_ssh_context(settings)
    return " ".join(shlex.quote(part) for part in ssh_command), env


def transfer_destination_test() -> dict:
    settings = load_settings()
    summary = transfer_settings_summary()
    if not summary["configured"]:
        return command_result("transfer test", stderr="Configure the TrueNAS connection first.", ok=False)
    if is_demo_mode():
        return demo_command_result("demo transfer test", stdout="connected")

    ssh_command, env = build_ssh_context(settings)
    target = f"{summary['username']}@{summary['host']}"
    return _run_secure_command([*ssh_command, target, "printf", "connected"], env=env, timeout=20)


def save_import_jobs(jobs: list[dict]) -> None:
    path = import_jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(jobs, handle, indent=2)


def load_import_jobs() -> list[dict]:
    path = import_jobs_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def parse_speed_to_bps(speed_value: str, unit: str) -> int:
    multiplier = {
        "": 1,
        "k": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }.get(unit or "", 1)
    try:
        return int(float(speed_value) * multiplier)
    except ValueError:
        return 0


class ImportJobManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._jobs: list[dict] = []
        self._active_process: subprocess.Popen[str] | None = None
        self._active_job_id = ""
        self._last_persist: dict[str, float] = {}

    def start(self) -> None:
        ensure_import_dirs()
        with self._lock:
            self._jobs = load_import_jobs()
            changed = False
            for job in self._jobs:
                if job.get("status") in {"running", "verifying"}:
                    job["status"] = "waiting_retry"
                    job["phase"] = "waiting"
                    job["error"] = "Upload was interrupted and will resume."
                    job["next_retry_at"] = utc_now_iso()
                    changed = True
            if changed:
                save_import_jobs(self._jobs)
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="import-job-worker", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        with self._lock:
            if self._active_process and self._active_process.poll() is None:
                self._active_process.terminate()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return sorted((dict(job) for job in self._jobs), key=lambda item: item.get("created_at", ""), reverse=True)

    def enqueue_folder(self, device_path: str, source_path: str, destination_path: str) -> dict:
        stats = folder_import_stats(device_path, source_path)
        if not stats["ok"]:
            return {"ok": False, "error": stats.get("error", "Could not prepare folder import.")}

        destination = destination_path.strip()
        if not destination:
            return {"ok": False, "error": "Choose a destination path first."}

        update_settings("transfer", {"last_destination_path": destination})
        job = {
            "id": uuid.uuid4().hex[:12],
            "kind": "folder",
            "device_path": device_path,
            "source_path": normalize_relative_path(source_path),
            "selected_files": [],
            "source_name": stats["source_name"],
            "destination_path": destination,
            "status": "queued",
            "phase": "queued",
            "total_files": int(stats["total_files"]),
            "total_bytes": int(stats["total_bytes"]),
            "bytes_sent": 0,
            "speed_bps": 0,
            "progress_percent": 0,
            "retries": 0,
            "error": "",
            "last_output": "",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "next_retry_at": "",
            "cancel_requested": False,
        }
        self._add_job(job)
        return {"ok": True, "job": job}

    def enqueue_files(self, device_path: str, source_path: str, selected_files: list[str], destination_path: str) -> dict:
        stats = file_import_stats(device_path, source_path, selected_files)
        if not stats["ok"]:
            return {"ok": False, "error": stats.get("error", "Could not prepare file import.")}

        destination = destination_path.strip()
        if not destination:
            return {"ok": False, "error": "Choose a destination path first."}

        update_settings("transfer", {"last_destination_path": destination})
        job = {
            "id": uuid.uuid4().hex[:12],
            "kind": "files",
            "device_path": device_path,
            "source_path": normalize_relative_path(source_path),
            "selected_files": list(stats["selected_files"]),
            "source_name": stats["source_name"],
            "destination_path": destination,
            "status": "queued",
            "phase": "queued",
            "total_files": int(stats["total_files"]),
            "total_bytes": int(stats["total_bytes"]),
            "bytes_sent": 0,
            "speed_bps": 0,
            "progress_percent": 0,
            "retries": 0,
            "error": "",
            "last_output": "",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "next_retry_at": "",
            "cancel_requested": False,
        }
        self._add_job(job)
        return {"ok": True, "job": job}

    def retry_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._find_job(job_id)
            if not job:
                return False
            job.update(
                {
                    "status": "queued",
                    "phase": "queued",
                    "error": "",
                    "next_retry_at": "",
                    "cancel_requested": False,
                    "updated_at": utc_now_iso(),
                }
            )
            save_import_jobs(self._jobs)
        self._wake_event.set()
        return True

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._find_job(job_id)
            if not job:
                return False
            job["cancel_requested"] = True
            job["updated_at"] = utc_now_iso()
            if job.get("status") not in {"running", "verifying"}:
                job["status"] = "cancelled"
                job["phase"] = "cancelled"
            save_import_jobs(self._jobs)
            if self._active_job_id == job_id and self._active_process and self._active_process.poll() is None:
                self._active_process.terminate()
        self._wake_event.set()
        return True

    def _add_job(self, job: dict) -> None:
        with self._lock:
            self._jobs.append(job)
            save_import_jobs(self._jobs)
        self._wake_event.set()

    def _find_job(self, job_id: str) -> dict | None:
        for job in self._jobs:
            if job.get("id") == job_id:
                return job
        return None

    def _persist_jobs(self) -> None:
        with self._lock:
            save_import_jobs(self._jobs)

    def _update_job(self, job_id: str, *, persist: bool = True, **values) -> dict | None:
        with self._lock:
            job = self._find_job(job_id)
            if not job:
                return None
            job.update(values)
            job["updated_at"] = utc_now_iso()
            if persist:
                save_import_jobs(self._jobs)
            return dict(job)

    def _throttled_progress_update(self, job_id: str, **values) -> None:
        now = time.monotonic()
        persist = now - self._last_persist.get(job_id, 0) > 0.9
        if persist:
            self._last_persist[job_id] = now
        self._update_job(job_id, persist=persist, **values)

    def _next_job(self) -> dict | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            candidates = []
            for job in self._jobs:
                if job.get("status") not in {"queued", "waiting_retry", "waiting_source"}:
                    continue
                next_retry = job.get("next_retry_at", "")
                if next_retry:
                    try:
                        retry_time = datetime.fromisoformat(next_retry)
                    except ValueError:
                        retry_time = now
                    if retry_time > now:
                        continue
                candidates.append(job)
            candidates.sort(key=lambda item: item.get("created_at", ""))
            return dict(candidates[0]) if candidates else None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self._next_job()
            if not job:
                self._wake_event.wait(timeout=1.0)
                self._wake_event.clear()
                continue
            self._process_job(job["id"])

    def _process_job(self, job_id: str) -> None:
        job = self._update_job(job_id, status="running", phase="preparing", error="", next_retry_at="", speed_bps=0)
        if not job:
            return

        if is_demo_mode():
            self._process_demo_job(job_id)
            return

        settings = load_settings()
        transfer = transfer_settings_summary()
        if not transfer["configured"]:
            self._update_job(job_id, status="failed", phase="failed", error="Configure the TrueNAS transfer settings first.")
            return

        mount_result = mount_import_device(job["device_path"])
        mount_path = resolve_device_mount(job["device_path"])
        if not mount_result["ok"] and not mount_path:
            self._schedule_retry(job_id, "SD card is not mounted or could not be mounted.", source_missing=True)
            return

        try:
            local_source, remote_target, manifest_path = self._prepare_job_paths(job_id, mount_path)
        except FileNotFoundError:
            self._schedule_retry(job_id, "The selected SD card folder is unavailable.", source_missing=True)
            return
        except ValueError as error:
            self._update_job(job_id, status="failed", phase="failed", error=str(error))
            return

        mkdir_result = self._ensure_remote_path(settings, remote_target)
        if not mkdir_result["ok"]:
            self._schedule_retry(job_id, mkdir_result["stderr"] or mkdir_result["stdout"] or "Could not create the destination path.")
            return

        upload_result = self._run_upload(job_id, settings, local_source, remote_target, manifest_path)
        if not upload_result["ok"]:
            if self._job_cancelled(job_id):
                self._update_job(job_id, status="cancelled", phase="cancelled", error="Upload cancelled.", speed_bps=0)
                return
            self._schedule_retry(job_id, upload_result["stderr"] or upload_result["stdout"] or "Upload failed.")
            return

        self._update_job(job_id, status="verifying", phase="verifying", speed_bps=0, bytes_sent=int(job.get("total_bytes", 0)), progress_percent=100)
        verify_result = self._run_verify(job_id, settings, local_source, remote_target, manifest_path)
        if not verify_result["ok"]:
            self._schedule_retry(job_id, verify_result["stderr"] or verify_result["stdout"] or "Verification failed.")
            return

        self._update_job(
            job_id,
            status="completed",
            phase="completed",
            error="",
            speed_bps=0,
            bytes_sent=int(job.get("total_bytes", 0)),
            progress_percent=100,
            last_output="Verified",
        )

    def _process_demo_job(self, job_id: str) -> None:
        job = self._find_job(job_id)
        if not job:
            return
        total = max(int(job.get("total_bytes", 0)), 1)
        bytes_sent = int(job.get("bytes_sent", 0))
        while bytes_sent < total and not self._stop_event.is_set():
            if self._job_cancelled(job_id):
                self._update_job(job_id, status="cancelled", phase="cancelled", error="Upload cancelled.", speed_bps=0)
                return
            bytes_sent = min(total, bytes_sent + max(total // 10, 256000))
            progress = min(100, int((bytes_sent / total) * 100))
            self._throttled_progress_update(
                job_id,
                status="running",
                phase="uploading",
                bytes_sent=bytes_sent,
                progress_percent=progress,
                speed_bps=max(total // 8, 350000),
                last_output="Demo upload running",
            )
            time.sleep(0.5)
        self._update_job(job_id, status="verifying", phase="verifying", speed_bps=0)
        time.sleep(0.6)
        self._update_job(job_id, status="completed", phase="completed", bytes_sent=total, progress_percent=100, speed_bps=0, last_output="Verified")

    def _prepare_job_paths(self, job_id: str, mount_path: str) -> tuple[str, str, str]:
        job = self._find_job(job_id)
        if not job:
            raise ValueError("Job not found.")

        mount_root = Path(mount_path).resolve()
        source_path = normalize_relative_path(job.get("source_path", ""))
        source_dir = safe_browse_path(mount_root, source_path)
        if not source_dir.exists():
            raise FileNotFoundError("Source folder missing")

        destination_path = job.get("destination_path", "").strip()
        if not destination_path:
            raise ValueError("Destination path is required.")

        manifest_path = ""
        if job.get("kind") == "folder":
            local_source = f"{source_dir}/"
            remote_target = join_remote_path(destination_path, Path(source_dir).name)
        else:
            local_source = f"{source_dir}/"
            remote_target = destination_path
            manifest_file = import_manifest_root() / f"{job_id}.txt"
            manifest_file.write_text("\n".join(job.get("selected_files", [])) + "\n", encoding="utf-8")
            manifest_path = str(manifest_file)
        return str(local_source), remote_target, manifest_path

    def _ensure_remote_path(self, settings: dict, remote_target: str) -> dict:
        summary = transfer_settings_summary()
        ssh_command, env = build_ssh_context(settings)
        target = f"{summary['username']}@{summary['host']}"
        mkdir_command = f"mkdir -p -- {shlex.quote(remote_target)}"
        return _run_secure_command([*ssh_command, target, mkdir_command], env=env, timeout=30)

    def _run_upload(self, job_id: str, settings: dict, local_source: str, remote_target: str, manifest_path: str) -> dict:
        summary = transfer_settings_summary()
        ssh_command, env = build_rsync_ssh_command(settings)
        remote_spec = f"{summary['username']}@{summary['host']}:{shlex.quote(remote_target)}"
        command = [
            "rsync",
            "-rlt",
            "--partial",
            "--append-verify",
            "--info=progress2,stats",
            "-e",
            ssh_command,
        ]
        if manifest_path:
            command.append(f"--files-from={manifest_path}")
        if settings.get("transfer", {}).get("auth_mode") == "password":
            command = ["sshpass", "-e", *command]

        command.extend([local_source, remote_spec])
        return self._stream_process(job_id, command, env=env)

    def _run_verify(self, job_id: str, settings: dict, local_source: str, remote_target: str, manifest_path: str) -> dict:
        summary = transfer_settings_summary()
        ssh_command, env = build_rsync_ssh_command(settings)
        remote_spec = f"{summary['username']}@{summary['host']}:{shlex.quote(remote_target)}"
        command = [
            "rsync",
            "-rltc",
            "-n",
            "--out-format=%n",
            "-e",
            ssh_command,
        ]
        if manifest_path:
            command.append(f"--files-from={manifest_path}")
        if settings.get("transfer", {}).get("auth_mode") == "password":
            command = ["sshpass", "-e", *command]

        command.extend([local_source, remote_spec])
        result = _run_secure_command(command, env=env, timeout=120)
        if result["ok"] and result["stdout"]:
            result["ok"] = False
            result["stderr"] = f"Files differ after upload: {result['stdout'].splitlines()[0]}"
        return result

    def _stream_process(self, job_id: str, command: list[str], env: dict | None = None) -> dict:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )
        except FileNotFoundError:
            return command_result(" ".join(shlex.quote(part) for part in command), stderr=f"Missing command: {command[0]}", ok=False)

        with self._lock:
            self._active_process = process
            self._active_job_id = job_id

        command_text = " ".join(shlex.quote(part) for part in command)
        buffer = ""
        captured_lines: list[str] = []

        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(1)
            if chunk == "" and process.poll() is not None:
                if buffer.strip():
                    self._consume_progress_line(job_id, buffer.strip(), captured_lines)
                break
            if chunk in {"\r", "\n"}:
                if buffer.strip():
                    self._consume_progress_line(job_id, buffer.strip(), captured_lines)
                buffer = ""
                continue
            buffer += chunk
            if self._job_cancelled(job_id) and process.poll() is None:
                process.terminate()

        return_code = process.wait()
        with self._lock:
            self._active_process = None
            self._active_job_id = ""

        stdout = "\n".join(line for line in captured_lines[-20:] if line)
        return command_result(command_text, stdout=stdout, stderr="" if return_code == 0 else stdout, ok=return_code == 0)

    def _consume_progress_line(self, job_id: str, line: str, captured_lines: list[str]) -> None:
        if len(captured_lines) < 100:
            captured_lines.append(line)
        else:
            captured_lines.pop(0)
            captured_lines.append(line)

        match = PROGRESS_PATTERN.match(line)
        if not match:
            self._throttled_progress_update(job_id, phase="uploading", last_output=line)
            return

        bytes_sent = int(match.group(1).replace(",", ""))
        progress_percent = int(match.group(2))
        speed_bps = parse_speed_to_bps(match.group(3), match.group(4))
        self._throttled_progress_update(
            job_id,
            phase="uploading",
            bytes_sent=bytes_sent,
            progress_percent=progress_percent,
            speed_bps=speed_bps,
            last_output=line,
        )

    def _job_cancelled(self, job_id: str) -> bool:
        with self._lock:
            job = self._find_job(job_id)
            return bool(job and job.get("cancel_requested"))

    def _schedule_retry(self, job_id: str, message: str, source_missing: bool = False) -> None:
        with self._lock:
            job = self._find_job(job_id)
            if not job:
                return
            retries = int(job.get("retries", 0))
            if retries >= RETRY_LIMIT:
                job.update(
                    {
                        "status": "failed",
                        "phase": "failed",
                        "error": message,
                        "speed_bps": 0,
                        "next_retry_at": "",
                    }
                )
                save_import_jobs(self._jobs)
                return

            delay = RETRY_DELAYS[min(retries, len(RETRY_DELAYS) - 1)]
            next_retry = datetime.now(timezone.utc).timestamp() + delay
            job.update(
                {
                    "status": "waiting_source" if source_missing else "waiting_retry",
                    "phase": "waiting",
                    "error": message,
                    "retries": retries + 1,
                    "speed_bps": 0,
                    "next_retry_at": datetime.fromtimestamp(next_retry, timezone.utc).isoformat(),
                    "last_output": message,
                }
            )
            save_import_jobs(self._jobs)
        self._wake_event.set()


import_job_manager = ImportJobManager()
