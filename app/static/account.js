const root = document.getElementById("account-root");

if (!isLoggedIn()) {
  window.location.href = "/login";
}

async function loadAccount() {
  const { username } = getAuth();
  try {
    const res = await fetch(`/users/${encodeURIComponent(username)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const profile = await res.json();
    render(profile);
  } catch (err) {
    root.innerHTML = `<p class="error">Erro ao carregar sua conta: ${err.message}</p>`;
  }
}

function render(profile) {
  root.innerHTML = `
    <div class="page-header">
      <h1>Minha conta</h1>
      <p>Perfil, dados da conta e chave de API pessoal.</p>
    </div>

    <div class="form-card wide">
      <h2>Perfil</h2>
      <table class="fiscal-table">
        <tr><th>Usuário</th><td>${avatarHtml(profile.username)} ${escapeHtml(profile.username)}</td></tr>
        <tr><th>Papel</th><td><span class="badge">${escapeHtml(profile.role)}</span></td></tr>
        <tr><th>Nível</th><td>${tierBadgeHtml(profile)} <span class="form-hint" style="display:inline;">(${profile.edit_count} edição(ões))</span></td></tr>
        <tr><th>Contribuidor desde</th><td>${new Date(profile.created_at + "Z").toLocaleDateString("pt-BR")}</td></tr>
      </table>
    </div>

    <div class="form-card wide" style="margin-top:1.2rem;">
      <h2>Dados da conta</h2>
      <p class="subtitle">O nome de usuário não muda (ele assina o histórico das suas edições). Para alterar e-mail ou senha, confirme a senha atual.</p>
      <form id="account-form">
        <label>E-mail
          <input type="email" id="acc-email" required autocomplete="email" />
        </label>
        <label>Nova senha <span class="form-hint" style="display:inline;">(deixe em branco para manter)</span>
          <input type="password" id="acc-new-password" minlength="8" autocomplete="new-password" />
        </label>
        <label>Repita a nova senha
          <input type="password" id="acc-new-password2" minlength="8" autocomplete="new-password" />
        </label>
        <label>Senha atual
          <input type="password" id="acc-current-password" required autocomplete="current-password" />
        </label>
        <button type="submit" class="btn">Salvar alterações</button>
      </form>
      <div class="form-message" id="account-message" hidden></div>
    </div>

    <div class="form-card wide" style="margin-top:1.2rem;">
      <h2>Chave de API</h2>
      <p class="subtitle">
        Sua chave pessoal (<code>X-API-Key</code>) é mostrada só uma vez, no momento em que é criada.
        Perdeu a sua? Gere uma nova abaixo — a antiga é revogada na hora.
      </p>
      <button type="button" id="regenerate-btn" class="btn btn-outline">Gerar nova chave de API</button>
      <div class="form-message" id="key-message" hidden></div>
    </div>
  `;

  document.getElementById("regenerate-btn").addEventListener("click", onRegenerate);
  document.getElementById("account-form").addEventListener("submit", onSaveAccount);
  loadPrivateData();
}

async function loadPrivateData() {
  // E-mail só vem de /auth/me (o perfil público nunca mostra).
  try {
    const res = await authFetch("/auth/me");
    if (res.ok) document.getElementById("acc-email").value = (await res.json()).email;
  } catch (err) {
    /* campo fica vazio - o usuário ainda pode digitar */
  }
}

async function onSaveAccount(event) {
  event.preventDefault();
  const messageEl = document.getElementById("account-message");
  const newPassword = document.getElementById("acc-new-password").value;
  if (newPassword !== document.getElementById("acc-new-password2").value) {
    showMessage(messageEl, "error", "As duas senhas novas não são iguais.");
    return;
  }

  const payload = {
    current_password: document.getElementById("acc-current-password").value,
    email: document.getElementById("acc-email").value.trim(),
  };
  if (newPassword) payload.new_password = newPassword;

  try {
    const res = await authFetch("/auth/me", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join(" ") : body.detail;
      showMessage(messageEl, "error", detail || "Erro ao salvar.");
      return;
    }
    if (newPassword) {
      // Trocar a senha encerra todas as sessões de login - entra de novo.
      clearAuth();
      showMessage(messageEl, "success", "Senha alterada. Entre de novo com a senha nova...");
      setTimeout(() => (window.location.href = "/login"), 1500);
      return;
    }
    showMessage(messageEl, "success", "Dados atualizados.");
    document.getElementById("acc-current-password").value = "";
  } catch (err) {
    showMessage(messageEl, "error", err.message);
  }
}

async function onRegenerate() {
  const btn = document.getElementById("regenerate-btn");
  const messageEl = document.getElementById("key-message");

  if (btn.dataset.confirming !== "1") {
    btn.dataset.confirming = "1";
    btn.textContent = "Confirmar? Isso revoga a chave atual";
    btn.classList.add("btn-reject");
    setTimeout(() => {
      if (btn.dataset.confirming === "1") {
        btn.dataset.confirming = "0";
        btn.textContent = "Gerar nova chave de API";
        btn.classList.remove("btn-reject");
      }
    }, 4000);
    return;
  }

  btn.disabled = true;
  try {
    const res = await authFetch("/auth/api-key/regenerate", { method: "POST" });
    const body = await res.json();
    if (!res.ok) {
      showMessage(messageEl, "error", body.detail ? JSON.stringify(body.detail) : "Erro ao gerar chave.");
      return;
    }
    btn.hidden = true;
    messageEl.hidden = false;
    messageEl.className = "form-message success";
    messageEl.innerHTML = `
      Nova chave gerada (guarde agora, não será mostrada de novo):<br>
      <code style="display:block;margin-top:.5rem;word-break:break-all;">${escapeHtml(body.raw_key)}</code>
    `;
  } catch (err) {
    showMessage(messageEl, "error", err.message);
  } finally {
    btn.disabled = false;
    btn.dataset.confirming = "0";
  }
}

function showMessage(el, kind, text) {
  el.hidden = false;
  el.className = `form-message ${kind}`;
  el.textContent = text;
}

loadAccount();
