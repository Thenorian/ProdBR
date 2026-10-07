const usersEl = document.getElementById("users");
const ROLE_LABELS = { member: "Membro", moderator: "Moderador", admin: "Administrador" };

async function loadUsers() {
  if (!isLoggedIn()) {
    usersEl.innerHTML = `<p class="error">Você precisa <a href="/login">entrar</a> com uma conta de administrador.</p>`;
    return;
  }

  try {
    const res = await authFetch("/admin/users");
    if (res.status === 403) {
      usersEl.innerHTML = `<p class="error">Acesso restrito a administradores.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (err) {
    usersEl.innerHTML = `<p class="error">Erro ao carregar usuários: ${escapeHtml(err.message)}</p>`;
  }
}

function render(users) {
  const me = getAuth().username;
  usersEl.innerHTML = users
    .map((u) => {
      const options = Object.entries(ROLE_LABELS)
        .map(([value, label]) => `<option value="${value}" ${u.role === value ? "selected" : ""}>${label}</option>`)
        .join("");
      const self = u.username === me;
      return `
      <div class="mod-item" data-username="${escapeHtml(u.username)}">
        <div class="feed-title">
          ${avatarHtml(u.username)} ${escapeHtml(u.username)} ${tierBadgeHtml(u)}
          ${self ? '<span class="badge">você</span>' : ""}
        </div>
        <div class="feed-meta">${escapeHtml(u.email)} · reputação ${u.reputation} · ${u.edit_count} edições · desde ${timeAgo(u.created_at)}</div>
        <div class="mod-actions">
          <select class="role-select" ${self ? "disabled" : ""}>${options}</select>
          <button class="btn btn-sm" data-action="save" ${self ? "disabled" : ""}>Salvar</button>
        </div>
        <div class="form-message" hidden></div>
      </div>`;
    })
    .join("");

  usersEl.querySelectorAll(".mod-item").forEach((el) => {
    el.querySelector('[data-action="save"]').addEventListener("click", () => saveRole(el));
  });
}

async function saveRole(el) {
  const username = el.dataset.username;
  const role = el.querySelector(".role-select").value;
  const messageEl = el.querySelector(".form-message");
  messageEl.hidden = false;
  try {
    const res = await authFetch(`/admin/users/${encodeURIComponent(username)}/role`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    const body = await res.json();
    if (!res.ok) {
      messageEl.className = "form-message error";
      messageEl.textContent = body.detail || "Erro ao salvar.";
      return;
    }
    messageEl.className = "form-message success";
    messageEl.textContent = `Papel de ${username} agora é ${ROLE_LABELS[body.role]}.`;
  } catch (err) {
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
}

loadUsers();
