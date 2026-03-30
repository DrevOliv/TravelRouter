const SCREEN_TITLES = {
  home: "Home",
  import: "Import",
  media: "Media",
  remote: "Remote",
  settings: "Settings",
};

let mediaSearchTimer = null;
let homeWifiPollTimer = null;
let importJobsPollTimer = null;
let homeWifiRefreshPromise = null;
let screenLoadController = null;
const wifiModalState = {
  isOpen: false,
  ssid: "",
  security: "",
  isOpenNetwork: false,
  password: "",
};

function redirectToLogin() {
  stopHomeWifiPolling();
  stopImportJobsPolling();
  window.location.href = "/login";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const decimals = unitIndex === 0 ? 0 : (size >= 10 ? 1 : 2);
  return `${size.toFixed(decimals)} ${units[unitIndex]}`;
}

function formatSpeed(speedBps) {
  const value = Number(speedBps || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B/s";
  return `${formatBytes(value)}/s`;
}

function formatPathLabel(value) {
  return value ? escapeHtml(value) : "Not set";
}

function formToJson(form) {
  const data = {};
  const formData = new FormData(form);
  for (const [key, value] of formData.entries()) {
    if (Object.hasOwn(data, key)) {
      if (Array.isArray(data[key])) {
        data[key].push(value);
      } else {
        data[key] = [data[key], value];
      }
    } else {
      data[key] = value;
    }
  }

  form.querySelectorAll('input[type="checkbox"][data-boolean-field]').forEach((input) => {
    data[input.name] = input.checked;
  });

  form.querySelectorAll('input[type="checkbox"][data-array-field]').forEach((input) => {
    if (!input.name) return;
    const values = Array.from(form.querySelectorAll(`input[type="checkbox"][data-array-field][name="${CSS.escape(input.name)}"]:checked`))
      .map((element) => element.value);
    data[input.name] = values;
  });

  return data;
}

function getScreenFromPath(pathname) {
  if (pathname === "/import") return "import";
  if (pathname === "/settings") return "settings";
  if (pathname === "/media") return "media";
  if (pathname === "/remote") return "remote";
  return "home";
}

function getApiUrl(screen) {
  const url = new URL(window.location.href);
  if (screen === "import") return `/api/import${url.search}`;
  if (screen === "settings") return "/api/settings";
  if (screen === "media") return `/api/media${url.search}`;
  if (screen === "remote") return "/api/remote";
  return "/api/home";
}

function updateFeedback(payload) {
  if (!payload) return;
  showToast(payload);
}

function showToast(payload) {
  const stack = document.querySelector("[data-toast-stack]");
  if (!stack) return;

  const toast = document.createElement("section");
  toast.className = `toast ${payload.ok ? "success" : "error"}`;
  const detail = payload.detail ? `<p>${escapeHtml(payload.detail)}</p>` : "";
  const link = payload.link
    ? `<p><a href="${escapeAttr(payload.link)}" target="_blank" rel="noopener noreferrer">Open link</a></p>`
    : "";
  toast.innerHTML = `<div><strong>${escapeHtml(payload.message || "")}</strong>${detail}${link}</div>`;
  stack.appendChild(toast);

  window.setTimeout(() => {
    toast.remove();
  }, 2600);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    redirectToLogin();
    return null;
  }
  return response;
}

function updateNavState(screen) {
  document.title = `Pi Travel Router - ${SCREEN_TITLES[screen] || "Home"}`;
  document.querySelectorAll("[data-nav-link]").forEach((link) => {
    const href = link.getAttribute("href") || "/";
    const path = new URL(href, window.location.origin).pathname;
    const active = getScreenFromPath(path) === screen;
    link.classList.toggle("is-active", active);
  });
}

function renderLoading() {
  const root = document.querySelector("#app-root");
  if (!root) return;
  root.innerHTML = `
    <section class="card loading-card">
      <p class="muted">Loading…</p>
    </section>
  `;
}

function setRootBusy(isBusy) {
  const root = document.querySelector("#app-root");
  if (!(root instanceof HTMLElement)) return;
  root.classList.toggle("is-busy", isBusy);
}

function renderError(message) {
  const root = document.querySelector("#app-root");
  if (!root) return;
  closeWifiModal({ restoreFocus: false });
  root.innerHTML = `
    <section class="card empty-state">
      <h3>Could not load this page</h3>
      <p>${escapeHtml(message)}</p>
    </section>
  `;
}

function relayoutPackedGrid(selector) {
  const grid = document.querySelector(selector);
  if (!(grid instanceof HTMLElement)) return;

  const computed = window.getComputedStyle(grid);
  const columnCount = computed.gridTemplateColumns.split(" ").filter(Boolean).length;
  if (columnCount <= 1) {
    grid.querySelectorAll(":scope > .card").forEach((card) => {
      if (card instanceof HTMLElement) {
        card.style.gridRowEnd = "";
      }
    });
    return;
  }

  const rowHeight = Number.parseFloat(computed.getPropertyValue("grid-auto-rows")) || 1;
  const rowGap = Number.parseFloat(computed.getPropertyValue("row-gap")) || 0;

  grid.querySelectorAll(":scope > .card").forEach((card) => {
    if (!(card instanceof HTMLElement)) return;
    card.style.gridRowEnd = "auto";
    const span = Math.ceil((card.getBoundingClientRect().height + rowGap) / (rowHeight + rowGap));
    card.style.gridRowEnd = `span ${Math.max(span, 1)}`;
  });
}

function relayoutAllPackedGrids() {
  relayoutPackedGrid(".dashboard-grid");
}

function renderCurrentNetworkContent(wifiCurrent) {
  if (wifiCurrent.connected) {
    return `
      <div class="stack">
        <ul class="status-list compact-list">
          <li><span>SSID</span><strong class="ok">${escapeHtml(wifiCurrent.ssid)}</strong></li>
          <li><span>Signal</span><strong>${escapeHtml(wifiCurrent.signal)}%</strong></li>
          <li><span>Security</span><strong>${escapeHtml(wifiCurrent.security)}</strong></li>
        </ul>
        <form action="/api/wifi/disconnect" method="post" data-api-form data-refresh-target="home-wifi">
          <button type="submit" data-action="wifi_disconnect" class="secondary">Disconnect Wi-Fi</button>
        </form>
      </div>
    `;
  }

  return `<p class="muted">${escapeHtml(wifiCurrent.ok ? "No upstream Wi-Fi connected." : (wifiCurrent.error || "No upstream Wi-Fi connected."))}</p>`;
}

function renderWifiNetworksContent(wifiNetworks, scanMessage) {
  return wifiNetworks.length
    ? `
      <div class="wifi-network-list">
        ${wifiNetworks
          .map(
            (network) => `
          <div class="wifi-network-item">
            <button
              type="button"
              class="wifi-network-row"
              data-wifi-select
              data-ssid="${escapeAttr(network.ssid)}"
              data-security="${escapeAttr(network.security)}"
              data-open="${network.is_open ? "true" : "false"}"
            >
              <span class="wifi-network-main">
                <strong>${escapeHtml(network.ssid)}</strong>
                <small>${escapeHtml(network.security)}</small>
              </span>
              <span class="wifi-network-signal">${escapeHtml(network.signal)}%</span>
            </button>
          </div>
        `
          )
          .join("")}
      </div>
    `
    : `<p class="muted">${escapeHtml(scanMessage)}</p>`;
}

function renderConnectedDevicesContent(connectedDevices) {
  if (!connectedDevices.length) {
    return `<p class="muted">No devices connected to the private AP.</p>`;
  }

  return `
    <ul class="status-list compact-list device-list">
      ${connectedDevices
        .map(
          (device) => `
        <li>
          <span>
            <strong>${escapeHtml(device.name || device.ip || "Unknown device")}</strong>
            <small>${escapeHtml(device.ip || "No IP")}${device.mac ? ` · ${escapeHtml(device.mac)}` : ""}</small>
          </span>
          <strong class="ok">${escapeHtml(device.state || "connected")}</strong>
        </li>
      `
        )
        .join("")}
    </ul>
  `;
}

function renderWifiModal() {
  return `
    <div class="wifi-modal" data-wifi-modal hidden>
      <div class="wifi-modal-backdrop" data-wifi-modal-dismiss></div>
      <section class="card wifi-modal-panel" role="dialog" aria-modal="true" aria-labelledby="wifi-modal-title">
        <div class="wifi-modal-head">
          <div class="wifi-modal-copy">
            <p class="eyebrow">Connect</p>
            <h3 id="wifi-modal-title" data-wifi-modal-title>Choose a network</h3>
            <p class="muted wifi-modal-security" data-wifi-modal-security>Password protected</p>
          </div>
          <button type="button" class="secondary wifi-close" data-wifi-modal-close>Close</button>
        </div>

        <form action="/api/wifi/connect" method="post" class="stack wifi-modal-form" data-api-form data-refresh-target="home-wifi" data-wifi-modal-form>
          <input type="hidden" name="ssid" value="" data-wifi-modal-ssid>
          <label data-wifi-modal-password-wrap>
            Password
            <input type="password" name="password" placeholder="Enter password" autocomplete="current-password" data-wifi-modal-password>
          </label>
          <p class="muted" data-wifi-modal-hint>Password is optional for open networks.</p>
          <div class="wifi-modal-actions">
            <button type="submit" data-action="wifi_connect" data-wifi-modal-submit>Connect</button>
            <button type="button" class="secondary" data-wifi-modal-close>Cancel</button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function applyWifiSelectionState(scope = document, selectedSsid = "") {
  const rows = Array.from(scope.querySelectorAll("[data-wifi-select]"));
  rows.forEach((row) => {
    const rowSsid = row.getAttribute("data-ssid") || "";
    const isActive = Boolean(selectedSsid) && rowSsid === selectedSsid;
    row.classList.toggle("is-active", isActive);
  });
}

function getWifiModalElements(scope = document) {
  return {
    modal: scope.querySelector("[data-wifi-modal]"),
    title: scope.querySelector("[data-wifi-modal-title]"),
    security: scope.querySelector("[data-wifi-modal-security]"),
    form: scope.querySelector("[data-wifi-modal-form]"),
    ssidInput: scope.querySelector("[data-wifi-modal-ssid]"),
    passwordWrap: scope.querySelector("[data-wifi-modal-password-wrap]"),
    passwordInput: scope.querySelector("[data-wifi-modal-password]"),
    hint: scope.querySelector("[data-wifi-modal-hint]"),
    submit: scope.querySelector("[data-wifi-modal-submit]"),
  };
}

function syncWifiModalState({ focus = false } = {}) {
  const { modal, title, security, ssidInput, passwordWrap, passwordInput, hint, submit } = getWifiModalElements();
  const shouldShow = wifiModalState.isOpen && Boolean(wifiModalState.ssid) && getScreenFromPath(window.location.pathname) === "home";

  document.body.classList.toggle("has-wifi-modal", shouldShow);
  if (!(modal instanceof HTMLElement)) return;

  modal.hidden = !shouldShow;
  if (!shouldShow) return;

  if (title instanceof HTMLElement) {
    title.textContent = wifiModalState.ssid;
  }
  if (security instanceof HTMLElement) {
    security.textContent = wifiModalState.security || (wifiModalState.isOpenNetwork ? "Open network" : "Password protected");
  }
  if (ssidInput instanceof HTMLInputElement) {
    ssidInput.value = wifiModalState.ssid;
  }
  if (passwordWrap instanceof HTMLElement) {
    passwordWrap.hidden = wifiModalState.isOpenNetwork;
  }
  if (passwordInput instanceof HTMLInputElement) {
    passwordInput.required = !wifiModalState.isOpenNetwork;
    passwordInput.value = wifiModalState.isOpenNetwork ? "" : wifiModalState.password;
  }
  if (hint instanceof HTMLElement) {
    hint.textContent = wifiModalState.isOpenNetwork
      ? "Open network selected. You can connect right away."
      : "Enter the Wi-Fi password to connect.";
  }
  if (submit instanceof HTMLButtonElement) {
    submit.disabled = false;
  }

  if (focus) {
    window.requestAnimationFrame(() => {
      if (wifiModalState.isOpenNetwork) {
        if (submit instanceof HTMLButtonElement) submit.focus();
        return;
      }
      if (passwordInput instanceof HTMLInputElement) {
        passwordInput.focus();
      }
    });
  }
}

function openWifiModal({ ssid, security, isOpenNetwork }) {
  if (!ssid) return;

  const keepPassword = wifiModalState.isOpen && wifiModalState.ssid === ssid;
  wifiModalState.isOpen = true;
  wifiModalState.ssid = ssid;
  wifiModalState.security = security || (isOpenNetwork ? "Open network" : "Password protected");
  wifiModalState.isOpenNetwork = isOpenNetwork;
  if (!keepPassword) {
    wifiModalState.password = "";
  }

  applyWifiSelectionState(document, ssid);
  syncWifiModalState({ focus: true });
}

function closeWifiModal({ restoreFocus = true, clearPassword = true } = {}) {
  const selectedSsid = wifiModalState.ssid;
  wifiModalState.isOpen = false;
  wifiModalState.ssid = "";
  wifiModalState.security = "";
  wifiModalState.isOpenNetwork = false;
  if (clearPassword) {
    wifiModalState.password = "";
  }

  syncWifiModalState();
  applyWifiSelectionState(document, "");

  if (!restoreFocus || !selectedSsid) return;
  const trigger = document.querySelector(`[data-wifi-select][data-ssid="${CSS.escape(selectedSsid)}"]`);
  if (trigger instanceof HTMLElement) {
    trigger.focus();
  }
}

function renderHome(data) {
  const wifiCurrent = data.wifi_current || {};
  const connectedDevices = data.connected_devices || [];
  const settings = data.settings || { wifi: {} };
  const wifiNetworks = data.wifi_networks || [];
  const exitNodes = data.exit_nodes || [];
  const selectedExitNode = data.selected_exit_node || "";
  const exitNodeActive = Boolean(data.exit_node_active);
  const exitNodeOptions = [
    `<option value="">Choose exit node</option>`,
    ...exitNodes.map(
      (node) =>
        `<option value="${escapeAttr(node.value)}" ${selectedExitNode === node.value ? "selected" : ""}>${escapeHtml(node.label)}${node.online ? " · online" : ""}</option>`
    ),
  ].join("");
  const scanMessage = data.wifi_scan?.stdout || data.wifi_scan?.stderr || "No scan data yet.";
  const currentNetworkHtml = renderCurrentNetworkContent(wifiCurrent);

  const wifiNetworksHtml = renderWifiNetworksContent(wifiNetworks, scanMessage);

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Wi-Fi</h2>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Connected</span>
          <strong data-home-hero-connected>${escapeHtml(wifiCurrent.connected ? wifiCurrent.ssid : "Not connected")}</strong>
        </div>
        <div class="mini-stat">
          <span class="mini-stat-label">Upstream NIC</span>
          <strong>${escapeHtml(settings.wifi?.upstream_interface || "wlan0")}</strong>
        </div>
        <div class="mini-stat">
          <span class="mini-stat-label">Private AP</span>
          <strong>${escapeHtml(settings.wifi?.ap_interface || "wlan1")}</strong>
        </div>
      </div>
    </section>

    <section class="grid dashboard-grid">
      <article class="card">
        <h3>Current network</h3>
        <div data-home-current-network>
          ${currentNetworkHtml}
        </div>
      </article>

      <article class="card wifi-qr-card">
        <div class="section-head">
          <div>
            <h3>Private Wi-Fi QR</h3>
            <p class="muted">${escapeHtml(settings.wifi?.ap_ssid || "PiTravelHub")}</p>
          </div>
        </div>
        <div class="wifi-qr-block">
          <img src="/api/home/ap-qr" alt="QR code for the private Wi-Fi network">
          <p class="muted">Scan to join the router Wi-Fi quickly.</p>
        </div>
      </article>

      <article class="card">
        <h3>Connected devices</h3>
        <div data-home-connected-devices>
          ${renderConnectedDevicesContent(connectedDevices)}
        </div>
      </article>

      <article class="card dashboard-card-tall">
        <div class="travel-panel-head">
          <div>
            <h3>Choose Wi-Fi</h3>
            <p class="muted">Scanning via <code>${escapeHtml(settings.wifi?.upstream_interface || "wlan0")}</code></p>
          </div>
        </div>
        <div data-home-wifi-list>
          ${wifiNetworksHtml}
        </div>
      </article>

      <article class="card" data-home-exit-node>
        ${renderHomeExitNodeContent({
          exitNodes,
          selectedExitNode,
          exitNodeActive,
        })}
      </article>
    </section>

    ${renderWifiModal()}
  `;
}

function renderHomeExitNodeContent(data) {
  const exitNodes = data.exitNodes || [];
  const selectedExitNode = data.selectedExitNode || "";
  const exitNodeActive = Boolean(data.exitNodeActive);
  const selectedExitNodeLabel = exitNodes.find((node) => node.value === selectedExitNode)?.label || selectedExitNode;
  const exitNodeOptions = [
    `<option value="">Choose exit node</option>`,
    ...exitNodes.map(
      (node) =>
        `<option value="${escapeAttr(node.value)}" ${selectedExitNode === node.value ? "selected" : ""}>${escapeHtml(node.label)}${node.online ? " · online" : ""}</option>`
    ),
  ].join("");

  return `
    <div class="travel-panel-head">
      <div>
        <h3>Exit node</h3>
        <p class="muted">Save one node, then turn it on only when you need it.</p>
      </div>
      <span class="status-chip">${escapeHtml(exitNodeActive ? "On" : "Off")}</span>
    </div>

    <div class="travel-panel">
      <div class="exit-node-current">
        <span class="mini-stat-label">Saved exit node</span>
        <strong>${escapeHtml(selectedExitNodeLabel || "No exit node selected")}</strong>
      </div>

      <form action="/api/settings/tailscale/toggle" method="post" class="stack exit-node-toggle-form" data-api-form data-refresh-target="home-exit-node" data-refresh-on-error="true">
        <label class="switch-row switch-control">
          <span>Use exit node</span>
          <input type="checkbox" name="enabled" ${exitNodeActive ? "checked" : ""} data-exit-node-toggle data-boolean-field ${selectedExitNode ? "" : "disabled"}>
          <span class="switch-slider" aria-hidden="true"></span>
        </label>
      </form>

      <form action="/api/settings/tailscale/selection" method="post" class="stack exit-node-form" data-api-form data-refresh-target="home-exit-node" data-refresh-on-error="true">
        <label>
          Exit node
          <select name="exit_node" ${exitNodes.length ? "" : "disabled"}>${exitNodeOptions}</select>
        </label>
        <button type="submit" data-action="tailscale_selection" class="secondary" ${exitNodes.length ? "" : "disabled"}>Save exit node</button>
      </form>

      ${exitNodes.length ? "" : `<p class="muted">No exit nodes available yet.</p>`}
      ${exitNodes.length && !selectedExitNode ? `<p class="muted">Choose and save an exit node before turning it on.</p>` : ""}
    </div>
  `;
}

function renderSettings(data) {
  const settings = data.settings || {};
  const jellyfin = data.jellyfin || {};
  const transfer = settings.transfer || {};

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Settings</h2>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Jellyfin</span>
          <strong data-jellyfin-hero-name>${escapeHtml(jellyfin.configured ? "Checking..." : "Not set")}</strong>
        </div>
        <div class="mini-stat">
          <span class="mini-stat-label">TrueNAS</span>
          <strong>${escapeHtml(transfer.host || "Not set")}</strong>
        </div>
      </div>
    </section>

    <section class="grid settings-grid">
      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Wi-Fi</p>
            <h3>Interface mapping</h3>
          </div>
        </div>
        <form action="/api/settings/wifi" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            Upstream interface
            <input type="text" name="upstream_interface" value="${escapeAttr(settings.wifi?.upstream_interface || "wlan0")}">
          </label>
          <label>
            AP interface
            <input type="text" name="ap_interface" value="${escapeAttr(settings.wifi?.ap_interface || "wlan1")}">
          </label>
          <button type="submit" data-action="wifi_settings">Save interfaces</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Private Wi-Fi</p>
            <h3>SSID</h3>
          </div>
        </div>
        <form action="/api/settings/wifi/ap-ssid" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            Network name
            <input type="text" name="ap_ssid" value="${escapeAttr(settings.wifi?.ap_ssid || "PiTravelHub")}">
          </label>
          <button type="submit" data-action="wifi_ap_ssid">Save SSID</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Private Wi-Fi</p>
            <h3>Password</h3>
          </div>
        </div>
        <form action="/api/settings/wifi/ap-password" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            Network password
            <input type="password" name="ap_password" value="${escapeAttr(settings.wifi?.ap_password || "ChangeThisPassword")}">
          </label>
          <button type="submit" data-action="wifi_ap_password">Save password</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">TrueNAS import</p>
            <h3>Transfer connection</h3>
          </div>
          <span class="status-chip">${escapeHtml(transfer.host ? "Configured" : "Not set")}</span>
        </div>
        <form action="/api/settings/truenas-transfer" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            Host
            <input type="text" name="host" value="${escapeAttr(transfer.host || "")}" placeholder="truenas.local">
          </label>
          <div class="inline-fields">
            <label>
              Port
              <input type="number" name="port" value="${escapeAttr(transfer.port || 22)}" min="1" max="65535">
            </label>
            <label>
              Username
              <input type="text" name="username" value="${escapeAttr(transfer.username || "")}" placeholder="backup">
            </label>
          </div>
          <label>
            Auth mode
            <select name="auth_mode" data-transfer-auth-mode>
              <option value="ssh_key" ${transfer.auth_mode === "ssh_key" || !transfer.auth_mode ? "selected" : ""}>SSH key</option>
              <option value="password" ${transfer.auth_mode === "password" ? "selected" : ""}>Password</option>
            </select>
          </label>
          <label data-transfer-key-wrap>
            Private key path on Pi
            <input type="text" name="private_key_path" value="${escapeAttr(transfer.private_key_path || "")}" placeholder="/var/lib/pi-travel-router/.ssh/id_ed25519">
          </label>
          <label data-transfer-password-wrap>
            Password
            <input type="password" name="password" value="${escapeAttr(transfer.password || "")}">
          </label>
          <button type="submit" data-action="transfer_settings">Save transfer settings</button>
        </form>
        <form action="/api/settings/truenas-transfer/test" method="post" class="stack" data-api-form>
          <button type="submit" data-action="transfer_settings_test" class="secondary">Test connection</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Security</p>
            <h3>Admin password</h3>
          </div>
        </div>
        <form action="/api/auth/password" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            New password
            <input type="password" name="new_password" autocomplete="new-password">
          </label>
          <label>
            Confirm new password
            <input type="password" name="confirm_password" autocomplete="new-password">
          </label>
          <button type="submit" data-action="auth_password">Change password</button>
        </form>
      </article>

      <article
        class="card"
        data-jellyfin-panel
        data-jellyfin-configured="${jellyfin.configured ? "true" : "false"}"
      >
        <div class="section-head">
          <div>
            <p class="eyebrow">Jellyfin</p>
            <h3 data-jellyfin-title>${escapeHtml(jellyfin.configured ? "Checking server" : "Media server settings")}</h3>
          </div>
          <span class="status-chip" data-jellyfin-chip ${jellyfin.configured ? "" : "hidden"}>${jellyfin.configured ? "Checking..." : ""}</span>
        </div>

        <p class="muted" data-jellyfin-message>${escapeHtml(jellyfin.error || "Configure Jellyfin below.")}</p>

        <form action="/api/settings/jellyfin" method="post" class="stack" data-api-form data-refresh="settings">
          <label>
            Server URL
            <input type="url" name="server_url" value="${escapeAttr(settings.jellyfin?.server_url || "")}" placeholder="http://100.x.x.x:8096">
          </label>
          <label>
            API key
            <input type="password" name="api_key" value="${escapeAttr(settings.jellyfin?.api_key || "")}">
          </label>
          <label>
            User ID
            <input type="text" name="user_id" value="${escapeAttr(settings.jellyfin?.user_id || "")}">
          </label>
          <label>
            Device name
            <input type="text" name="device_name" value="${escapeAttr(settings.jellyfin?.device_name || "Pi Travel Router")}">
          </label>
          <button type="submit" data-action="jellyfin_settings">Save Jellyfin settings</button>
        </form>
      </article>
    </section>
  `;
}

function renderImportJobs(jobs) {
  if (!jobs.length) {
    return `<p class="muted">No uploads yet.</p>`;
  }

  return `
    <div class="import-job-list">
      ${jobs
        .map((job) => {
          const progress = Math.max(0, Math.min(100, Number(job.progress_percent || 0)));
          const statusLabel = job.phase || job.status || "queued";
          const retryLabel = job.next_retry_at ? `Retry scheduled` : "";
          const canRetry = ["failed", "cancelled", "waiting_retry", "waiting_source"].includes(job.status);
          const canCancel = ["queued", "running", "verifying", "waiting_retry", "waiting_source"].includes(job.status);
          return `
            <article class="import-job-item">
              <div class="import-job-head">
                <div>
                  <strong>${escapeHtml(job.source_name || "Import job")}</strong>
                  <p class="muted">${escapeHtml(job.kind === "folder" ? "Folder upload" : `${job.selected_files?.length || 0} selected photos`)}</p>
                </div>
                <span class="status-chip">${escapeHtml(statusLabel)}</span>
              </div>
              <p class="import-job-path">${escapeHtml(job.destination_path || "")}</p>
              <div class="remote-progress">
                <div class="remote-progress-bar">
                  <span style="width: ${progress}%"></span>
                </div>
                <div class="remote-progress-copy">
                  <span>${formatBytes(job.bytes_sent || 0)} / ${formatBytes(job.total_bytes || 0)}</span>
                  <span>${progress}%</span>
                </div>
              </div>
              <div class="import-job-meta">
                <span>${escapeHtml(`${job.total_files || 0} files`)}</span>
                <span>${escapeHtml(formatSpeed(job.speed_bps || 0))}</span>
              </div>
              ${job.error ? `<p class="muted">${escapeHtml(job.error)}</p>` : ""}
              ${retryLabel ? `<p class="muted">${escapeHtml(retryLabel)}</p>` : ""}
              ${job.last_output ? `<p class="muted">${escapeHtml(job.last_output)}</p>` : ""}
              <div class="button-row">
                ${canRetry ? `
                  <form action="/api/import/jobs/${encodeURIComponent(job.id)}/retry" method="post" data-api-form data-refresh-target="import-jobs">
                    <button type="submit" class="secondary">Retry</button>
                  </form>
                ` : ""}
                ${canCancel ? `
                  <form action="/api/import/jobs/${encodeURIComponent(job.id)}/cancel" method="post" data-api-form data-refresh-target="import-jobs">
                    <button type="submit" class="secondary">Cancel</button>
                  </form>
                ` : ""}
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderImport(data) {
  const transfer = data.transfer || {};
  const devices = data.devices || [];
  const browser = data.browser || { directories: [], files: [], breadcrumbs: [] };
  const selectedDevice = data.selected_device || "";
  const selectedDeviceInfo = devices.find((device) => device.device_path === selectedDevice) || null;
  const directories = browser.directories || [];
  const files = browser.files || [];
  const currentPath = browser.current_path || "";
  const currentFolderName = currentPath.split("/").filter(Boolean).pop() || "SD card";
  const destinationValue = transfer.last_destination_path || "";

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Import Photos</h2>
        <p class="muted">Mount an SD card, browse photos, choose a destination path, and queue resumable uploads to TrueNAS.</p>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Target host</span>
          <strong>${escapeHtml(transfer.host || "Not set")}</strong>
        </div>
        <div class="mini-stat">
          <span class="mini-stat-label">Destination path</span>
          <strong>${escapeHtml(transfer.last_destination_path || "Choose on this page")}</strong>
        </div>
      </div>
    </section>

    <section class="grid import-grid">
      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">SD card</p>
            <h3>Removable storage</h3>
          </div>
        </div>
        ${
          devices.length
            ? `
              <div class="import-device-list">
                ${devices
                  .map(
                    (device) => `
                      <div class="import-device-item ${device.device_path === selectedDevice ? "is-active" : ""}">
                        <div>
                          <strong>${escapeHtml(device.label || device.name || device.device_path)}</strong>
                          <p class="muted">${escapeHtml(device.size || "")}${device.fstype ? ` · ${escapeHtml(device.fstype)}` : ""}</p>
                        </div>
                        <div class="button-row">
                          ${
                            device.mounted
                              ? `
                                <a href="/import?device=${encodeURIComponent(device.device_path)}" data-nav-link class="button secondary">Browse</a>
                                <form action="/api/import/unmount" method="post" data-api-form data-refresh="import">
                                  <input type="hidden" name="device_path" value="${escapeAttr(device.device_path)}">
                                  <button type="submit" class="secondary">Unmount</button>
                                </form>
                              `
                              : `
                                <form action="/api/import/mount" method="post" data-api-form data-refresh="import">
                                  <input type="hidden" name="device_path" value="${escapeAttr(device.device_path)}">
                                  <button type="submit">Mount</button>
                                </form>
                              `
                          }
                        </div>
                      </div>
                    `
                  )
                  .join("")}
              </div>
            `
            : `<p class="muted">No removable SD card detected.</p>`
        }
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Destination</p>
            <h3>TrueNAS path</h3>
          </div>
          <span class="status-chip">${escapeHtml(transfer.configured ? "Ready" : "Setup needed")}</span>
        </div>
        <label>
          Destination path on TrueNAS
          <input type="text" value="${escapeAttr(destinationValue)}" placeholder="/mnt/tank/photos/imports/trip" data-import-destination-input>
        </label>
        <p class="muted">This path is chosen on the Import page and reused as the default next time.</p>
        <ul class="status-list compact-list import-target-summary">
          <li><span>Host</span><strong>${escapeHtml(transfer.host || "Not set")}</strong></li>
          <li><span>User</span><strong>${escapeHtml(transfer.username || "Not set")}</strong></li>
          <li><span>Auth</span><strong>${escapeHtml(transfer.auth_mode === "password" ? "Password" : "SSH key")}</strong></li>
        </ul>
      </article>

      <article class="card card-wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Source browser</p>
            <h3>${escapeHtml(selectedDeviceInfo ? selectedDeviceInfo.label || currentFolderName : "Browse SD card")}</h3>
          </div>
          <span class="status-chip">${escapeHtml(browser.ok ? currentFolderName : "Waiting")}</span>
        </div>
        ${
          browser.ok
            ? `
              <div class="import-breadcrumbs">
                ${browser.breadcrumbs
                  .map(
                    (crumb) => `
                      <a href="/import?device=${encodeURIComponent(selectedDevice)}${crumb.path ? `&source=${encodeURIComponent(crumb.path)}` : ""}" data-nav-link class="pill-link">${escapeHtml(crumb.name)}</a>
                    `
                  )
                  .join("")}
              </div>

              <form action="/api/import/upload-folder" method="post" class="stack import-upload-form" data-api-form data-refresh="import">
                <input type="hidden" name="device_path" value="${escapeAttr(selectedDevice)}">
                <input type="hidden" name="source_path" value="${escapeAttr(currentPath)}">
                <input type="hidden" name="destination_path" value="${escapeAttr(destinationValue)}" data-import-destination-field>
                <button type="submit" data-import-current-folder-button ${destinationValue && currentPath ? "" : "disabled"}>Upload current folder</button>
              </form>

              <div class="import-browser-grid">
                <div class="import-browser-column">
                  <h4>Folders</h4>
                  ${
                    directories.length
                      ? `
                        <div class="import-entry-list">
                          ${directories
                            .map(
                              (entry) => `
                                <div class="import-entry-item">
                                  <a href="/import?device=${encodeURIComponent(selectedDevice)}&source=${encodeURIComponent(entry.relative_path)}" data-nav-link class="import-entry-link">
                                    <strong>${escapeHtml(entry.name)}</strong>
                                    <small>Open folder</small>
                                  </a>
                                  <form action="/api/import/upload-folder" method="post" data-api-form data-refresh="import">
                                    <input type="hidden" name="device_path" value="${escapeAttr(selectedDevice)}">
                                    <input type="hidden" name="source_path" value="${escapeAttr(entry.relative_path)}">
                                    <input type="hidden" name="destination_path" value="${escapeAttr(destinationValue)}" data-import-destination-field>
                                    <button type="submit" class="secondary" ${destinationValue ? "" : "disabled"}>Upload folder</button>
                                  </form>
                                </div>
                              `
                            )
                            .join("")}
                        </div>
                      `
                      : `<p class="muted">No subfolders here.</p>`
                  }
                </div>

                <div class="import-browser-column">
                  <h4>Photos</h4>
                  ${
                    files.length
                      ? `
                        <form action="/api/import/upload-files" method="post" class="stack import-file-form" data-api-form data-refresh="import">
                          <input type="hidden" name="device_path" value="${escapeAttr(selectedDevice)}">
                          <input type="hidden" name="source_path" value="${escapeAttr(currentPath)}">
                          <input type="hidden" name="destination_path" value="${escapeAttr(destinationValue)}" data-import-destination-field>
                          <div class="import-file-list">
                            ${files
                              .map(
                                (entry) => `
                                  <label class="import-file-row">
                                    <span>
                                      <input type="checkbox" name="selected_files" value="${escapeAttr(entry.name)}" data-import-file-checkbox data-array-field>
                                      <strong>${escapeHtml(entry.name)}</strong>
                                    </span>
                                    <small>${escapeHtml(formatBytes(entry.size_bytes))}</small>
                                  </label>
                                `
                              )
                              .join("")}
                          </div>
                          <button type="submit" data-import-files-submit ${destinationValue ? "" : "disabled"}>Upload selected photos</button>
                        </form>
                      `
                      : `<p class="muted">No photos found in this folder.</p>`
                  }
                </div>
              </div>
            `
            : `<p class="muted">${escapeHtml(browser.error || "Mount an SD card to start browsing.")}</p>`
        }
      </article>

      <article class="card card-wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Queue</p>
            <h3>Uploads</h3>
          </div>
        </div>
        <div data-import-jobs>
          ${renderImportJobs(data.jobs || [])}
        </div>
      </article>
    </section>
  `;
}

function renderMedia(data) {
  const items = data.items || {};
  const list = items.data?.Items || [];
  const rootLabel = data.parent_id ? "Collection" : "Library";
  const itemCount = list.length;

  const itemsHtml = items.ok
    ? `
      <div class="media-grid">
        ${list
          .map((item) => {
            const resumeTicks = item.UserData?.PlaybackPositionTicks || 0;
            const remoteResumeMinutes = Math.floor(resumeTicks / 10000000 / 60);
            const localResumeMinutes = item.LocalResumeSeconds ? Math.floor(item.LocalResumeSeconds / 60) : 0;
            const resumeMinutes = remoteResumeMinutes || localResumeMinutes;
            const isFolder = ["CollectionFolder", "UserView", "Series", "Season", "BoxSet"].includes(item.Type);

            return `
              <article class="media-card">
                <div class="poster-frame">
                  <img src="${escapeAttr(item.image_url)}" alt="${escapeAttr(item.Name)} poster" loading="lazy">
                  ${
                    isFolder
                      ? `<a class="poster-hitarea" href="/media?parent_id=${encodeURIComponent(item.Id)}" data-nav-link aria-label="Open ${escapeAttr(item.Name)}"></a>`
                      : `
                        <form action="/api/media/play/${encodeURIComponent(item.Id)}" method="post" class="poster-play-form" data-api-form>
                          <input type="hidden" name="resume" value="true">
                          <button type="submit" data-action="media_play" class="poster-hitarea poster-play-button" aria-label="Play ${escapeAttr(item.Name)}">
                            <span class="play-icon" aria-hidden="true"></span>
                          </button>
                        </form>
                      `
                  }
                  <div class="poster-overlay">
                    ${resumeMinutes ? `<span class="resume-badge">Resume ${escapeHtml(resumeMinutes)}m</span>` : ""}
                  </div>
                </div>
                <div class="media-card-body">
                  <div class="media-card-copy">
                    <p class="media-kicker">${escapeHtml(isFolder ? "Browse" : item.Type)}</p>
                    <h3>${escapeHtml(item.Name)}</h3>
                    <p class="media-meta">${escapeHtml(isFolder ? "Open collection" : (resumeMinutes ? `Resume at ${resumeMinutes} min` : "Ready to play"))}</p>
                  </div>
                  <div class="media-card-actions">
                    ${
                      isFolder
                        ? `<a class="button secondary" href="/media?parent_id=${encodeURIComponent(item.Id)}" data-nav-link>Open</a>`
                        : `
                          <form action="/api/media/play/${encodeURIComponent(item.Id)}" method="post" data-api-form>
                            <input type="hidden" name="resume" value="false">
                            <button type="submit" class="secondary">From start</button>
                          </form>
                        `
                    }
                  </div>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    `
    : `
      <section class="card media-empty-state">
        <p class="eyebrow">Media</p>
        <h3>${escapeHtml(items.configured ? "Jellyfin is unreachable" : "Library unavailable")}</h3>
        <p>${escapeHtml(items.error || "Could not load the library.")}</p>
      </section>
    `;

  return `
    <section class="media-shell">
      <section class="media-heading">
        <div class="media-heading-copy">
          <p class="eyebrow">${escapeHtml(rootLabel)}</p>
          <h2>${escapeHtml(data.search_term ? `Results for "${data.search_term}"` : (data.parent_id ? "Collection view" : "Media library"))}</h2>
          <p class="media-subcopy">${escapeHtml(items.ok ? `${itemCount} item${itemCount === 1 ? "" : "s"} available` : "Check Jellyfin connection and try again.")}</p>
        </div>
      </section>

      <section class="card media-toolbar">
        <form class="media-search-bar" data-nav-form="media" data-live-search="media">
          <input type="text" name="q" value="${escapeAttr(data.search_term || "")}" placeholder="Search movies, shows, collections" autocomplete="off">
          <input type="hidden" name="parent_id" value="${escapeAttr(data.parent_id || "")}">
          <button type="submit">Search</button>
        </form>
        <div class="media-toolbar-links">
          ${data.parent_id ? `<a class="pill-link" href="/media" data-nav-link>Back to library</a>` : ""}
        </div>
      </section>
    </section>

    <section class="media-shelf">
      ${itemsHtml}
    </section>
  `;
}

function renderRemote(data) {
  const playback = data.playback_state || {};
  const audioTracks = playback.audio_tracks || [];
  const subtitleTracks = playback.subtitle_tracks || [];
  const progressPercent = playback.duration ? Math.max(0, Math.min(100, Math.round((playback.time_pos / playback.duration) * 100))) : 0;

  const nowPlayingHtml = playback.ok
    ? `
      <div class="remote-now-playing">
        <div class="playback-meta">
          <div>
            <p class="eyebrow">Now playing</p>
            <h3>${escapeHtml(playback.active_item_id || "Active stream")}</h3>
            <p class="muted">${playback.duration ? `${escapeHtml(playback.time_pos)}s of ${escapeHtml(playback.duration)}s` : `Position ${escapeHtml(playback.time_pos)}s`}</p>
          </div>
          <span class="status-chip">${escapeHtml(playback.paused ? "Paused" : "Playing")}</span>
        </div>
        <div class="remote-progress">
          <div class="remote-progress-bar">
            <span style="width: ${progressPercent}%"></span>
          </div>
          <div class="remote-progress-copy">
            <span>${escapeHtml(playback.resume_seconds || 0)}s saved</span>
            <span>${escapeHtml(progressPercent)}%</span>
          </div>
        </div>
      </div>
    `
    : `
      <div class="remote-idle">
        <p class="eyebrow">Playback</p>
        <h3>Nothing is playing</h3>
        <p class="muted">${escapeHtml(playback.error || "Start something from Media to use these controls.")}</p>
        ${playback.resume_seconds ? `<p class="muted">Latest saved resume point: ${escapeHtml(playback.resume_seconds)} seconds.</p>` : ""}
      </div>
    `;

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Remote</h2>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Playback</span>
          <strong>${escapeHtml(playback.ok ? "Active" : "Idle")}</strong>
        </div>
        <div class="mini-stat">
          <span class="mini-stat-label">Resume</span>
          <strong>${escapeHtml(playback.resume_seconds || 0)}s</strong>
        </div>
      </div>
    </section>

    <section class="remote-shell">
      <section class="card now-playing">${nowPlayingHtml}</section>

      <section class="card remote-transport">
        <div class="section-head">
          <div>
            <p class="eyebrow">Controls</p>
            <h3>Transport</h3>
          </div>
        </div>
        <div class="remote-transport-grid">
          <form action="/api/remote/rewind" method="post" data-api-form data-refresh-target="remote-state">
            <button type="submit" data-action="remote_rewind" class="transport-button secondary">-30s</button>
          </form>
          <form action="/api/remote/pause" method="post" data-api-form data-refresh-target="remote-state">
            <button type="submit" data-action="remote_pause" class="transport-button transport-primary">${playback.paused ? "Resume" : "Pause"}</button>
          </form>
          <form action="/api/remote/forward" method="post" data-api-form data-refresh-target="remote-state">
            <button type="submit" data-action="remote_forward" class="transport-button secondary">+30s</button>
          </form>
          <form action="/api/remote/stop" method="post" data-api-form data-refresh-target="remote-state" class="transport-stop">
            <button type="submit" data-action="remote_stop" class="danger">Stop playback</button>
          </form>
        </div>
      </section>

      <section class="grid remote-settings-grid">
      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Audio</p>
            <h3>Language</h3>
          </div>
        </div>
        <form action="/api/remote/audio" method="post" class="stack" data-api-form data-refresh-target="remote-state">
          <label>
            Active audio track
            <select name="track_id">
              ${audioTracks
                .map(
                  (track) =>
                    `<option value="${escapeAttr(track.id)}" ${track.selected ? "selected" : ""}>${escapeHtml((track.lang || "und").toUpperCase())} - ${escapeHtml(track.title)}</option>`
                )
                .join("")}
            </select>
          </label>
          <button type="submit" data-action="remote_audio">Switch audio</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Subtitles</p>
            <h3>Track</h3>
          </div>
        </div>
        <form action="/api/remote/subtitles" method="post" class="stack" data-api-form data-refresh-target="remote-state">
          <label>
            Subtitle track
            <select name="track_id">
              <option value="no">Off</option>
              ${subtitleTracks
                .map(
                  (track) =>
                    `<option value="${escapeAttr(track.id)}" ${track.selected ? "selected" : ""}>${escapeHtml((track.lang || "und").toUpperCase())} - ${escapeHtml(track.title)}</option>`
                )
                .join("")}
            </select>
          </label>
          <button type="submit" data-action="remote_subtitles">Apply subtitles</button>
        </form>
      </article>
      </section>
    </section>
  `;
}

function renderScreen(screen, payload) {
  const root = document.querySelector("#app-root");
  if (!root) return;

  if (screen === "import") {
    root.innerHTML = renderImport(payload);
    syncImportDestination(document);
    syncTransferAuthMode(document);
    return;
  }
  if (screen === "settings") {
    closeWifiModal({ restoreFocus: false });
    root.innerHTML = renderSettings(payload);
    syncTransferAuthMode(root);
    hydrateJellyfinStatus();
    return;
  }
  if (screen === "media") {
    closeWifiModal({ restoreFocus: false });
    root.innerHTML = renderMedia(payload);
    return;
  }
  if (screen === "remote") {
    closeWifiModal({ restoreFocus: false });
    root.innerHTML = renderRemote(payload);
    return;
  }
  root.innerHTML = renderHome(payload);
  applyWifiSelectionState(root, wifiModalState.ssid);
  syncWifiModalState();
  requestAnimationFrame(relayoutAllPackedGrids);
}

async function fetchScreenPayload(screen) {
  const response = await fetchJson(getApiUrl(screen), {
    headers: {
      Accept: "application/json",
    },
  });
  if (!response) return null;
  return response.json();
}

async function refreshHomeExitNodeWidget() {
  const widget = document.querySelector("[data-home-exit-node]");
  if (!(widget instanceof HTMLElement)) return;
  const payload = await fetchScreenPayload("home");
  if (!payload) return;
  widget.innerHTML = renderHomeExitNodeContent({
    exitNodes: payload.exit_nodes || [],
    selectedExitNode: payload.selected_exit_node || "",
    exitNodeActive: payload.exit_node_active,
  });
  requestAnimationFrame(relayoutAllPackedGrids);
}

async function refreshRemoteState() {
  const shell = document.querySelector(".remote-shell");
  if (!(shell instanceof HTMLElement)) return;
  const payload = await fetchScreenPayload("remote");
  if (!payload) return;
  renderScreen("remote", payload);
}

async function refreshImportJobs() {
  if (getScreenFromPath(window.location.pathname) !== "import") return;
  const jobsContainer = document.querySelector("[data-import-jobs]");
  if (!(jobsContainer instanceof HTMLElement)) return;

  try {
    const response = await fetchJson("/api/import/jobs", {
      headers: { Accept: "application/json" },
    });
    if (!response) return;
    const payload = await response.json();
    jobsContainer.innerHTML = renderImportJobs(payload.jobs || []);
  } catch (_error) {
    // Leave the current queue view in place on transient polling failures.
  }
}

async function handleActionRefresh(form, payload) {
  const refreshTarget = form.dataset.refreshTarget || "";
  if (refreshTarget === "home-wifi") {
    await refreshHomeWifiLive();
    return true;
  }
  if (refreshTarget === "home-exit-node") {
    await refreshHomeExitNodeWidget();
    return true;
  }
  if (refreshTarget === "remote-state") {
    await refreshRemoteState();
    return true;
  }
  if (refreshTarget === "import-jobs") {
    await refreshImportJobs();
    return true;
  }

  const action = payload.action || "";
  if (action === "wifi_connect" || action === "wifi_disconnect") {
    await refreshHomeWifiLive();
    return true;
  }
  if (action === "tailscale_toggle" || action === "tailscale_selection") {
    await refreshHomeExitNodeWidget();
    return true;
  }
  if (action.startsWith("remote_")) {
    await refreshRemoteState();
    return true;
  }
  if (action === "jellyfin_settings") {
    hydrateJellyfinStatus();
    return true;
  }
  return false;
}

function stopHomeWifiPolling() {
  if (homeWifiPollTimer !== null) {
    window.clearInterval(homeWifiPollTimer);
    homeWifiPollTimer = null;
  }
}

function stopImportJobsPolling() {
  if (importJobsPollTimer !== null) {
    window.clearInterval(importJobsPollTimer);
    importJobsPollTimer = null;
  }
}

async function refreshHomeWifiLive() {
  if (getScreenFromPath(window.location.pathname) !== "home") return;
  if (homeWifiRefreshPromise) return homeWifiRefreshPromise;

  homeWifiRefreshPromise = (async () => {
    const currentCard = document.querySelector("[data-home-current-network]");
    const wifiList = document.querySelector("[data-home-wifi-list]");
    const connectedDevicesCard = document.querySelector("[data-home-connected-devices]");
    const heroConnected = document.querySelector("[data-home-hero-connected]");
    if (!(currentCard instanceof HTMLElement) || !(wifiList instanceof HTMLElement) || !(connectedDevicesCard instanceof HTMLElement)) return;

    try {
      const response = await fetchJson("/api/home/wifi-live", {
        headers: { Accept: "application/json" },
      });
      if (!response) return;
      const payload = await response.json();
      if (getScreenFromPath(window.location.pathname) !== "home") return;

      currentCard.innerHTML = renderCurrentNetworkContent(payload.wifi_current || {});
      connectedDevicesCard.innerHTML = renderConnectedDevicesContent(payload.connected_devices || []);
      if (heroConnected instanceof HTMLElement) {
        heroConnected.textContent = payload.wifi_current?.connected ? payload.wifi_current.ssid : "Not connected";
      }

      const scanMessage = payload.wifi_scan?.stdout || payload.wifi_scan?.stderr || "No scan data yet.";
      wifiList.innerHTML = renderWifiNetworksContent(payload.wifi_networks || [], scanMessage);
      applyWifiSelectionState(document, wifiModalState.ssid);
      requestAnimationFrame(relayoutAllPackedGrids);
    } catch (_error) {
      // Ignore transient polling failures and keep the last rendered Wi-Fi state.
    }
  })();

  try {
    await homeWifiRefreshPromise;
  } finally {
    homeWifiRefreshPromise = null;
  }
}

function startHomeWifiPolling() {
  stopHomeWifiPolling();
  if (getScreenFromPath(window.location.pathname) !== "home") return;
  homeWifiPollTimer = window.setInterval(() => {
    refreshHomeWifiLive();
  }, 5000);
}

function startImportJobsPolling() {
  stopImportJobsPolling();
  if (getScreenFromPath(window.location.pathname) !== "import") return;
  importJobsPollTimer = window.setInterval(() => {
    refreshImportJobs();
  }, 1500);
}

async function loadCurrentScreen(options = {}) {
  const { silent = true } = options;
  const screen = getScreenFromPath(window.location.pathname);
  updateNavState(screen);
  const root = document.querySelector("#app-root");
  if (!silent && root?.children.length === 0) {
    renderLoading();
  }

  if (screenLoadController) {
    screenLoadController.abort();
  }
  screenLoadController = new AbortController();
  setRootBusy(true);

  try {
    const response = await fetchJson(getApiUrl(screen), {
      headers: {
        Accept: "application/json",
      },
      signal: screenLoadController.signal,
    });
    if (!response) return;
    const payload = await response.json();
    renderScreen(screen, payload);
    if (screen === "home") {
      startHomeWifiPolling();
    } else {
      stopHomeWifiPolling();
    }
    if (screen === "import") {
      startImportJobsPolling();
    } else {
      stopImportJobsPolling();
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    stopHomeWifiPolling();
    stopImportJobsPolling();
    renderError(String(error));
  } finally {
    setRootBusy(false);
  }
}

function navigate(url) {
  const nextUrl = new URL(url, window.location.origin);
  window.history.pushState({}, "", `${nextUrl.pathname}${nextUrl.search}`);
  loadCurrentScreen({ silent: true });
}

function triggerLiveMediaSearch(form) {
  const data = new FormData(form);
  const query = new URLSearchParams();
  for (const [key, value] of data.entries()) {
    const text = String(value).trim();
    if (text) query.set(key, text);
  }
  const nextUrl = query.toString() ? `/media?${query.toString()}` : "/media";
  const currentUrl = `${window.location.pathname}${window.location.search}`;
  if (nextUrl === currentUrl) return;
  window.history.replaceState({}, "", nextUrl);
  loadCurrentScreen({ silent: true });
}

function syncTransferAuthMode(scope = document) {
  const select = scope.querySelector("[data-transfer-auth-mode]");
  if (!(select instanceof HTMLSelectElement)) return;

  const value = select.value;
  scope.querySelectorAll("[data-transfer-password-wrap]").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.hidden = value !== "password";
    }
    const input = element.querySelector("input");
    if (input instanceof HTMLInputElement) {
      input.required = value === "password";
    }
  });
  scope.querySelectorAll("[data-transfer-key-wrap]").forEach((element) => {
    if (element instanceof HTMLElement) {
      element.hidden = value !== "ssh_key";
    }
    const input = element.querySelector("input");
    if (input instanceof HTMLInputElement) {
      input.required = value === "ssh_key";
    }
  });
}

function syncImportDestination(scope = document) {
  const input = scope.querySelector("[data-import-destination-input]");
  if (!(input instanceof HTMLInputElement)) return;

  const apply = () => {
    const value = input.value.trim();
    scope.querySelectorAll("[data-import-destination-field]").forEach((field) => {
      if (field instanceof HTMLInputElement) {
        field.value = value;
      }
    });
    scope.querySelectorAll("[data-import-files-submit], .import-browser-grid form button[type='submit'], .import-upload-form button[type='submit']").forEach((button) => {
      if (button instanceof HTMLButtonElement) {
        button.disabled = !value;
      }
    });
    scope.querySelectorAll("[data-import-current-folder-button]").forEach((button) => {
      if (button instanceof HTMLButtonElement) {
        const sourceField = button.form?.querySelector('input[name="source_path"]');
        const hasFolder = sourceField instanceof HTMLInputElement && Boolean(sourceField.value.trim());
        button.disabled = !value || !hasFolder;
      }
    });
    syncImportFileSelection(scope);
  };

  apply();
}

function syncImportFileSelection(scope = document) {
  const form = scope.querySelector(".import-file-form");
  if (!(form instanceof HTMLFormElement)) return;
  const submit = form.querySelector("[data-import-files-submit]");
  const destination = scope.querySelector("[data-import-destination-input]");
  const checked = form.querySelectorAll("[data-import-file-checkbox]:checked").length;
  if (submit instanceof HTMLButtonElement) {
    submit.disabled = checked === 0 || !(destination instanceof HTMLInputElement && destination.value.trim());
    submit.textContent = checked > 0 ? `Upload ${checked} selected photo${checked === 1 ? "" : "s"}` : "Upload selected photos";
  }
}

async function hydrateJellyfinStatus() {
  const panel = document.querySelector("[data-jellyfin-panel]");
  if (!(panel instanceof HTMLElement)) return;
  if (panel.dataset.jellyfinConfigured !== "true") return;

  const heroName = document.querySelector("[data-jellyfin-hero-name]");
  const title = panel.querySelector("[data-jellyfin-title]");
  const chip = panel.querySelector("[data-jellyfin-chip]");
  const message = panel.querySelector("[data-jellyfin-message]");

  try {
    const response = await fetchJson("/api/settings/jellyfin-status", {
      headers: { Accept: "application/json" },
    });
    if (!response) return;
    const payload = await response.json();
    if (payload.ok) {
      if (heroName) heroName.textContent = payload.data?.ServerName || "Connected";
      if (title) title.textContent = payload.data?.ServerName || "Connected";
      if (chip) {
        chip.hidden = false;
        chip.textContent = payload.data?.Version || "Online";
      }
      if (message) {
        message.hidden = true;
        message.textContent = "";
      }
      return;
    }

    if (heroName) heroName.textContent = "Unreachable";
    if (title) title.textContent = "Server unreachable";
    if (chip) {
      chip.hidden = false;
      chip.textContent = "Offline";
    }
    if (message) {
      message.hidden = false;
      message.textContent = payload.error || "Jellyfin server is unreachable.";
    }
  } catch (_error) {
    if (heroName) heroName.textContent = "Unreachable";
    if (title) title.textContent = "Server unreachable";
    if (chip) {
      chip.hidden = false;
      chip.textContent = "Offline";
    }
    if (message) {
      message.hidden = false;
      message.textContent = "Could not check Jellyfin right now.";
    }
  }
}

function flashActionSuccess(target, ok) {
  if (!(target instanceof HTMLElement) || !ok) return;
  target.classList.add("did-succeed");
  window.setTimeout(() => {
    target.classList.remove("did-succeed");
  }, 1800);
}

async function submitApiForm(form, submitter) {
  const body = JSON.stringify(formToJson(form));
  const originalText = submitter instanceof HTMLButtonElement ? submitter.textContent : "";

  if (submitter instanceof HTMLButtonElement) {
    submitter.disabled = true;
    submitter.textContent = "Saving...";
  }

  try {
    const response = await fetchJson(form.action, {
      method: form.method || "POST",
      body,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    if (!response) return;
    const payload = await response.json();
    updateFeedback(payload);
    flashActionSuccess(submitter, payload.ok);
    if (payload.ok && payload.action === "auth_logout") {
      redirectToLogin();
      return;
    }
    if (payload.ok && payload.action === "wifi_connect") {
      closeWifiModal({ restoreFocus: false });
    }
    const handled = await handleActionRefresh(form, payload);
    const desiredRefresh = form.dataset.refresh || payload.refresh;
    if (!handled && payload.ok && desiredRefresh && desiredRefresh === getScreenFromPath(window.location.pathname)) {
      await loadCurrentScreen({ silent: true });
    } else if (!handled && !payload.ok && form.dataset.refreshOnError === "true" && desiredRefresh === getScreenFromPath(window.location.pathname)) {
      await loadCurrentScreen({ silent: true });
    }
  } catch (error) {
    updateFeedback({ ok: false, message: "Request failed", detail: String(error) });
    const desiredRefresh = form.dataset.refresh;
    if (form.dataset.refreshOnError === "true" && desiredRefresh === getScreenFromPath(window.location.pathname)) {
      await loadCurrentScreen({ silent: true });
    }
  } finally {
    if (submitter instanceof HTMLButtonElement) {
      submitter.disabled = false;
      submitter.textContent = originalText;
    }
  }
}

async function loadMeta() {
  try {
    const response = await fetchJson("/api/meta", {
      headers: { Accept: "application/json" },
    });
    if (!response) return;
    const payload = await response.json();
    const badge = document.querySelector("[data-demo-badge]");
    if (badge) {
      badge.hidden = !payload.demo_mode;
    }
  } catch (_error) {
    // Ignore meta load failures; the app can still render.
  }
}

function handleClick(event) {
  const link = event.target.closest("[data-nav-link]");
  if (link instanceof HTMLAnchorElement) {
    const href = link.getAttribute("href");
    if (href && href.startsWith("/")) {
      event.preventDefault();
      navigate(href);
      return;
    }
  }

  const wifiModalClose = event.target.closest("[data-wifi-modal-close], [data-wifi-modal-dismiss]");
  if (wifiModalClose instanceof HTMLElement) {
    closeWifiModal();
    return;
  }

  const wifiButton = event.target.closest("[data-wifi-select]");
  if (wifiButton instanceof HTMLElement) {
    const ssid = wifiButton.getAttribute("data-ssid") || "";
    const security = wifiButton.getAttribute("data-security") || "";
    const isOpenNetwork = wifiButton.getAttribute("data-open") === "true";
    openWifiModal({ ssid, security, isOpenNetwork });
    return;
  }
}

function handleInput(event) {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  if (input.matches("[data-import-destination-input]")) {
    syncImportDestination(document);
    return;
  }

  if (input.matches("[data-wifi-modal-password]")) {
    wifiModalState.password = input.value;
  }

  const form = input.closest('form[data-live-search="media"]');
  if (!(form instanceof HTMLFormElement)) return;
  if (input.name !== "q") return;

  window.clearTimeout(mediaSearchTimer);
  mediaSearchTimer = window.setTimeout(() => {
    triggerLiveMediaSearch(form);
  }, 220);
}

function handleChange(event) {
  const target = event.target;
  if (target instanceof HTMLInputElement && target.matches("[data-exit-node-toggle]")) {
    const form = target.closest("form[data-api-form]");
    if (!(form instanceof HTMLFormElement)) return;
    submitApiForm(form, null);
    return;
  }

  if (target instanceof HTMLSelectElement && target.matches("[data-transfer-auth-mode]")) {
    syncTransferAuthMode(document);
    return;
  }

  if (target instanceof HTMLInputElement && target.matches("[data-import-file-checkbox]")) {
    syncImportFileSelection(document);
  }
}

function handleKeydown(event) {
  if (event.key !== "Escape" || !wifiModalState.isOpen) return;
  event.preventDefault();
  closeWifiModal();
}

function handleSubmit(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;

  const navForm = form.getAttribute("data-nav-form");
  if (navForm) {
    event.preventDefault();
    const data = new FormData(form);
    const query = new URLSearchParams();
    for (const [key, value] of data.entries()) {
      const text = String(value).trim();
      if (text) query.set(key, text);
    }
    const path = navForm === "media" ? "/media" : "/";
    navigate(query.toString() ? `${path}?${query.toString()}` : path);
    return;
  }

  if (!form.matches("[data-api-form]")) return;

  event.preventDefault();
  const submitter = event.submitter || form.querySelector('button[type="submit"], button:not([type])');
  submitApiForm(form, submitter);
}

document.addEventListener("click", handleClick);
document.addEventListener("change", handleChange);
document.addEventListener("input", handleInput);
document.addEventListener("keydown", handleKeydown);
document.addEventListener("submit", handleSubmit);
window.addEventListener("popstate", () => {
  loadCurrentScreen({ silent: true });
});
window.addEventListener("resize", () => {
  requestAnimationFrame(relayoutAllPackedGrids);
});
window.addEventListener("beforeunload", stopHomeWifiPolling);
window.addEventListener("beforeunload", stopImportJobsPolling);
document.addEventListener("DOMContentLoaded", loadMeta);
document.addEventListener("DOMContentLoaded", loadCurrentScreen);
