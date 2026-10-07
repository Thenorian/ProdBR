const queueEl = document.getElementById("queue");
let isModerator = false;

async function loadQueue() {
  if (!isLoggedIn()) {
    queueEl.innerHTML = `<p class="error">Você precisa <a href="/login">entrar</a> para ver e votar nas contribuições pendentes.</p>`;
    return;
  }

  try {
    const [res, profileRes] = await Promise.all([
      authFetch("/moderation/queue?limit=10"),
      fetch(`/users/${encodeURIComponent(getAuth().username)}`),
    ]);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const profile = profileRes.ok ? await profileRes.json() : {};
    isModerator = profile.role === "moderator" || profile.role === "admin";
    render(await res.json());
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
        <div class="mod-actions vote-actions">
          ${voteHtml(item)}
        </div>
        ${isModerator ? `
        <div class="mod-actions">
          <button class="btn btn-approve btn-sm" data-action="approve">Aprovar</button>
          <button class="btn btn-reject btn-sm" data-action="reject">Rejeitar</button>
          <input type="text" class="reject-note" placeholder="motivo da rejeição (opcional)" />
        </div>` : ""}
        <div class="form-message" hidden></div>
      </div>`;
    })
    .join("");

  queueEl.querySelectorAll(".mod-item").forEach(bindItem);
}

function voteHtml(item) {
  const score = item.votes_for - item.votes_against;
  const mine = (v) => (item.my_vote === v ? "active" : "");
  return `
    <button class="btn btn-sm btn-vote ${mine(1)}" data-vote="1" title="A favor">▲ ${item.votes_for}</button>
    <button class="btn btn-sm btn-vote ${mine(-1)}" data-vote="-1" title="Contra">▼ ${item.votes_against}</button>
    <span class="vote-score">saldo ${score} de ${item.vote_threshold} para aprovar sozinha</span>`;
}

function bindItem(el) {
  const id = el.dataset.id;
  el.querySelectorAll("[data-vote]").forEach((btn) =>
    btn.addEventListener("click", () => {
      // Clicar no voto que já é o seu retira o voto.
      const value = btn.classList.contains("active") ? 0 : Number(btn.dataset.vote);
      castVote(id, value, el);
    })
  );
  el.querySelector('[data-action="approve"]')?.addEventListener("click", () => decide(id, "approve", el));
  el.querySelector('[data-action="reject"]')?.addEventListener("click", () => decide(id, "reject", el));
}

async function castVote(id, value, el) {
  const messageEl = el.querySelector(".form-message");
  try {
    const res = await authFetch(`/moderation/${id}/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    const body = await res.json();
    if (!res.ok) {
      messageEl.hidden = false;
      messageEl.className = "form-message error";
      messageEl.textContent = body.detail || "Erro ao votar.";
      return;
    }
    el.querySelector(".vote-actions").innerHTML = voteHtml(body);
    bindItem(el);
    if (body.status !== "pending") {
      el.style.opacity = ".5";
      el.querySelectorAll("button").forEach((b) => (b.disabled = true));
      messageEl.hidden = false;
      messageEl.className = "form-message success";
      messageEl.textContent =
        body.status === "approved" ? "Aprovada pela comunidade e aplicada." : "Rejeitada pela comunidade.";
    }
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
}

async function decide(id, action, el) {
  const messageEl = el.querySelector(".form-message");
  const note = el.querySelector(".reject-note")?.value;
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
