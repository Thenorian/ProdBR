const input = document.getElementById("query");
const button = document.getElementById("search-btn");
const results = document.getElementById("results");
const changesEl = document.getElementById("changes");

async function search() {
  const q = input.value.trim();
  if (!q) {
    results.innerHTML = "";
    return;
  }

  results.innerHTML = '<p class="empty">Buscando...</p>';

  const looksLikeNcm = /^\d{8}$/.test(q);
  const looksLikeIdentifier = /^\d{6,14}$/.test(q);

  const params = new URLSearchParams();
  if (looksLikeNcm) params.set("ncm", q);
  else if (looksLikeIdentifier) params.set("identifier", q);
  else params.set("q", q);

  try {
    const res = await fetch(`/products?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderResults(data.items);
  } catch (err) {
    results.innerHTML = `<p class="error">Erro ao buscar: ${err.message}</p>`;
  }
}

function renderResults(items) {
  if (!items || items.length === 0) {
    results.innerHTML = '<p class="empty">Nenhum produto encontrado. <a href="/new">Cadastre este produto</a>.</p>';
    return;
  }

  results.innerHTML = items
    .map(
      (p) => `
    <a class="card" href="/view/products/${encodeURIComponent(p.id)}">
      <h3>${escapeHtml(p.name)}</h3>
      <dl>
        ${p.brand ? `<dt>Marca</dt><dd>${escapeHtml(p.brand)}</dd>` : ""}
        <dt>NCM</dt><dd>${escapeHtml(p.ncm)}</dd>
        <dt>Identificadores</dt><dd>${p.identifiers.map((i) => escapeHtml(i.value)).join(", ") || "-"}</dd>
      </dl>
    </a>`
    )
    .join("");
}

const portalEl = document.getElementById("portal");

async function loadRecentPortal() {
  try {
    const pages = await Promise.all(
      [0, 10, 20, 30, 40].map((offset) =>
        fetch(`/products?sort=recent&limit=10&offset=${offset}`).then((r) => (r.ok ? r.json() : { items: [] }))
      )
    );
    const products = pages.flatMap((p) => p.items);
    renderPortal(products);
  } catch (err) {
    portalEl.innerHTML = `<p class="error">Erro ao carregar produtos recentes: ${err.message}</p>`;
  }
}

function renderPortal(products) {
  if (!products.length) {
    portalEl.innerHTML = '<p class="empty">Nenhum produto cadastrado ainda. <a href="/new">Seja o primeiro</a>.</p>';
    return;
  }

  const sections = new Map();
  for (const p of products) {
    const section = (p.category || "Sem categoria").split(">")[0].trim();
    if (!sections.has(section)) sections.set(section, []);
    sections.get(section).push(p);
  }

  portalEl.innerHTML = [...sections.entries()]
    .map(
      ([section, items]) => `
      <div class="portal-section">
        <h3>${escapeHtml(section)}</h3>
        <ul>
          ${items.map((p) => `<li><a href="/view/products/${encodeURIComponent(p.id)}">${escapeHtml(p.name)}</a></li>`).join("")}
        </ul>
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
    document.getElementById("stat-revisions").textContent = stats.revisions;
  } catch {
    // estatisticas sao so um detalhe cosmetico - falha silenciosa
  }
}

async function loadChanges() {
  try {
    const res = await fetch("/revisions?limit=10");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const revisions = await res.json();
    renderChanges(revisions);
  } catch (err) {
    changesEl.innerHTML = `<p class="error">Erro ao carregar mudanças: ${err.message}</p>`;
  }
}

const DIFF_TAG = { create: "+", update: "±", delete: "−" };

function renderChanges(revisions) {
  if (!revisions || revisions.length === 0) {
    changesEl.innerHTML = '<p class="empty">Nenhuma edição ainda — seja o primeiro a contribuir.</p>';
    return;
  }

  changesEl.innerHTML = revisions
    .map((r) => {
      const who = r.contributor || "sistema";
      const href = r.entity_type === "product" ? `/view/products/${encodeURIComponent(r.entity_id)}?tab=history` : "#";
      const tag = r.entity_type === "product" ? "a" : "div";
      const label = r.entity_name || `${entityLabel(r.entity_type)} ${r.entity_id}`;
      return `
      <${tag} class="change-row" ${r.entity_type === "product" ? `href="${href}"` : ""}>
        <span class="diff-tag ${r.action}">${DIFF_TAG[r.action] || "•"}</span>
        <span class="change-entity">${escapeHtml(label)}</span>
        <span class="badge">${entityLabel(r.entity_type)}</span>
        ${r.field ? `<code class="history-field">${escapeHtml(r.field)}</code>` : ""}
        <span class="change-time">· ${timeAgo(r.created_at)}</span> ·
        <span class="change-user">${escapeHtml(who)}</span>
        <span class="change-reason">"${escapeHtml(r.reason)}"</span>
      </${tag}>`;
    })
    .join("");
}

button.addEventListener("click", search);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});

const params = new URLSearchParams(window.location.search);
const initialQuery = params.get("q");
if (initialQuery) {
  input.value = initialQuery;
  search();
}

loadStats();
loadRecentPortal();
loadChanges();
