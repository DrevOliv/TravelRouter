import json
import subprocess


def list_drives() -> list[dict]:
    command = ["lsblk", "-J", "-o", "NAME,SIZE,LABEL,TRAN,TYPE,MOUNTPOINT,FSTYPE"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout or "{}")
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        return []

    drives = []
    for device in payload.get("blockdevices", []):
        if device.get("type") != "disk":
            continue

        partitions = []
        for child in device.get("children") or []:
            if child.get("type") != "part":
                continue
            partitions.append(
                {
                    "name": child.get("name", ""),
                    "size": child.get("size", ""),
                    "mountpoint": child.get("mountpoint"),
                    "fstype": child.get("fstype"),
                }
            )

        transport = str(device.get("tran") or "").lower() or None
        if transport not in {"usb", "sata", "nvme"}:
            transport = None

        drives.append(
            {
                "name": device.get("name", ""),
                "size": device.get("size", ""),
                "label": device.get("label"),
                "transport": transport,
                "partitions": partitions,
            }
        )

    return drives
