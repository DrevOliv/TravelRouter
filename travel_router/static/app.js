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

document.addEventListener("submit", handleAsyncForm);
