document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const messageEl = document.getElementById("message");
  messageEl.hidden = true;

  const data = Object.fromEntries(new FormData(e.target).entries());
  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await res.json();
    if (!res.ok) {
      messageEl.hidden = false;
      messageEl.className = "form-message error";
      messageEl.textContent = body.detail || "Falha ao entrar.";
      return;
    }
    setAuthFromLogin(data.username, body.token);
    window.location.href = "/";
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
});
