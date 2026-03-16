const SCREEN_TITLES = {
  home: "Home",
  media: "Media",
  remote: "Remote",
  settings: "Settings",
};

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
  const banner = document.querySelector("[data-feedback]");
  if (!banner) return;

  if (!payload) {
    banner.hidden = true;
    banner.className = "feedback-banner";
    banner.innerHTML = "";
    return;
  }

  banner.hidden = false;
  banner.className = `feedback-banner ${payload.ok ? "success" : "error"}`;
  const detail = payload.detail ? `<p>${escapeHtml(payload.detail)}</p>` : "";
  const link = payload.link
    ? `<p><a href="${escapeAttr(payload.link)}" target="_blank" rel="noopener noreferrer">Open link</a></p>`
    : "";
  banner.innerHTML = `<div><strong>${escapeHtml(payload.message || "")}</strong>${detail}${link}</div>`;
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

function renderError(message) {
  const root = document.querySelector("#app-root");
  if (!root) return;
  root.innerHTML = `
    <section class="card empty-state">
      <h3>Could not load this page</h3>
      <p>${escapeHtml(message)}</p>
    </section>
  `;
}

function renderHome(data) {
  const wifiCurrent = data.wifi_current || {};
  const services = data.services || {};
  const settings = data.settings || { wifi: {} };
  const wifiNetworks = data.wifi_networks || [];
  const scanMessage = data.wifi_scan?.stdout || data.wifi_scan?.stderr || "No scan data yet.";

  const currentNetworkHtml = wifiCurrent.connected
    ? `
      <ul class="status-list compact-list">
        <li><span>SSID</span><strong class="ok">${escapeHtml(wifiCurrent.ssid)}</strong></li>
        <li><span>Signal</span><strong>${escapeHtml(wifiCurrent.signal)}%</strong></li>
        <li><span>Security</span><strong>${escapeHtml(wifiCurrent.security)}</strong></li>
      </ul>
    `
    : `<p class="muted">${escapeHtml(wifiCurrent.ok ? "No upstream Wi-Fi connected." : (wifiCurrent.error || "No upstream Wi-Fi connected."))}</p>`;

  const servicesHtml = Object.entries(services)
    .map(([name, result]) => {
      const state = result?.stdout || result?.stderr || "unknown";
      const stateClass = result?.ok && result?.stdout === "active" ? "ok" : "warn";
      return `<li><span>${escapeHtml(name)}</span><strong class="${stateClass}">${escapeHtml(state)}</strong></li>`;
    })
    .join("");

  const wifiNetworksHtml = wifiNetworks.length
    ? `
      <div class="wifi-network-list">
        ${wifiNetworks
          .map(
            (network) => `
          <button
            type="button"
            class="wifi-network-row"
            data-wifi-select
            data-ssid="${escapeAttr(network.ssid)}"
            data-open="${network.is_open ? "true" : "false"}"
          >
            <span class="wifi-network-main">
              <strong>${escapeHtml(network.ssid)}</strong>
              <small>${escapeHtml(network.security)}</small>
            </span>
            <span class="wifi-network-signal">${escapeHtml(network.signal)}%</span>
          </button>
        `
          )
          .join("")}
      </div>
      <form action="/api/wifi/connect" method="post" class="stack wifi-connect-inline" data-api-form data-refresh="home" data-wifi-form hidden>
        <div class="wifi-connect-head">
          <div>
            <p class="eyebrow">Connect</p>
            <h4 data-wifi-selected>Choose a network</h4>
          </div>
          <button type="button" class="button secondary wifi-close" data-wifi-cancel>Close</button>
        </div>
        <input type="hidden" name="ssid" value="" data-wifi-ssid>
        <label>
          Password
          <input type="password" name="password" placeholder="Enter password" data-wifi-password>
        </label>
        <p class="muted" data-wifi-hint>Password is optional for open networks.</p>
        <button type="submit" data-action="wifi_connect">Connect</button>
      </form>
    `
    : `<p class="muted">${escapeHtml(scanMessage)}</p>`;

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Wi-Fi</h2>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Connected</span>
          <strong>${escapeHtml(wifiCurrent.connected ? wifiCurrent.ssid : "Not connected")}</strong>
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

    <section class="grid">
      <article class="card">
        <h3>Current network</h3>
        ${currentNetworkHtml}
      </article>

      <article class="card">
        <h3>Service status</h3>
        <ul class="status-list">${servicesHtml}</ul>
      </article>
    </section>

    <section class="grid">
      <article class="card">
        <h3>Nearby Wi-Fi networks</h3>
        <p class="muted">Scanning via <code>${escapeHtml(settings.wifi?.upstream_interface || "wlan0")}</code></p>
        ${wifiNetworksHtml}
      </article>

      <article class="card">
        <h3>Quick links</h3>
        <div class="stack quick-links">
          <a class="button" href="/settings" data-nav-link>Settings</a>
          <a class="button secondary" href="/media" data-nav-link>Media</a>
        </div>
      </article>
    </section>
  `;
}

function renderSettings(data) {
  const settings = data.settings || {};
  const tailscaleData = data.tailscale_data || {};
  const exitNodes = data.exit_nodes || [];
  const selectedExitNode = data.selected_exit_node || "";
  const jellyfin = data.jellyfin || {};
  const tailscaleOutput = data.tailscale?.stdout || data.tailscale?.stderr || "No Tailscale data yet.";

  const exitNodeOptions = [
    `<option value="">Select node</option>`,
    ...exitNodes.map(
      (node) =>
        `<option value="${escapeAttr(node.value)}" ${selectedExitNode === node.value ? "selected" : ""}>${escapeHtml(node.label)}${node.online ? " · online" : ""}</option>`
    ),
  ].join("");

  return `
    <section class="card hero page-hero">
      <div class="hero-copy">
        <h2>Settings</h2>
      </div>
      <div class="hero-side">
        <div class="mini-stat">
          <span class="mini-stat-label">Tailscale</span>
          <strong>${escapeHtml(tailscaleData.BackendState || "Unknown")}</strong>
        </div>
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
          <button type="submit" data-action="wifi_settings">Save Wi-Fi settings</button>
        </form>
      </article>

      <article class="card">
        <div class="section-head">
          <div>
            <p class="eyebrow">Tailscale</p>
            <h3>${escapeHtml(tailscaleData.Self?.HostName || "Not connected yet")}</h3>
          </div>
          <span class="status-chip">${escapeHtml(tailscaleData.BackendState || "Unknown")}</span>
        </div>

        <form action="/api/settings/tailscale/login" method="post" class="stack" data-api-form data-refresh="settings">
          <button type="submit" data-action="tailscale_login">Log in to Tailscale</button>
        </form>

        <form action="/api/settings/tailscale" method="post" class="stack toggle-form" data-api-form data-refresh="settings">
          <label class="switch-row">
            <span>Use exit node</span>
            <input type="checkbox" name="use_exit_node" ${selectedExitNode ? "checked" : ""}>
          </label>
          <label>
            Exit node
            <select name="exit_node">${exitNodeOptions}</select>
          </label>
          <button type="submit" data-action="tailscale_settings" class="secondary">Save Tailscale settings</button>
        </form>

        <details class="log-panel">
          <summary>Output</summary>
          <pre class="terminal">${escapeHtml(tailscaleOutput)}</pre>
        </details>
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

  const itemsHtml = items.ok
    ? `
      <div class="poster-grid">
        ${list
          .map((item) => {
            const resumeTicks = item.UserData?.PlaybackPositionTicks || 0;
            const remoteResumeMinutes = Math.floor(resumeTicks / 10000000 / 60);
            const localResumeMinutes = item.LocalResumeSeconds ? Math.floor(item.LocalResumeSeconds / 60) : 0;
            const resumeMinutes = remoteResumeMinutes || localResumeMinutes;
            const isFolder = ["CollectionFolder", "UserView", "Series", "Season", "BoxSet"].includes(item.Type);

            return `
              <article class="poster-card">
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
                <div class="poster-body">
                  <h3>${escapeHtml(item.Name)}</h3>
                  <p class="poster-meta">${escapeHtml(item.Type)}</p>
                  <div class="poster-actions">
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
      <section class="card empty-state">
        <h3>${escapeHtml(items.configured ? "Jellyfin unreachable" : "Library unavailable")}</h3>
        <p>${escapeHtml(items.error || "Could not load the library.")}</p>
      </section>
    `;

  return `
    <section class="hero media-hero page-hero">
      <div class="hero-copy">
        <h2>Media</h2>
      </div>
      ${!items.ok ? `<div class="hero-side"><div class="mini-stat"><span class="mini-stat-label">Jellyfin</span><strong>${escapeHtml(items.configured ? "Unreachable" : "Not set")}</strong></div></div>` : ""}
      <form class="toolbar media-search" data-nav-form="media">
        <input type="text" name="q" value="${escapeAttr(data.search_term || "")}" placeholder="Search">
        <input type="hidden" name="parent_id" value="${escapeAttr(data.parent_id || "")}">
        <button type="submit">Search</button>
      </form>
    </section>

    <section class="media-shelf">
      ${data.parent_id ? `<a class="pill-link" href="/media" data-nav-link>Back to library</a>` : ""}
      ${itemsHtml}
    </section>
  `;
}

function renderRemote(data) {
  const playback = data.playback_state || {};
  const audioTracks = playback.audio_tracks || [];
  const subtitleTracks = playback.subtitle_tracks || [];

  const nowPlayingHtml = playback.ok
    ? `
      <div class="playback-meta">
        <div>
          <h3>${escapeHtml(playback.active_item_id || "Active stream")}</h3>
          <p class="muted">${playback.duration ? `${escapeHtml(playback.time_pos)}s / ${escapeHtml(playback.duration)}s` : `Position ${escapeHtml(playback.time_pos)}s`}</p>
        </div>
        <span class="status-chip">${escapeHtml(playback.paused ? "Paused" : "Playing")}</span>
      </div>
    `
    : `
      <p class="muted">${escapeHtml(playback.error || "No active playback session yet.")}</p>
      ${playback.resume_seconds ? `<p class="muted">Latest saved resume point: ${escapeHtml(playback.resume_seconds)} seconds.</p>` : ""}
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

    <section class="card now-playing">${nowPlayingHtml}</section>

    <section class="card">
      <div class="remote-grid">
        <form action="/api/remote/rewind" method="post" data-api-form data-refresh="remote"><button type="submit" data-action="remote_rewind">-30s</button></form>
        <form action="/api/remote/pause" method="post" data-api-form data-refresh="remote"><button type="submit" data-action="remote_pause">Pause / Resume</button></form>
        <form action="/api/remote/forward" method="post" data-api-form data-refresh="remote"><button type="submit" data-action="remote_forward">+30s</button></form>
        <form action="/api/remote/stop" method="post" data-api-form data-refresh="remote"><button type="submit" data-action="remote_stop" class="danger">Stop</button></form>
      </div>
    </section>

    <section class="grid remote-settings-grid">
      <article class="card">
        <h3>Audio language</h3>
        <form action="/api/remote/audio" method="post" class="stack" data-api-form data-refresh="remote">
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
        <h3>Subtitles</h3>
        <form action="/api/remote/subtitles" method="post" class="stack" data-api-form data-refresh="remote">
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
  `;
}

function renderScreen(screen, payload) {
  const root = document.querySelector("#app-root");
  if (!root) return;

  if (screen === "settings") {
    root.innerHTML = renderSettings(payload);
    hydrateJellyfinStatus();
    return;
  }
  if (screen === "media") {
    root.innerHTML = renderMedia(payload);
    return;
  }
  if (screen === "remote") {
    root.innerHTML = renderRemote(payload);
    return;
  }
  root.innerHTML = renderHome(payload);
}

async function loadCurrentScreen() {
  const screen = getScreenFromPath(window.location.pathname);
  updateNavState(screen);
  renderLoading();

  try {
    const response = await fetch(getApiUrl(screen), {
      headers: {
        Accept: "application/json",
      },
    });
    const payload = await response.json();
    renderScreen(screen, payload);
  } catch (error) {
    renderError(String(error));
  }
}

function navigate(url) {
  const nextUrl = new URL(url, window.location.origin);
  window.history.pushState({}, "", `${nextUrl.pathname}${nextUrl.search}`);
  updateFeedback(null);
  loadCurrentScreen();
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
    const response = await fetch("/api/settings/jellyfin-status", {
      headers: { Accept: "application/json" },
    });
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

function setActionState(action, ok) {
  document.querySelectorAll("[data-action]").forEach((el) => {
    el.classList.remove("is-success");
    if (ok && el.dataset.action === action) {
      el.classList.add("is-success");
    }
  });
}

async function submitApiForm(form, submitter) {
  const body = JSON.stringify(formToJson(form));
  const originalText = submitter ? submitter.textContent : "";

  if (submitter) {
    submitter.disabled = true;
    submitter.textContent = "Saving...";
  }

  try {
    const response = await fetch(form.action, {
      method: form.method || "POST",
      body,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    const payload = await response.json();
    updateFeedback(payload);
    setActionState(payload.action, payload.ok);
    if (payload.ok && payload.refresh && payload.refresh === getScreenFromPath(window.location.pathname)) {
      await loadCurrentScreen();
    }
  } catch (error) {
    updateFeedback({ ok: false, message: "Request failed", detail: String(error) });
  } finally {
    if (submitter) {
      submitter.disabled = false;
      submitter.textContent = originalText;
    }
  }
}

async function loadMeta() {
  try {
    const response = await fetch("/api/meta", {
      headers: { Accept: "application/json" },
    });
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

  const wifiButton = event.target.closest("[data-wifi-select]");
  if (wifiButton instanceof HTMLElement) {
    const form = document.querySelector("[data-wifi-form]");
    if (!(form instanceof HTMLFormElement)) return;
    const ssidInput = form.querySelector("[data-wifi-ssid]");
    const passwordInput = form.querySelector("[data-wifi-password]");
    const title = form.querySelector("[data-wifi-selected]");
    const hint = form.querySelector("[data-wifi-hint]");
    const ssid = wifiButton.getAttribute("data-ssid") || "";
    const isOpen = wifiButton.getAttribute("data-open") === "true";

    document.querySelectorAll("[data-wifi-select]").forEach((row) => row.classList.remove("is-active"));
    wifiButton.classList.add("is-active");

    if (ssidInput instanceof HTMLInputElement) ssidInput.value = ssid;
    if (title) title.textContent = ssid;
    if (passwordInput instanceof HTMLInputElement) {
      passwordInput.value = "";
      passwordInput.required = !isOpen;
      passwordInput.placeholder = isOpen ? "No password needed" : "Enter password";
      if (!isOpen) passwordInput.focus();
    }
    if (hint) {
      hint.textContent = isOpen ? "This network looks open. You can connect without a password." : "Enter the Wi-Fi password to connect.";
    }
    form.hidden = false;
    return;
  }

  const wifiCancel = event.target.closest("[data-wifi-cancel]");
  if (wifiCancel instanceof HTMLElement) {
    const form = document.querySelector("[data-wifi-form]");
    if (!(form instanceof HTMLFormElement)) return;
    const ssidInput = form.querySelector("[data-wifi-ssid]");
    const passwordInput = form.querySelector("[data-wifi-password]");
    const title = form.querySelector("[data-wifi-selected]");
    const hint = form.querySelector("[data-wifi-hint]");
    form.hidden = true;
    document.querySelectorAll("[data-wifi-select]").forEach((row) => row.classList.remove("is-active"));
    if (ssidInput instanceof HTMLInputElement) ssidInput.value = "";
    if (passwordInput instanceof HTMLInputElement) {
      passwordInput.value = "";
      passwordInput.required = false;
    }
    if (title) title.textContent = "Choose a network";
    if (hint) hint.textContent = "Password is optional for open networks.";
  }
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
document.addEventListener("submit", handleSubmit);
window.addEventListener("popstate", () => {
  updateFeedback(null);
  loadCurrentScreen();
});
document.addEventListener("DOMContentLoaded", loadMeta);
document.addEventListener("DOMContentLoaded", loadCurrentScreen);
