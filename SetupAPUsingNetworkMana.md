Setting up a Raspberry Pi as an Access Point (AP) while simultaneously using another interface (like a secondary USB Wi-Fi dongle or Ethernet) to connect to the internet is a classic "Wireless Client + AP" or "Bridge" setup. 

Using **NetworkManager** (`nmcli`) is actually the smartest way to do this in 2026, as it handles the handoffs and interface management much more gracefully than the old `hostapd` manual configurations.

### Prerequisites
* **Hardware:** Ensure your Pi's built-in Wi-Fi supports **AP Mode** (the Pi 3, 4, 5, and Zero W all do).
* **Interfaces:** I'll assume `wlan0` is your AP and `eth0` (or `wlan1`) is your internet source.

---

### Step 1: Create the AP Profile
We will create a new connection profile specifically for the hotspot. Replace `MyPiAP` and `Password123` with your preferred credentials.

```bash
sudo nmcli con add type wifi ifname wlan0 mode ap con-name MyHotspot ssid MyPiAP
sudo nmcli con modify MyHotspot 802-11-wireless.band bg
sudo nmcli con modify MyHotspot 802-11-wireless-security.key-mgmt wpa-psk
sudo nmcli con modify MyHotspot 802-11-wireless-security.psk Password123
sudo nmcli con modify MyHotspot ipv4.method shared
```

**Why `ipv4.method shared`?** This is the "magic" setting in NetworkManager. It automatically starts a local DHCP server (dnsmasq) and sets up the NAT (Network Address Translation) rules so that devices connecting to your Pi can reach the internet via your other active interface.

---

### Step 2: Fine-Tuning for Stability
By default, NetworkManager might try to use `wlan0` to scan for other networks. We want it focused on being an AP.

1.  **Set a static IP for the Pi on the AP side (Optional but Recommended):**
    ```bash
    sudo nmcli con modify MyHotspot ipv4.addresses 192.168.50.1/24
    ```
2.  **Ensure it starts automatically:**
    ```bash
    sudo nmcli con modify MyHotspot connection.autoconnect yes
    ```

---

### Step 3: Bring the AP Online
Now, tell NetworkManager to fire up the hotspot:

```bash
sudo nmcli con up MyHotspot
```



---

### Troubleshooting & Tips

* **Interface Names:** Run `nmcli device` to confirm your Wi-Fi is actually named `wlan0`.
* **Regulatory Domain:** If the AP fails to start, it might be due to Wi-Fi country codes. Ensure yours is set:
    ```bash
    sudo raspi-config  # Localisation Options -> WLAN Country
    ```
* **Dual Wi-Fi:** If you are trying to use the **same** physical Wi-Fi chip to both connect to a router and host an AP, be aware that many chips struggle with "Station + AP" mode simultaneously. It is much more stable to use the built-in Wi-Fi for the AP and a USB dongle (or Ethernet) for the internet source.

---

**Would you like me to show you how to configure the routing rules if you want to block certain devices on your new AP from accessing the main network?**