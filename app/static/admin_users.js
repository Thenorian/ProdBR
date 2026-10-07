const usersEl = document.getElementById("users");
const ROLE_LABELS = { member: "Membro", moderator: "Moderador", admin: "Administrador" };
let tiers = [];

async function loadUsers() {
  if (!isLoggedIn()) {
    usersEl.innerHTML = `<p class="error">Você precisa <a href="/login">entrar</a> com uma conta de administrador.</p>`;
    return;
  }

  try {
    const [res, tiersRes] = await Promise.all([authFetch("/admin/users"), authFetch("/admin/tiers")]);
    if (res.status === 403) {
      usersEl.innerHTML = `<p class="error">Acesso restrito a administradores.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    tiers = tiersRes.ok ? await tiersRes.json() : [];
    render(await res.json());
  } catch (err) {
    usersEl.innerHTML = `<p class="error">Erro ao carregar usuários: ${escapeHtml(err.message)}</p>`;
  }
}

function render(users) {
  const me = getAuth().username;
  usersEl.innerHTML = users.map((u) => userHtml(u, u.username === me)).join("");
  usersEl.querySelectorAll(".mod-item").forEach(bindItem);
}

function userHtml(u, self) {
  const roleOptions = Object.entries(ROLE_LABELS)
    .map(([value, label]) => `<option value="${value}" ${u.role === value ? "selected" : ""}>${label}</option>`)
    .join("");
  // Nível concedido é um piso: o que a pessoa já conquistou editando nunca cai.
  const tierOptions = [`<option value="">— nenhum (só o conquistado) —</option>`]
    .concat(
      tiers.map(
        (t) => `<option value="${escapeHtml(t.name)}" ${u.tier_override === t.name ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      )
    )
    .join("");
  return `
    <div class="mod-item" data-username="${escapeHtml(u.username)}" data-self="${self ? "1" : ""}">
      <div class="feed-title">
        ${avatarHtml(u.username)} ${escapeHtml(u.username)} ${tierBadgeHtml(u)}
        ${self ? '<span class="badge">você</span>' : ""}
      </div>
      <div class="feed-meta">
        ${escapeHtml(u.email)} · reputação ${u.reputation} · ${u.edit_count} edições
        (nível conquistado: ${escapeHtml(u.earned_tier)}) · desde ${timeAgo(u.created_at)}
      </div>
      <div class="mod-actions admin-user-actions">
        <label>Papel
          <select class="role-select" ${self ? 'disabled title="Você não pode mudar o seu próprio papel"' : ""}>${roleOptions}</select>
        </label>
        <button class="btn btn-sm" data-action="role" ${self ? "disabled" : ""}>Salvar papel</button>
        <label>Nível concedido
          <select class="tier-select">${tierOptions}</select>
        </label>
        <button class="btn btn-sm" data-action="tier">Salvar nível</button>
      </div>
      <div class="form-message" hidden></div>
    </div>`;
}

function bindItem(el) {
  el.querySelector('[data-action="role"]').addEventListener("click", () => save(el, "role"));
  el.querySelector('[data-action="tier"]').addEventListener("click", () => save(el, "tier"));
}

async function save(el, kind) {
  const username = el.dataset.username;
  const messageEl = el.querySelector(".form-message");
  const body =
    kind === "role"
      ? { role: el.querySelector(".role-select").value }
      : { tier: el.querySelector(".tier-select").value || null };
  messageEl.hidden = false;
  try {
    const res = await authFetch(`/admin/users/${encodeURIComponent(username)}/${kind}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      messageEl.className = "form-message error";
      messageEl.textContent = data.detail || "Erro ao salvar.";
      return;
    }
    el.outerHTML = userHtml(data, el.dataset.self === "1");
    const fresh = usersEl.querySelector(`.mod-item[data-username="${CSS.escape(username)}"]`);
    bindItem(fresh);
    const msg = fresh.querySelector(".form-message");
    msg.hidden = false;
    msg.className = "form-message success";
    msg.textContent =
      kind === "role"
        ? `Papel de ${username} agora é ${ROLE_LABELS[data.role]}.`
        : `Nível de ${username} agora é ${data.tier_name}.`;
  } catch (err) {
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
}

loadUsers();
