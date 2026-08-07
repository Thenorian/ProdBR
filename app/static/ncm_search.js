const input = document.getElementById("ncm-query");
const button = document.getElementById("ncm-search-btn");
const results = document.getElementById("ncm-results");

async function search() {
  const q = input.value.trim();
  if (!q) {
    results.innerHTML = "";
    return;
  }
  results.innerHTML = '<p class="empty">Buscando...</p>';
  try {
    const res = await fetch(`/ncm?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const items = await res.json();
    renderResults(items);
  } catch (err) {
    results.innerHTML = `<p class="error">Erro ao buscar: ${err.message}</p>`;
  }
}

function renderResults(items) {
  if (!items || items.length === 0) {
    results.innerHTML = '<p class="empty">Nenhum NCM encontrado.</p>';
    return;
  }
  results.innerHTML = items
    .map(
      (n) => `
    <a class="card" href="/view/ncm/${encodeURIComponent(n.ncm)}">
      <h3>${escapeHtml(n.ncm)}</h3>
      <dl>
        <dt>Descrição</dt><dd>${escapeHtml(n.description)}</dd>
        ${n.unit ? `<dt>Unidade</dt><dd>${escapeHtml(n.unit)}</dd>` : ""}
      </dl>
    </a>`
    )
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
