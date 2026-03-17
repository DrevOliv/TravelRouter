To run a single GUI application on a headless Raspberry Pi without the overhead of a full desktop environment (like GNOME or PIXEL), the best approach is to use a **Kiosk Compositor**.

For a Raspberry Pi 4, the most modern and efficient way to do this is using **Cage**. Cage is a Wayland compositor that is designed to run a single maximized application, perfect for dashboards or media players like Jellyfin MPV Shim.

### Why this approach?
Instead of loading a taskbar, wallpaper, file manager, and window decorations, the system loads only the bare minimum required to talk to your GPU and display the app.



---

### Step 1: Install System Dependencies
First, ensure your system is up to date and install the necessary graphics drivers and the Cage compositor.

1.  **Update your Pi:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Install Cage and XWayland:**
    (XWayland is needed because some Python-based GUIs still rely on X11 protocols).
    ```bash
    sudo apt install cage xwayland-session-utils -y
    ```
3.  **Install MPV and Python dependencies:**
    Jellyfin MPV Shim requires `mpv` and several libraries to run.
    ```bash
    sudo apt install mpv python3-pip python3-tk python3-pil python3-numpy libatspi0 -y
    ```

### Step 2: Install Jellyfin MPV Shim
Now, install the shim itself using `pip`. It is recommended to install it for your specific user.

```bash
pip3 install jellyfin-mpv-shim
```
*Note: If you get an "externally-managed-environment" error, you may need to use `pip3 install --break-system-packages jellyfin-mpv-shim` or install it inside a virtual environment (venv).*

### Step 3: Configure GPU and Autologin
Since you are running headless, you need to make sure the Pi boots to the console and automatically logs in so the GUI can start.

1.  Run `sudo raspi-config`.
2.  Navigate to **System Options** -> **Boot / Auto Login**.
3.  Select **Console Autologin**.
4.  Go to **Advanced Options** -> **GL Driver** and ensure **V3D Full KMS** is selected (default for Pi 4).
5.  Finish and Reboot.

### Step 4: Test the Application
Once the Pi reboots and you are at the command line, try launching the app via Cage to see if it displays on your TV:

```bash
cage jellyfin-mpv-shim
```
If the app appears on your TV, you are ready to automate it.

### Step 5: Automate on Boot (The "Kiosk" Setup)
To make the app start automatically every time the Pi turns on, we will create a small script and a systemd service.

1.  **Create a launch script:**
    ```bash
    nano ~/start-shim.sh
    ```
    Paste the following:
    ```bash
    #!/bin/bash
    # Ensure the GPU is ready
    export DISPLAY=:0
    cage jellyfin-mpv-shim
    ```
    Give it execution permissions: `chmod +x ~/start-shim.sh`

2.  **Edit your `.bash_profile`:**
    You want the script to run only when you log in on the physical terminal (tty1), not when you log in via SSH.
    ```bash
    nano ~/.bash_profile
    ```
    Add this to the bottom:
    ```bash
    if [ -z "$DISPLAY" ] && [ "$XDG_VTNR" -eq 1 ]; then
      exec ~/start-shim.sh
    fi
    ```

### Troubleshooting & Tips
* **Hardware Acceleration:** The Pi 4 handles MPV very well, but ensure you aren't running out of Video RAM. You can increase this in `/boot/config.txt` by adding `gpu_mem=320` (though with KMS on Pi 4, this is handled more dynamically).
* **Permissions:** If the app fails to start due to "Permission Denied" on the video device, add your user to the video and render groups:
    `sudo usermod -a -G video,render $USER`
* **Exiting:** Since there is no "X" button or window manager, you usually quit the app using the app's internal menu or by pressing `Ctrl+C` if you have a keyboard attached.

By using **Cage**, your Raspberry Pi 4 will remain extremely lightweight, using minimal RAM while providing a dedicated, appliance-like experience for your Jellyfin setup.