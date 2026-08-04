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

  const looksLikeBarcode = /^\d{6,14}$/.test(q);
  const looksLikeNcm = /^\d{8}$/.test(q);

  const params = new URLSearchParams();
  if (looksLikeBarcode) params.set("barcode", q);
  else if (looksLikeNcm) params.set("ncm", q);
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
      <h3>${escapeHtml(p.description)}</h3>
      <dl>
        <dt>NCM</dt><dd>${escapeHtml(p.ncm)}</dd>
        ${p.cest ? `<dt>CEST</dt><dd>${escapeHtml(p.cest)}</dd>` : ""}
        <dt>Códigos de barras</dt><dd>${p.barcodes.map(escapeHtml).join(", ")}</dd>
        <dt>Unidade</dt><dd>${escapeHtml(p.unit)}</dd>
        ${p.icms_rate != null ? `<dt>ICMS</dt><dd>${p.icms_rate}%</dd>` : ""}
        ${p.ipi_rate != null ? `<dt>IPI</dt><dd>${p.ipi_rate}%</dd>` : ""}
      </dl>
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
