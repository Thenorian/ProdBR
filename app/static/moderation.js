const queueEl = document.getElementById("queue");

async function loadQueue() {
  if (!isLoggedIn()) {
    queueEl.innerHTML = `<p class="error">Você precisa <a href="/login">entrar</a> com uma conta de moderador.</p>`;
    return;
  }

  try {
    const res = await authFetch("/moderation/queue?limit=10");
    if (res.status === 403) {
      queueEl.innerHTML = `<p class="error">Acesso restrito a moderadores.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const items = await res.json();
    render(items);
  } catch (err) {
    queueEl.innerHTML = `<p class="error">Erro ao carregar fila: ${err.message}</p>`;
  }
}

function render(items) {
  if (!items || items.length === 0) {
    queueEl.innerHTML = '<p class="empty">Fila vazia — nada pendente no momento.</p>';
    return;
  }

  queueEl.innerHTML = items
    .map((item) => {
      const action = item.entity_id ? "update" : "create";
      return `
      <div class="mod-item" data-id="${item.id}">
        <div class="feed-title">
          ${avatarHtml(item.contributor)} ${escapeHtml(item.contributor)}
          <span class="badge badge-pending">pendente</span>
          <span class="badge badge-${action}">${action}</span>
          <span class="badge">${entityLabel(item.entity_type)}</span>
        </div>
        <div class="feed-meta">${timeAgo(item.created_at)}${item.entity_id ? ` · alterando ${escapeHtml(item.entity_id)}` : ""}</div>
        <div class="feed-reason">"${escapeHtml(item.reason)}"</div>
        <pre>${escapeHtml(JSON.stringify(item.payload, null, 2))}</pre>
        <div class="mod-actions">
          <button class="btn btn-approve btn-sm" data-action="approve">Aprovar</button>
          <button class="btn btn-reject btn-sm" data-action="reject">Rejeitar</button>
          <input type="text" class="reject-note" placeholder="motivo da rejeição (opcional)" style="flex:1;padding:.35rem .6rem;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--fg);" />
        </div>
        <div class="form-message" hidden></div>
      </div>`;
    })
    .join("");

  queueEl.querySelectorAll(".mod-item").forEach((el) => {
    const id = el.dataset.id;
    el.querySelector('[data-action="approve"]').addEventListener("click", () => decide(id, "approve", el));
    el.querySelector('[data-action="reject"]').addEventListener("click", () => decide(id, "reject", el));
  });
}

async function decide(id, action, el) {
  const messageEl = el.querySelector(".form-message");
  const note = el.querySelector(".reject-note").value;
  try {
    const res = await authFetch(`/moderation/${id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: action === "reject" ? JSON.stringify({ note: note || null }) : undefined,
    });
    const body = await res.json();
    if (!res.ok) {
      messageEl.hidden = false;
      messageEl.className = "form-message error";
      messageEl.textContent = body.detail || "Erro ao processar.";
      return;
    }
    el.style.opacity = ".5";
    el.querySelectorAll("button").forEach((b) => (b.disabled = true));
    messageEl.hidden = false;
    messageEl.className = "form-message success";
    messageEl.textContent = action === "approve" ? "Aprovado e aplicado." : "Rejeitado.";
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
}

loadQueue();
