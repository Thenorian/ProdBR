const input = document.getElementById("query");
const button = document.getElementById("search-btn");
const results = document.getElementById("results");

async function search() {
  const q = input.value.trim();
  if (!q) {
    results.innerHTML = "";
    return;
  }

  results.innerHTML = '<p class="empty">Buscando...</p>';

  const looksLikeIdentifier = /^\d{6,14}$/.test(q);
  const looksLikeNcm = /^\d{8}$/.test(q);

  const params = new URLSearchParams();
  if (looksLikeNcm) params.set("ncm", q);
  else if (looksLikeIdentifier) params.set("identifier", q);
  else params.set("q", q);

  try {
    const res = await fetch(`/products?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data.items);
  } catch (err) {
    results.innerHTML = `<p class="error">Erro ao buscar: ${err.message}</p>`;
  }
}

function render(items) {
  if (!items || items.length === 0) {
    results.innerHTML = '<p class="empty">Nenhum produto encontrado.</p>';
    return;
  }

  results.innerHTML = items
    .map(
      (p) => `
    <article class="card">
      <h3>${escapeHtml(p.name)}</h3>
      <dl>
        ${p.brand ? `<dt>Marca</dt><dd>${escapeHtml(p.brand)}</dd>` : ""}
        <dt>NCM</dt><dd>${escapeHtml(p.ncm)}</dd>
        ${p.cest ? `<dt>CEST</dt><dd>${escapeHtml(p.cest)}</dd>` : ""}
        <dt>Identificadores</dt><dd>${p.identifiers.map((i) => escapeHtml(i.value)).join(", ") || "-"}</dd>
        <dt>Unidade</dt><dd>${escapeHtml(p.commercial_unit)}</dd>
        <dt>Fonte</dt><dd>${escapeHtml(p.source)}</dd>
      </dl>
      <p class="card-links"><a href="/products/${encodeURIComponent(p.id)}/fiscal" target="_blank" rel="noopener">Ver alíquotas</a></p>
    </article>`
    )
    .join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

button.addEventListener("click", search);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
