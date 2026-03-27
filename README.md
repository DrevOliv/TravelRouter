# Pi Travel Router

A lightweight Raspberry Pi travel router and entertainment center built on Raspberry Pi OS Lite.

## Goals

- Join hotel or local Wi-Fi from the Pi
- Broadcast a private Wi-Fi network from a second adapter
- Route traffic through Tailscale, with optional exit-node usage
- Connect to a TV over HDMI and play Jellyfin media
- Control everything from a phone-friendly web UI

## Recommended software stack

### Base OS

- Raspberry Pi OS Lite (64-bit)

### Networking

- `network-manager`
- `hostapd`
- `dnsmasq`
- `iptables-persistent`

### VPN

- `tailscale`

### Media playback

- `mpv`
- `ffmpeg`

### Python web app

- `python3`
- `python3-venv`
- `python3-pip`

## Suggested hardware

- Raspberry Pi 4 or 5
- Official or reliable USB-C power supply
- MicroSD card or SSD
- Built-in Wi-Fi for upstream client mode
- Second USB Wi-Fi adapter for the private AP
- HDMI cable

## Network design

- `wlan0`: upstream/client interface for hotel or travel Wi-Fi
- `wlan1`: private access point for your own devices
- `eth0`: optional management port
- AP subnet: `192.168.50.0/24`
- Router IP: `192.168.50.1`

## Install packages

```bash
sudo apt update
sudo apt install -y network-manager dnsmasq iptables-persistent mpv ffmpeg python3 python3-venv python3-pip curl
curl -fsSL https://tailscale.com/install.sh | sh
```

## High-level setup steps

1. Keep Raspberry Pi OS Lite minimal.
2. Use `NetworkManager` for scanning and joining upstream Wi-Fi.
3. Use `hostapd` to broadcast your own SSID on `wlan1`.
4. Use `dnsmasq` to hand out DHCP leases on the private network.
5. Enable IPv4 forwarding and NAT from `wlan1` to `wlan0` or `tailscale0`.
6. Install Tailscale and authenticate the device.
7. Run this Flask app as a systemd service.
8. Open the web UI from your phone while connected to the Pi's private SSID.

## Example AP configuration

`/etc/hostapd/hostapd.conf`

```ini
country_code=SE
interface=wlan1
driver=nl80211
ssid=PiTravelHub
hw_mode=g
channel=6
wmm_enabled=1
auth_algs=1
wpa=2
wpa_passphrase=ChangeThisPassword
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Point `/etc/default/hostapd` at that file:

```ini
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

## Example dnsmasq configuration

`/etc/dnsmasq.d/travel-router.conf`

```ini
interface=wlan1
dhcp-range=192.168.50.100,192.168.50.200,255.255.255.0,24h
dhcp-option=3,192.168.50.1
dhcp-option=6,1.1.1.1,8.8.8.8
```

## Static IP for the AP interface

Use a NetworkManager profile or assign it manually:

```bash
sudo nmcli connection add type wifi ifname wlan1 con-name travel-ap autoconnect yes ssid PiTravelHub
sudo nmcli connection modify travel-ap 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method manual ipv4.addresses 192.168.50.1/24 ipv6.method disabled
```

If you prefer `hostapd` to own the SSID fully, just assign the address and skip the AP mode profile.

## Enable forwarding

`/etc/sysctl.d/99-travel-router.conf`

```ini
net.ipv4.ip_forward=1
```

Apply it:

```bash
sudo sysctl --system
```

## NAT rules

Use `iptables` to masquerade AP clients out through the current uplink:

```bash
sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
sudo iptables -A FORWARD -i wlan1 -o wlan0 -j ACCEPT
sudo iptables -A FORWARD -i wlan0 -o wlan1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo netfilter-persistent save
```

If you want forced VPN egress later, switch the outbound interface from `wlan0` to `tailscale0` or use routing rules managed by your app.

## Tailscale

Install and bring it up:

```bash
sudo tailscale up
```

Optional exit node:

```bash
sudo tailscale up --exit-node=<NODE_IP_OR_NAME>
```

If you run the Flask app as an unprivileged user, commands like `tailscale up` will need passwordless sudo for only the specific commands you allow. A tight sudoers example is:

```ini
pi ALL=(root) NOPASSWD: /usr/bin/tailscale, /usr/bin/systemctl, /usr/bin/nmcli
```

## Jellyfin playback approach in this project

This app does not run a full TV-first frontend. Instead it:

- connects to your Jellyfin server over HTTP or through Tailscale
- lets you browse media from your phone
- launches playback on the Raspberry Pi HDMI output using `mpv`
- exposes simple playback controls from the same web UI

This keeps the system smaller than a full Kodi appliance while still fitting the "travel router + entertainment box" use case.

## Run the app locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then open `http://<pi-ip>:8080`.

## Demo mode for Mac UI testing

If you want to test the full UI on your Mac without Raspberry Pi networking tools, use demo mode.

Edit `.env` in the project root:

```ini
DEMO_MODE=1
```

In demo mode:

- Wi-Fi scanning and connecting are mocked
- Tailscale exit node data and changes are mocked
- playback controls are mocked
- Jellyfin browsing stays real, so you can still browse your actual library

To go back to Raspberry Pi behavior, set:

```ini
DEMO_MODE=0
```

## Run as a service

Create `/etc/systemd/system/pi-travel-router.service`:

```ini
[Unit]
Description=Pi Travel Router Web UI
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
WorkingDirectory=/opt/pi-travel-router
ExecStart=/opt/pi-travel-router/.venv/bin/python /opt/pi-travel-router/app.py
Restart=always
User=pi
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Install it:

```bash
sudo mkdir -p /opt/pi-travel-router
sudo rsync -a ./ /opt/pi-travel-router/
cd /opt/pi-travel-router
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl daemon-reload
sudo systemctl enable --now pi-travel-router.service
```

## Notes

- Many hotel Wi-Fi networks use captive portals. The Pi may need a one-time browser login before routing works.
- Some USB Wi-Fi adapters do not support AP mode. Check before buying.
- You should lock down the web UI before exposing it beyond your private travel SSID.
