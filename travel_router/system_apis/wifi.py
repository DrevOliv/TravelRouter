import io
import json
import os

from ..env import is_demo_mode
from .command import command_result, demo_command_result, run_command
from .config import demo_state, load_settings, update_demo, update_settings


DNSMASQ_LEASES_PATH = "/var/lib/misc/dnsmasq.leases"
NM_DNSMASQ_LEASES_TEMPLATE = "/var/lib/nm-dnsmasq-{interface}.leases"
AP_CONNECTION_NAME = "MyHotspot"


def reload_ap_connection(profile_name: str) -> dict:
    down_result = run_command(["sudo", "nmcli", "con", "down", profile_name])
    up_result = run_command(["sudo", "nmcli", "con", "up", profile_name])
    if up_result["ok"]:
        return up_result
    if down_result["ok"]:
        return up_result
    return down_result if not down_result["ok"] else up_result


def apply_ap_ssid(ap_ssid: str) -> dict:
    if is_demo_mode():
        update_settings("wifi", {"ap_ssid": ap_ssid})
        return demo_command_result("demo ap ssid", stdout=f"AP SSID updated to {ap_ssid}")

    modify = run_command(["sudo", "nmcli", "con", "modify", AP_CONNECTION_NAME, "802-11-wireless.ssid", ap_ssid])
    if not modify["ok"]:
        return modify

    restart = reload_ap_connection(AP_CONNECTION_NAME)
    if not restart["ok"]:
        return restart

    update_settings("wifi", {"ap_ssid": ap_ssid})
    return command_result("nmcli ap ssid update", stdout=f"AP SSID updated to {ap_ssid}")


def apply_ap_password(ap_password: str) -> dict:
    if len(ap_password) < 8:
        return command_result("nmcli ap password update", stderr="Password must be at least 8 characters.", ok=False)

    if is_demo_mode():
        update_settings("wifi", {"ap_password": ap_password})
        return demo_command_result("demo ap password", stdout="AP password updated")

    modify = run_command(["sudo", "nmcli", "con", "modify", AP_CONNECTION_NAME, "802-11-wireless-security.psk", ap_password])
    if not modify["ok"]:
        return modify

    restart = reload_ap_connection(AP_CONNECTION_NAME)
    if not restart["ok"]:
        return restart

    update_settings("wifi", {"ap_password": ap_password})
    return command_result("nmcli ap password update", stdout="AP password updated")


def wifi_qr_payload(ssid: str, password: str) -> str:
    escaped_ssid = ssid.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace(":", r"\:")
    escaped_password = password.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace(":", r"\:")
    return f"WIFI:T:WPA;S:{escaped_ssid};P:{escaped_password};;"


def wifi_qr_svg(ssid: str, password: str) -> str:
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 280" role="img" aria-label="QR unavailable">'
            '<rect width="280" height="280" rx="24" fill="#fffaf2"/>'
            '<text x="140" y="132" text-anchor="middle" font-size="18" fill="#1f2a30">QR library missing</text>'
            '<text x="140" y="158" text-anchor="middle" font-size="14" fill="#6d776f">Install requirements.txt</text>'
            "</svg>"
        )

    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(wifi_qr_payload(ssid, password))
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def scan_wifi(interface: str) -> dict:
    if is_demo_mode():
        rows = []
        for network in demo_state()["wifi_networks"]:
            rows.append(f"{network['ssid']}:{network['signal']}:{network['security']}")
        return demo_command_result(f"demo wifi scan {interface}", stdout="\n".join(rows))

    result = run_command(["sudo", "nmcli", "device", "wifi", "rescan", "ifname", interface  ])
    if not result["ok"]:
        return result
    return run_command(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", interface])


def connect_wifi(interface: str, ssid: str, password: str | None) -> dict:
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

    command = ["sudo", "nmcli", "dev", "wifi", "connect", ssid, "ifname", interface]
    if password:
        command.extend(["password", password])
    return run_command(command)


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


def current_wifi(interface: str) -> dict:
    if is_demo_mode():
        current = demo_state()["wifi_current"]
        return {"ok": True, **current}

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


def ap_connected_devices(interface: str) -> list[dict]:
    if is_demo_mode():
        devices = demo_state().get("ap_clients", [])
        return sorted(devices, key=lambda device: ((device.get("name") or "").lower(), device.get("ip") or ""))

    lease_map = {}
    lease_paths = [NM_DNSMASQ_LEASES_TEMPLATE.format(interface=interface), DNSMASQ_LEASES_PATH]
    lease_path = next((path for path in lease_paths if os.path.exists(path)), "")
    if lease_path:
        try:
            with open(lease_path, "r", encoding="utf-8") as handle:
                rows = handle.read().splitlines()
            for row in rows:
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

    result = run_command(["ip", "-j", "neigh", "show", "dev", interface])
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
