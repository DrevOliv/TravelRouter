const SCREEN_TITLES = {
  home: "Home",
  media: "Media",
  remote: "Remote",
  settings: "Settings",
};

let mediaSearchTimer = null;
let homeWifiPollTimer = null;
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

function formToJson(form) {
  const data = {};
  const formData = new FormData(form);
  for (const [key, value] of formData.entries()) {
    data[key] = value;
  }

  form.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    data[input.name] = input.checked;
  });

  return data;
}

function getScreenFromPath(pathname) {
  if (pathname === "/settings") return "settings";
  if (pathname === "/media") return "media";
  if (pathname === "/remote") return "remote";
  return "home";
}

function getApiUrl(screen) {
  const url = new URL(window.location.href);
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

function relayoutAllPackedGrids() {}

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
  const services = data.services || {};
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

  const servicesHtml = Object.entries(services)
    .map(([name, result]) => {
      const state = result?.stdout || result?.stderr || "unknown";
      const stateClass = result?.ok && result?.stdout === "active" ? "ok" : "warn";
      return `<li><span>${escapeHtml(name)}</span><strong class="${stateClass}">${escapeHtml(state)}</strong></li>`;
    })
    .join("");

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

      <article class="card">
        <h3>Service status</h3>
        <ul class="status-list">${servicesHtml}</ul>
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
          <input type="checkbox" name="enabled" ${exitNodeActive ? "checked" : ""} data-exit-node-toggle ${selectedExitNode ? "" : "disabled"}>
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

  if (screen === "settings") {
    closeWifiModal({ restoreFocus: false });
    root.innerHTML = renderSettings(payload);
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
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    stopHomeWifiPolling();
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
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  if (!input.matches("[data-exit-node-toggle]")) return;

  const form = input.closest("form[data-api-form]");
  if (!(form instanceof HTMLFormElement)) return;
  submitApiForm(form, null);
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
document.addEventListener("DOMContentLoaded", loadMeta);
document.addEventListener("DOMContentLoaded", loadCurrentScreen);
