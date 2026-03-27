#!/usr/bin/env bash
set -euo pipefail

APP_NAME="pi-travel-router"
APP_USER="pi-travel-router"
APP_GROUP="pi-travel-router"
APP_DIR="/opt/pi-travel-router"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
ENV_FILE="/etc/default/${APP_NAME}"
SUDOERS_FILE="/etc/sudoers.d/${APP_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root: sudo ./install_pi_travel_router.sh"
  exit 1
fi

apt update
apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  network-manager \
  dnsmasq \
  iptables-persistent \
  mpv \
  ffmpeg \
  curl \
  dosfstools \
  exfatprogs \
  openssh-client \
  rsync \
  sshpass

if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

if ! getent group "${APP_GROUP}" >/dev/null; then
  groupadd --system "${APP_GROUP}"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --gid "${APP_GROUP}" \
    --create-home \
    --home-dir "/var/lib/${APP_NAME}" \
    --shell /usr/sbin/nologin \
    "${APP_USER}"
fi

mkdir -p "/var/lib/${APP_NAME}/import_mounts"
mkdir -p "/var/lib/${APP_NAME}/import_runtime/manifests"
chown -R "${APP_USER}:${APP_GROUP}" "/var/lib/${APP_NAME}"

mkdir -p "${APP_DIR}"
rsync -a \
  --delete \
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  "${SCRIPT_DIR}/" "${APP_DIR}/"

chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<'EOF'
DEMO_MODE=0
EOF
fi

cat > "${SUDOERS_FILE}" <<EOF
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/nmcli, /usr/bin/tailscale, /usr/bin/systemctl, /usr/bin/mount, /usr/bin/umount
EOF
chmod 0440 "${SUDOERS_FILE}"
visudo -cf "${SUDOERS_FILE}"

install -m 0644 "${APP_DIR}/deploy/${APP_NAME}.service" "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable --now "${APP_NAME}.service"

echo
echo "Installed ${APP_NAME}."
echo "Service status:"
systemctl --no-pager --full status "${APP_NAME}.service" || true
