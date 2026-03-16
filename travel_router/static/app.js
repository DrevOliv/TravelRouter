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

function setActionState(action, ok) {
  document.querySelectorAll("[data-action]").forEach((el) => {
    el.classList.remove("is-success");
    if (ok && el.dataset.action === action) {
      el.classList.add("is-success");
    }
  });
}

async function handleAsyncForm(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-async-form]")) return;

  event.preventDefault();

  const submitter = event.submitter || form.querySelector('button[type="submit"], button:not([type])');
  const body = new FormData(form);
  const action = form.action;

  if (submitter) {
    submitter.disabled = true;
    submitter.dataset.originalText = submitter.textContent;
    submitter.textContent = "Saving...";
  }

  try {
    const response = await fetch(action, {
      method: form.method || "POST",
      body,
      headers: {
        Accept: "application/json",
        "X-Requested-With": "fetch",
      },
    });

    const payload = await response.json();
    updateFeedback(payload);
    setActionState(payload.action, payload.ok);
  } catch (error) {
    updateFeedback({
      ok: false,
      message: "Request failed",
      detail: String(error),
    });
  } finally {
    if (submitter) {
      submitter.disabled = false;
      submitter.textContent = submitter.dataset.originalText || submitter.textContent;
    }
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

async function loadJellyfinStatus() {
  const panel = document.querySelector("[data-jellyfin-panel]");
  if (!(panel instanceof HTMLElement)) return;
  if (panel.dataset.jellyfinConfigured !== "true") return;

  const statusUrl = panel.dataset.jellyfinStatusUrl;
  const heroName = document.querySelector("[data-jellyfin-hero-name]");
  const title = panel.querySelector("[data-jellyfin-title]");
  const chip = panel.querySelector("[data-jellyfin-chip]");
  const message = panel.querySelector("[data-jellyfin-message]");

  try {
    const response = await fetch(statusUrl, {
      headers: {
        Accept: "application/json",
      },
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
  } catch (error) {
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

document.addEventListener("submit", handleAsyncForm);
document.addEventListener("DOMContentLoaded", loadJellyfinStatus);
