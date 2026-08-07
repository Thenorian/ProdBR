const root = document.getElementById("product-root");
const productId = window.PRODUCT_ID;

const IDENTIFIER_TYPES = [
  ["gtin13", "GTIN-13"],
  ["gtin8", "GTIN-8"],
  ["gtin12", "GTIN-12"],
  ["gtin14", "GTIN-14"],
  ["upc", "UPC"],
  ["ean", "EAN"],
  ["manufacturer_code", "Código do fabricante"],
  ["other", "Outro"],
];

async function loadProduct() {
  try {
    const [productRes, revisionsRes] = await Promise.all([
      fetch(`/products/${encodeURIComponent(productId)}`),
      fetch(`/products/${encodeURIComponent(productId)}/revisions?limit=10`),
    ]);

    if (!productRes.ok) {
      root.innerHTML = '<p class="error">Produto não encontrado. <a href="/">Voltar</a></p>';
      return;
    }

    const product = await productRes.json();
    const revisions = revisionsRes.ok ? await revisionsRes.json() : [];

    let fiscal = null;
    const fiscalRes = await fetch(`/products/${encodeURIComponent(productId)}/fiscal`);
    if (fiscalRes.ok) fiscal = await fiscalRes.json();

    currentFiscal = fiscal;
    currentRevisions = revisions;
    render(product, fiscal, revisions);
  } catch (err) {
    root.innerHTML = `<p class="error">Erro ao carregar: ${err.message}</p>`;
  }
}

function field(label, name, value, helpKey, extraAttrs = "", full = false) {
  return `
    <div class="form-group${full ? " full" : ""}">
      <label>${label}${helpKey ? helpIcon(helpKey) : ""}</label>
      <input name="${name}" value="${escapeHtml(value ?? "")}" ${extraAttrs} />
    </div>`;
}

function identifierRow(i) {
  const typeLabel = IDENTIFIER_TYPES.find((t) => t[0] === i.type)?.[1] || i.type;
  return `
    <tr data-id-row="${i.id}" data-type="${escapeHtml(i.type)}" data-value="${escapeHtml(i.value)}">
      <td>${escapeHtml(typeLabel)}</td>
      <td><code>${escapeHtml(i.value)}</code></td>
      <td class="edit-only id-row-actions">
        <button type="button" class="btn-link" data-edit-id="${i.id}">editar</button>
        <button type="button" class="btn-link remove-id-btn" data-remove-id="${i.id}">remover</button>
      </td>
    </tr>`;
}

function fiscalRows(fiscal) {
  if (!fiscal) {
    return `<tr><td colspan="2">Sem regra fiscal cadastrada para este NCM.</td></tr>`;
  }
  const rows = [
    ["País", fiscal.country ? escapeHtml(fiscal.country) : "BR", "country"],
    ["Escopo", fiscal.uf ? `Estado ${fiscal.uf}` : "Nacional (padrão)", "uf"],
    ["Origem", fiscal.origin != null ? fiscal.origin : "—", "origin"],
    ["ICMS", fiscal.icms_rate != null ? `${fiscal.icms_rate}%` : "—", "icms"],
    ["FCP", fiscal.fcp_rate != null ? `${fiscal.fcp_rate}%` : "—", "fcp"],
    ["MVA (ICMS-ST)", fiscal.icms_st_mva_rate != null ? `${fiscal.icms_st_mva_rate}%` : "—", null],
    ["IPI", fiscal.ipi_rate != null ? `${fiscal.ipi_rate}%` : "—", "ipi"],
    ["II", fiscal.ii_rate != null ? `${fiscal.ii_rate}%` : "—", "ii"],
    ["PIS", fiscal.pis_rate != null ? `${fiscal.pis_rate}%` : "—", "pis"],
    ["COFINS", fiscal.cofins_rate != null ? `${fiscal.cofins_rate}%` : "—", "cofins"],
    ["CBS", fiscal.cbs_rate != null ? `${fiscal.cbs_rate}%` : "—", "cbs"],
    ["IBS", fiscal.ibs_rate != null ? `${fiscal.ibs_rate}%` : "—", "ibs"],
    ["Vigência", fiscal.valid_until ? `${fiscal.valid_from} a ${fiscal.valid_until}` : `desde ${fiscal.valid_from}`, null],
    ["Fonte", escapeHtml(fiscal.source), null],
    ...(fiscal.notes ? [["Observações", escapeHtml(fiscal.notes), null]] : []),
  ];
  return rows
    .map(([k, v, help]) => `<tr><th>${k}${help ? helpIcon(help) : ""}</th><td>${v}</td></tr>`)
    .join("");
}

function render(product, fiscal, revisions) {
  root.innerHTML = `
    <div class="article-header">
      <h1>${escapeHtml(product.name)}</h1>
      <div class="article-subtitle">${escapeHtml(product.id)} · cadastrado ${timeAgo(product.created_at)} · atualizado ${timeAgo(product.updated_at)}</div>
    </div>

    <div class="tab-bar">
      <button class="tab-btn active" data-tab="article">Ficha do produto</button>
      <button class="tab-btn" data-tab="history">Histórico</button>
    </div>

    <div class="tab-panel active" id="tab-article">
      <div class="product-form-wrap" id="product-form-wrap">
        <div class="product-form">
          <div class="product-form-header">
            <h2>Ficha do produto</h2>
            <button type="button" id="edit-toggle" class="btn btn-outline btn-sm view-only">✎ Editar</button>
          </div>

          <form id="product-form">
            <fieldset id="product-fieldset" disabled>
              <div class="form-grid">
                ${field("Nome", "name", product.name, null, "", true)}
                ${field("Marca", "brand", product.brand)}
                ${field("Fabricante", "manufacturer", product.manufacturer)}
                ${field("NCM", "ncm", product.ncm, "ncm", 'maxlength="8"')}
                ${field("CEST", "cest", product.cest, "cest", 'maxlength="7"')}
                <div class="form-group">
                  <label>Categoria</label>
                  <input name="category" value="${escapeHtml(product.category ?? "")}" list="category-suggestions" />
                </div>
                ${field("Unidade comercial", "commercial_unit", product.commercial_unit)}
                <div class="form-group full">
                  <label>Descrição</label>
                  <textarea name="description">${escapeHtml(product.description ?? "")}</textarea>
                </div>
                ${field("Fonte", "source", product.source, null, "", true)}
              </div>
            </fieldset>

            <h3 class="section-title">Identificadores${helpIcon("gtin")}</h3>
            <table class="id-table">
              <thead><tr><th>Tipo</th><th>Código</th><th class="edit-only"></th></tr></thead>
              <tbody id="id-rows">
                ${product.identifiers.length ? product.identifiers.map(identifierRow).join("") : '<tr><td colspan="3" class="view-only">nenhum cadastrado</td></tr>'}
              </tbody>
            </table>
            <div class="add-identifier-row edit-only">
              <select id="new-id-type">${IDENTIFIER_TYPES.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
              <input id="new-id-value" placeholder="Código" />
              <button type="button" id="add-identifier-btn" class="btn btn-sm btn-outline">+ Adicionar</button>
            </div>

            <h3 class="section-title">Dados fiscais${helpIcon("ncm")}</h3>
            <table class="fiscal-table">${fiscalRows(fiscal)}</table>
            <p class="form-hint">
              Regras fiscais são compartilhadas por NCM e editadas na ficha do NCM, não aqui na ficha do produto.
              ${product.ncm ? `<a href="/view/ncm/${encodeURIComponent(product.ncm)}">Ver ficha completa do NCM ${escapeHtml(product.ncm)} →</a>` : ""}
            </p>

            <div class="edit-only form-group full" style="margin-top:1rem;">
              <label>Motivo da alteração *</label>
              <input name="reason" id="edit-reason" placeholder="Por que você está mudando isso?" />
            </div>
            <div class="edit-only form-actions">
              <button type="submit" class="btn">Salvar alterações</button>
              <button type="button" id="cancel-edit" class="btn btn-outline">Cancelar</button>
            </div>
          </form>
          <div class="form-message" id="edit-message" hidden></div>
        </div>
      </div>
    </div>

    <div class="tab-panel" id="tab-history">
      <div class="history-list">${renderHistory(revisions)}</div>
    </div>
  `;

  root.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  wireEditing(product);

  const initialTab = new URLSearchParams(window.location.search).get("tab");
  if (initialTab) activateTab(initialTab);
}

function activateTab(name) {
  root.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  root.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${name}`));
}

function renderHistory(revisions) {
  if (!revisions || revisions.length === 0) {
    return '<p class="empty">Nenhuma edição registrada ainda.</p>';
  }
  return revisions
    .map((r) => {
      const who = r.contributor || "sistema";
      const diff =
        r.action === "create"
          ? `definido como <strong>${escapeHtml(JSON.parse(r.new_value ?? "null"))}</strong>`
          : `<strong>${escapeHtml(JSON.parse(r.old_value ?? "null"))}</strong><span class="arrow">→</span><strong>${escapeHtml(JSON.parse(r.new_value ?? "null"))}</strong>`;
      return `
      <div class="history-row">
        <span class="history-time">${new Date(r.created_at + "Z").toLocaleString("pt-BR")}</span>
        · <span class="history-user">${escapeHtml(who)}</span>
        <span class="badge badge-${r.action}">${r.action}</span>
        <div class="history-diff"><code class="history-field">${escapeHtml(r.field)}</code> ${diff}</div>
        <span class="history-reason">"${escapeHtml(r.reason)}"</span>
      </div>`;
    })
    .join("");
}

function wireEditing(product) {
  const wrap = document.getElementById("product-form-wrap");
  const fieldset = document.getElementById("product-fieldset");
  const toggleBtn = document.getElementById("edit-toggle");
  const cancelBtn = document.getElementById("cancel-edit");
  const form = document.getElementById("product-form");
  const messageEl = document.getElementById("edit-message");

  if (!isLoggedIn()) {
    toggleBtn.replaceWith(document.createTextNode(""));
    const hint = document.createElement("p");
    hint.className = "form-hint view-only";
    hint.innerHTML = '<a href="/login">Entre</a> para editar este produto.';
    wrap.querySelector(".product-form-header").appendChild(hint);
  } else {
    toggleBtn.addEventListener("click", () => setEditing(true));
    cancelBtn.addEventListener("click", () => {
      setEditing(false);
      render(product, currentFiscal, currentRevisions); // reset any unsaved changes
    });
  }

  function setEditing(on) {
    fieldset.disabled = !on;
    wrap.classList.toggle("is-editing", on);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const reason = document.getElementById("edit-reason").value.trim();
    if (!reason) {
      showMessage(messageEl, "error", "Preencha o motivo da alteração.");
      return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    const payload = { reason };
    for (const key of ["name", "brand", "manufacturer", "ncm", "cest", "category", "commercial_unit", "description", "source"]) {
      payload[key] = data[key] || null;
    }
    await submitContribution(`/products/${encodeURIComponent(productId)}`, "PUT", payload, messageEl);
  });

  document.getElementById("add-identifier-btn").addEventListener("click", async () => {
    const type = document.getElementById("new-id-type").value;
    const value = document.getElementById("new-id-value").value.trim();
    const reason = document.getElementById("edit-reason").value.trim() || "Identificador adicional";
    if (!value) {
      showMessage(messageEl, "error", "Informe o código do identificador.");
      return;
    }
    await submitContribution("/identifiers", "POST", { product_id: productId, type, value, reason }, messageEl);
  });

  root.querySelectorAll("[data-remove-id]").forEach((btn) => {
    btn.addEventListener("click", () => startRemoveIdentifier(btn));
  });
  root.querySelectorAll("[data-edit-id]").forEach((btn) => {
    btn.addEventListener("click", () => startEditIdentifier(btn));
  });

  function startEditIdentifier(btn) {
    const row = btn.closest("tr");
    const idId = btn.dataset.editId;
    const currentType = row.dataset.type;
    const currentValue = row.dataset.value;
    row.innerHTML = `
      <td>
        <select class="edit-id-type">
          ${IDENTIFIER_TYPES.map(([v, l]) => `<option value="${v}" ${v === currentType ? "selected" : ""}>${l}</option>`).join("")}
        </select>
      </td>
      <td><input class="edit-id-value" value="${escapeHtml(currentValue)}" /></td>
      <td class="edit-only id-row-actions">
        <div class="inline-remove-form">
          <input type="text" placeholder="motivo" class="edit-id-reason-input" />
          <button type="button" class="btn-link confirm-edit-id-btn">salvar</button>
          <button type="button" class="btn-link cancel-edit-id-btn">cancelar</button>
        </div>
      </td>`;
    row.querySelector(".cancel-edit-id-btn").addEventListener("click", () => render(product, currentFiscal, currentRevisions));
    row.querySelector(".confirm-edit-id-btn").addEventListener("click", async () => {
      const type = row.querySelector(".edit-id-type").value;
      const value = row.querySelector(".edit-id-value").value.trim();
      const reason = row.querySelector(".edit-id-reason-input").value.trim() || "Identificador corrigido";
      if (!value) {
        showMessage(messageEl, "error", "Informe o código do identificador.");
        return;
      }
      await submitContribution(`/identifiers/${idId}`, "PUT", { type, value, reason }, messageEl);
    });
  }

  function startRemoveIdentifier(btn) {
    const row = btn.closest("tr");
    const idId = btn.dataset.removeId;
    const cell = btn.closest("td");
    cell.innerHTML = `
      <div class="inline-remove-form">
        <input type="text" placeholder="motivo" class="remove-reason-input" />
        <button type="button" class="confirm-remove-btn">confirmar</button>
        <button type="button" class="cancel-remove-btn">cancelar</button>
      </div>`;
    cell.querySelector(".cancel-remove-btn").addEventListener("click", () => render(product, currentFiscal, currentRevisions));
    cell.querySelector(".confirm-remove-btn").addEventListener("click", async () => {
      const reason = cell.querySelector(".remove-reason-input").value.trim() || "Identificador removido";
      await submitContribution(`/identifiers/${idId}`, "DELETE", { reason }, messageEl);
    });
  }
}

let currentFiscal = null;
let currentRevisions = [];

async function submitContribution(url, method, payload, messageEl) {
  showMessage(messageEl, null, "");
  messageEl.hidden = true;
  try {
    const res = await authFetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (res.status === 202) {
      showMessage(messageEl, "success", "Reputação insuficiente para aplicar direto — enviado para moderação.");
    } else if (res.ok) {
      showMessage(messageEl, "success", "Contribuição aplicada. Recarregando...");
      setTimeout(loadProduct, 900);
    } else {
      showMessage(messageEl, "error", body.detail ? JSON.stringify(body.detail) : "Erro ao enviar.");
    }
  } catch (err) {
    showMessage(messageEl, "error", err.message);
  }
}

function showMessage(el, kind, text) {
  if (!kind) return;
  el.hidden = false;
  el.className = `form-message ${kind}`;
  el.textContent = text;
}

loadProduct();
