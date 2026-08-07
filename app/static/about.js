const contributorsEl = document.getElementById("contributors-list");

async function loadContributors() {
  try {
    const res = await fetch("/users?limit=20");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const users = await res.json();
    renderContributors(users);
  } catch (err) {
    contributorsEl.innerHTML = `<p class="error">Erro ao carregar contribuidores: ${err.message}</p>`;
  }
}

function renderContributors(users) {
  if (!users || users.length === 0) {
    contributorsEl.innerHTML = '<p class="empty">Ninguém contribuiu ainda. <a href="/register">Seja o primeiro</a>.</p>';
    return;
  }
  contributorsEl.innerHTML = users
    .map(
      (u, i) => `
    <div class="contributor-row">
      <span class="contributor-rank">${i + 1}.</span>
      ${avatarHtml(u.username)}
      <a class="contributor-name" href="/users/${encodeURIComponent(u.username)}">${escapeHtml(u.username)}</a>
      <span class="badge">${escapeHtml(u.role)}</span>
      <span class="rep-badge">rep ${u.reputation}</span>
    </div>`
    )
    .join("");
}

async function loadStats() {
  try {
    const res = await fetch("/stats");
    if (!res.ok) return;
    const stats = await res.json();
    document.getElementById("stat-products").textContent = stats.products;
    document.getElementById("stat-ncm").textContent = stats.ncm_classifications;
    document.getElementById("stat-fiscal").textContent = stats.fiscal_rules;
    document.getElementById("stat-revisions").textContent = stats.revisions;
  } catch {
    // estatisticas sao so um detalhe cosmetico - falha silenciosa
  }
}

loadContributors();
loadStats();
