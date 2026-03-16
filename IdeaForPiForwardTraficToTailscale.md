Yes — what you’re describing is possible, but **not by giving real extra LAN IPs automatically through Tailscale itself**.
Instead, you simulate it using either:

1. **1:1 NAT / port forwarding on the Raspberry Pi**
2. **Proxy ARP / alias IPs on the Pi**
3. **DNS overrides (usually the cleanest)**

The idea is:

> A fake local IP on parents LAN → Raspberry Pi catches it → forwards to a chosen Tailscale/home device 🔁

---

# Option A — Give fake local IPs that forward to home devices (recommended) ⭐

Suppose:

* Parents LAN = `192.168.20.0/24`
* Pi = `192.168.20.5`
* Home server = `192.168.10.50`

You want:

```text id="8r4utl"
192.168.20.200 → actually goes to 192.168.10.50
```

---

## Add extra IP to Pi

On the Pi:

```bash id="7sn86c"
sudo ip addr add 192.168.20.200/24 dev eth0
```

Now Pi owns that IP.

---

## Forward traffic to home server

```bash id="0g9pr1"
sudo iptables -t nat -A PREROUTING -d 192.168.20.200 -j DNAT --to-destination 192.168.10.50
```

---

## Allow forwarding

```bash id="o1zk0e"
sudo iptables -A FORWARD -d 192.168.10.50 -j ACCEPT
```

---

## Masquerade into Tailscale

```bash id="s7ub6o"
sudo iptables -t nat -A POSTROUTING -o tailscale0 -j MASQUERADE
```

---

# Result

Now any device at parents house opens:

```text id="3h4uv0"
192.168.20.200
```

but traffic really goes to:

```text id="7d9w2r"
192.168.10.50
```

through Tailscale

---

# You can make many fake IPs

Example:

```text id="wh0sre"
192.168.20.200 → home NAS
192.168.20.201 → home camera
192.168.20.202 → home server
```

Each gets its own DNAT rule.

---

# Option B — Better than fake IPs: local DNS names 🧠

Instead of fake IPs:

Use names:

```text id="ht6y4z"
nas.home
server.home
camera.home
```

Parents router DNS points those names to Pi.

Pi forwards to home devices.

This is cleaner and easier to remember.

---

# Option C — Reverse proxy (best for web services)

If only web services:

Pi forwards:

```text id="4mpq6l"
nas.local → home NAS
plex.local → home server
```

using Nginx or Caddy

---

# Important limitation ⚠️

This only works reliably if:

Pi already has:

```bash id="g24c2u"
sysctl -w net.ipv4.ip_forward=1
```

and:

```bash id="pw3h6a"
iptables -t nat -A POSTROUTING -o tailscale0 -j MASQUERADE
```

---

# Very powerful setup ⭐

You can make parents LAN feel like home LAN:

```text id="5y5pkd"
192.168.20.200 = home NAS
192.168.20.201 = home server
192.168.20.202 = home printer
```

without touching each client.

---

# If you want, I can give you a **production-ready Raspberry Pi config where fake local IPs automatically map to your Tailscale/home devices permanently after reboot** 🚀
