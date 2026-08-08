if (!isLoggedIn()) {
  document.getElementById("guest-notice").hidden = false;
} else {
  document.getElementById("product-form").hidden = false;
}

fetch("/categories?limit=50")
  .then((r) => (r.ok ? r.json() : []))
  .then((names) => {
    const datalist = document.getElementById("category-suggestions");
    if (!datalist) return;
    for (const name of names) {
      if (![...datalist.options].some((o) => o.value === name)) {
        datalist.appendChild(new Option(name));
      }
    }
  })
  .catch(() => {});

// Varios produtos compartilham o mesmo NCM - ao digitar um ja
// cadastrado, mostra a classificacao e as regras fiscais existentes (e
// sugere a categoria), sem precisar sair da tela pra ver a ficha do NCM.
const ncmInput = document.querySelector('[name="ncm"]');
const previewWrap = document.getElementById("ncm-preview-wrap");
const previewEl = document.getElementById("ncm-preview");
const categoryInput = document.querySelector('[name="category"]');
let ncmLookupTimer = null;

ncmInput.addEventListener("input", () => {
  clearTimeout(ncmLookupTimer);
  const code = ncmInput.value.trim();
  if (!/^\d{8}$/.test(code)) {
    previewWrap.hidden = true;
    return;
  }
  ncmLookupTimer = setTimeout(() => lookupNcm(code), 400);
});

async function lookupNcm(code) {
  try {
    const res = await fetch(`/ncm/${encodeURIComponent(code)}`);
    previewWrap.hidden = false;
    if (res.status === 404) {
      previewEl.innerHTML = `<p class="form-hint">NCM ${escapeHtml(code)} ainda não catalogado — pode <a href="/view/ncm/${encodeURIComponent(code)}" target="_blank" rel="noopener">cadastrar a classificação dele</a> depois de salvar este produto.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const ncm = await res.json();

    if (ncm.category && categoryInput && !categoryInput.value) {
      categoryInput.value = ncm.category;
    }

    const rates = (ncm.fiscal_rules || [])
      .filter((f) => f.country === "BR" && !f.uf)
      .slice(0, 1)
      .flatMap((f) => [
        f.icms_rate != null ? `ICMS ${f.icms_rate}%` : null,
        f.ipi_rate != null ? `IPI ${f.ipi_rate}%` : null,
        f.pis_rate != null ? `PIS ${f.pis_rate}%` : null,
        f.cofins_rate != null ? `COFINS ${f.cofins_rate}%` : null,
      ])
      .filter(Boolean)
      .join(" · ");

    previewEl.innerHTML = `
      <div class="ncm-preview-card">
        <strong>${escapeHtml(ncm.ncm)}</strong> — ${escapeHtml(ncm.description)}
        ${ncm.category ? `<span class="badge">${escapeHtml(ncm.category)}</span>` : ""}
        <div class="form-hint">
          ${rates ? `Alíquotas nacionais de referência: ${rates}.` : "Sem regra fiscal nacional cadastrada ainda."}
          <a href="/view/ncm/${encodeURIComponent(ncm.ncm)}" target="_blank" rel="noopener">Ver ficha completa do NCM →</a>
        </div>
      </div>`;
  } catch (err) {
    previewWrap.hidden = true;
  }
}

document.getElementById("product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const messageEl = document.getElementById("message");
  messageEl.hidden = true;

  const data = Object.fromEntries(new FormData(e.target).entries());
  Object.keys(data).forEach((key) => {
    if (data[key] === "") delete data[key];
  });

  try {
    const res = await authFetch("/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await res.json();

    messageEl.hidden = false;
    if (res.status === 202) {
      messageEl.className = "form-message success";
      messageEl.textContent = "Reputação insuficiente para aplicar direto — enviado para a fila de moderação.";
    } else if (res.ok) {
      messageEl.className = "form-message success";
      messageEl.innerHTML = `Produto criado! <a href="/view/products/${encodeURIComponent(body.id)}">Ver produto</a>`;
      e.target.reset();
    } else {
      messageEl.className = "form-message error";
      messageEl.textContent = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join(" ")
        : body.detail || "Erro ao cadastrar.";
    }
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
});
