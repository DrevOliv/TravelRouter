async function submitLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = form.querySelector("[data-login-error]");
  const passwordInput = form.querySelector('input[name="password"]');
  const password = passwordInput instanceof HTMLInputElement ? passwordInput.value : "";

  if (error instanceof HTMLElement) {
    error.hidden = true;
    error.textContent = "";
  }

  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ password }),
  });
  const payload = await response.json();

  if (payload.ok) {
    window.location.href = "/";
    return;
  }

  if (error instanceof HTMLElement) {
    error.hidden = false;
    error.textContent = payload.detail || payload.message || "Login failed.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-login-form]");
  if (form instanceof HTMLFormElement) {
    form.addEventListener("submit", submitLogin);
  }
});
