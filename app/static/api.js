// "Testar agora" da pagina /api: monta a URL da consulta e mostra o JSON.
const tryForm = document.getElementById("api-try");
const countrySel = document.getElementById("try-country");
const stateSel = document.getElementById("try-state");
let apiCountries = [];

async function loadStates() {
  const country = apiCountries.find((c) => c.id === countrySel.value) || {};
  document.getElementById("try-state-label").textContent = country.subdivision_label || "UF";
  const states = await fetch(`/countries/${encodeURIComponent(countrySel.value)}/states`).then((r) => r.json());
  stateSel.innerHTML =
    `<option value="">(sem — só nacionais)</option>` +
    states.map((s) => `<option value="${escapeHtml(s.code)}">${escapeHtml(s.name)} (${escapeHtml(s.code)})</option>`).join("");
  const preferred = { BR: "SP", AR: "B", PY: "ASU", UY: "MO" }[countrySel.value];
  if (preferred && states.some((s) => s.code === preferred)) stateSel.value = preferred;
  updateUrl();
}

function currentUrl() {
  const code = document.getElementById("try-code").value.replace(/\D/g, "");
  const lang = document.getElementById("try-lang").value;
  const parts = ["/v1", encodeURIComponent(countrySel.value)];
  if (stateSel.value) parts.push(encodeURIComponent(stateSel.value));
  parts.push(code || "{ncm}");
  return parts.join("/") + (lang ? `?lang=${lang}` : "");
}

function updateUrl() {
  document.getElementById("try-url").textContent = window.location.origin + currentUrl();
}

tryForm.addEventListener("input", updateUrl);
tryForm.addEventListener("change", updateUrl);
countrySel.addEventListener("change", loadStates);
tryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = document.getElementById("try-result");
  out.hidden = false;
  out.textContent = "Consultando...";
  try {
    const res = await fetch(currentUrl());
    out.textContent = JSON.stringify(await res.json(), null, 2);
  } catch (err) {
    out.textContent = `Erro: ${err.message}`;
  }
});

(async () => {
  apiCountries = await fetch("/countries").then((r) => r.json());
  countrySel.innerHTML = apiCountries
    .map((c) => `<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)} (${escapeHtml(c.id)})</option>`)
    .join("");
  countrySel.value = apiCountries.some((c) => c.id === "BR") ? "BR" : apiCountries[0]?.id;
  await loadStates();
})();
