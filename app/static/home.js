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

  const MAX_PER_SECTION = 6;
  portalEl.innerHTML = [...sections.entries()]
    .map(([section, items]) => {
      const shown = items.slice(0, MAX_PER_SECTION);
      const more = items.length - shown.length;
      return `
      <div class="portal-section">
        <h3>${escapeHtml(section)}</h3>
        <ul>
          ${shown.map((p) => `<li><a href="/view/products/${encodeURIComponent(p.id)}">${escapeHtml(p.name)}</a></li>`).join("")}
        </ul>
        ${more > 0 ? `<a class="portal-more" href="/?q=${encodeURIComponent(section)}">+ ${more} produto(s)</a>` : ""}
      </div>`;
    })
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
      const LINKABLE = {
        product: (id) => `/view/products/${encodeURIComponent(id)}?tab=history`,
        ncm_classification: (id) => `/view/ncm/${encodeURIComponent(id)}?tab=history`,
      };
      const href = LINKABLE[r.entity_type]?.(r.entity_id) || "#";
      const tag = LINKABLE[r.entity_type] ? "a" : "div";
      const label = r.entity_name || `${entityLabel(r.entity_type)} ${r.entity_id}`;
      return `
      <${tag} class="change-row" ${LINKABLE[r.entity_type] ? `href="${href}"` : ""}>
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

const latestEl = document.getElementById("latest");

async function loadLatestCards() {
  try {
    const res = await fetch("/products?sort=recent&limit=10");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const fiscalResults = await Promise.all(
      data.items.map((p) =>
        p.ncm
          ? fetch(`/products/${encodeURIComponent(p.id)}/fiscal`)
              .then((r) => (r.ok ? r.json() : null))
              .catch(() => null)
          : Promise.resolve(null)
      )
    );
    renderLatestCards(data.items, fiscalResults);
  } catch (err) {
    latestEl.innerHTML = `<p class="error">Erro ao carregar últimos cadastrados: ${err.message}</p>`;
  }
}

function renderLatestCards(products, fiscalByIndex) {
  if (!products.length) {
    latestEl.innerHTML = '<p class="empty">Nenhum produto cadastrado ainda. <a href="/new">Seja o primeiro</a>.</p>';
    return;
  }
  latestEl.innerHTML = products
    .map((p, i) => {
      const fiscal = fiscalByIndex[i];
      const barcode = p.identifiers[0]?.value;
      const taxes = fiscal
        ? [
            fiscal.icms_rate != null ? `ICMS ${fiscal.icms_rate}%` : null,
            fiscal.ipi_rate != null ? `IPI ${fiscal.ipi_rate}%` : null,
            fiscal.pis_rate != null ? `PIS ${fiscal.pis_rate}%` : null,
            fiscal.cofins_rate != null ? `COFINS ${fiscal.cofins_rate}%` : null,
          ]
            .filter(Boolean)
            .join(" · ")
        : null;
      return `
      <a class="card" href="/view/products/${encodeURIComponent(p.id)}">
        <h3>${escapeHtml(p.name)}</h3>
        <dl>
          <dt>NCM</dt><dd>${p.ncm ? escapeHtml(p.ncm) : "—"}</dd>
          <dt>Código de barras</dt><dd>${barcode ? escapeHtml(barcode) : "—"}</dd>
          <dt>Alíquotas</dt><dd>${taxes || "sem regra fiscal cadastrada"}</dd>
        </dl>
      </a>`;
    })
    .join("");
}

const GLOSSARY_LABELS = {
  gtin: "GTIN",
  ncm: "NCM",
  cest: "CEST",
  uf: "UF",
  origin: "Origem (ICMS)",
  icms: "ICMS",
  ipi: "IPI",
  pis: "PIS",
  cofins: "COFINS",
  cbs: "CBS",
  ibs: "IBS",
  ii: "II",
  fcp: "FCP",
  country: "País (Mercosul)",
};

function renderGlossary() {
  const el = document.getElementById("glossary");
  if (!el) return;
  el.innerHTML = Object.entries(GLOSSARY)
    .map(([key, text]) => `<dt>${GLOSSARY_LABELS[key] || key.toUpperCase()}</dt><dd>${escapeHtml(text)}</dd>`)
    .join("");
}

loadStats();
loadLatestCards();
loadRecentPortal();
loadChanges();
renderGlossary();
