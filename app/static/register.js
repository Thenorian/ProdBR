document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const messageEl = document.getElementById("message");
  messageEl.hidden = true;

  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await res.json();
    if (!res.ok) {
      messageEl.hidden = false;
      messageEl.className = "form-message error";
      messageEl.textContent = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join(" ")
        : body.detail || "Falha ao registrar.";
      return;
    }

    setAuthFromRegister(data.username, body.api_key.raw_key);

    form.hidden = true;
    messageEl.hidden = false;
    messageEl.className = "form-message success";
    messageEl.innerHTML = `
      Conta criada! Sua chave de API pessoal (guarde agora, não será mostrada de novo):<br>
      <code style="display:block;margin-top:.5rem;word-break:break-all;">${escapeHtml(body.api_key.raw_key)}</code>
      <a class="btn btn-sm" style="margin-top:1rem;display:inline-block;" href="/">Continuar</a>
    `;
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
});
