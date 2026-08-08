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
      <p>Perfil, reputação e chave de API pessoal.</p>
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
