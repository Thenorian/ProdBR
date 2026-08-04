const root = document.getElementById("product-root");
const productId = window.PRODUCT_ID;

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

    render(product, fiscal, revisions);
  } catch (err) {
    root.innerHTML = `<p class="error">Erro ao carregar: ${err.message}</p>`;
  }
}

function leadParagraph(p, fiscal) {
  const bits = [];
  if (p.brand) bits.push(`da marca <strong>${escapeHtml(p.brand)}</strong>`);
  if (p.manufacturer) bits.push(`fabricado por <strong>${escapeHtml(p.manufacturer)}</strong>`);
  const originSentence = bits.length ? ` é um produto ${bits.join(", ")}` : " é um produto";

  let classification = `classificado no NCM <strong>${escapeHtml(p.ncm)}</strong>`;
  if (p.cest) classification += ` (CEST ${escapeHtml(p.cest)})`;
  if (p.category) classification += `, na categoria <em>${escapeHtml(p.category)}</em>`;

  const idCount = p.identifiers.length;
  const idSentence = idCount
    ? `Possui ${idCount} identificador${idCount > 1 ? "es" : ""} cadastrado${idCount > 1 ? "s" : ""}: ${p.identifiers.map((i) => `<code>${escapeHtml(i.value)}</code>`).join(", ")}.`
    : `Ainda não possui nenhum identificador (código de barras/GTIN) cadastrado.`;

  const fiscalSentence = fiscal
    ? `A alíquota de referência de ICMS é de <strong>${fiscal.icms_rate != null ? fiscal.icms_rate + "%" : "não informada"}</strong> (${fiscal.uf ? `específica do estado ${fiscal.uf}` : "regra nacional"}), vigente desde ${fiscal.valid_from}.`
    : `Ainda não há regra fiscal cadastrada para o NCM deste produto.`;

  return `
    <p><strong>${escapeHtml(p.name)}</strong>${originSentence}, ${classification}. Unidade comercial: <strong>${escapeHtml(p.commercial_unit)}</strong>. Fonte do cadastro: <em>${escapeHtml(p.source)}</em>.</p>
    <p>${idSentence}</p>
    <p>${fiscalSentence}</p>
    ${p.description ? `<p>${escapeHtml(p.description)}</p>` : ""}
  `;
}

function infoboxHtml(p, fiscal) {
  const rows = [
    ["Nome", escapeHtml(p.name)],
    ["Marca", p.brand ? escapeHtml(p.brand) : "—"],
    ["Fabricante", p.manufacturer ? escapeHtml(p.manufacturer) : "—"],
    ["NCM", escapeHtml(p.ncm)],
    ["CEST", p.cest ? escapeHtml(p.cest) : "—"],
    ["Categoria", p.category ? escapeHtml(p.category) : "—"],
    ["Unidade", escapeHtml(p.commercial_unit)],
    [
      "Identificadores",
      p.identifiers.length
        ? `<div class="identifier-list">${p.identifiers.map((i) => `<span>${escapeHtml(i.type)}: <code>${escapeHtml(i.value)}</code></span>`).join("")}</div>`
        : "nenhum",
    ],
    ["Fonte", escapeHtml(p.source)],
    ["ID interno", `<code>${escapeHtml(p.id)}</code>`],
  ];

  const fiscalRows = fiscal
    ? [
        ["Escopo", fiscal.uf ? `UF ${escapeHtml(fiscal.uf)}` : "Nacional"],
        ["ICMS", fiscal.icms_rate != null ? `${fiscal.icms_rate}%` : "—"],
        ["IPI", fiscal.ipi_rate != null ? `${fiscal.ipi_rate}%` : "—"],
        ["PIS", fiscal.pis_rate != null ? `${fiscal.pis_rate}%` : "—"],
        ["COFINS", fiscal.cofins_rate != null ? `${fiscal.cofins_rate}%` : "—"],
        ["CBS", fiscal.cbs_rate != null ? `${fiscal.cbs_rate}%` : "—"],
        ["IBS", fiscal.ibs_rate != null ? `${fiscal.ibs_rate}%` : "—"],
        ["Vigência", fiscal.valid_until ? `${fiscal.valid_from} a ${fiscal.valid_until}` : `desde ${fiscal.valid_from}`],
        ["Fonte fiscal", escapeHtml(fiscal.source)],
      ]
    : [["Alíquotas", "sem regra fiscal cadastrada"]];

  return `
    <aside class="infobox">
      <div class="infobox-header">${escapeHtml(p.name)}</div>
      <table>${rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table>
      <div class="infobox-header">Dados fiscais</div>
      <table>${fiscalRows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table>
    </aside>
  `;
}

function render(product, fiscal, revisions) {
  root.innerHTML = `
    <div class="article-header">
      <h1>${escapeHtml(product.name)}</h1>
      <div class="article-subtitle">cadastrado ${timeAgo(product.created_at)} · atualizado ${timeAgo(product.updated_at)}</div>
    </div>

    <div class="tab-bar">
      <button class="tab-btn active" data-tab="article">Artigo</button>
      <button class="tab-btn" data-tab="history">Histórico</button>
      <button class="tab-btn" data-tab="edit">Editar</button>
    </div>

    <div class="tab-panel active" id="tab-article">
      <div class="article-body">
        <div class="article-lead">${leadParagraph(product, fiscal)}</div>
        ${infoboxHtml(product, fiscal)}
      </div>
    </div>

    <div class="tab-panel" id="tab-history">
      <div class="history-list">${renderHistory(revisions)}</div>
    </div>

    <div class="tab-panel" id="tab-edit">
      <div id="contribute-box"></div>
    </div>
  `;

  root.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  renderContributeBox();

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

function renderContributeBox() {
  const box = document.getElementById("contribute-box");
  if (!isLoggedIn()) {
    box.innerHTML = `<p class="form-hint"><a href="/login">Entre</a> para editar este produto ou adicionar um identificador.</p>`;
    return;
  }

  box.innerHTML = `
    <h2 class="section-title">Editar produto</h2>
    <form id="edit-form" class="form-card wide">
      <div class="form-grid">
        <div class="form-group"><label>Nome</label><input name="name" /></div>
        <div class="form-group"><label>Marca</label><input name="brand" /></div>
        <div class="form-group"><label>Categoria</label><input name="category" /></div>
        <div class="form-group"><label>Fabricante</label><input name="manufacturer" /></div>
        <div class="form-group full"><label>Motivo da alteração *</label><input name="reason" required /></div>
      </div>
      <div class="form-actions"><button type="submit" class="btn">Enviar contribuição</button></div>
      <div class="form-message" id="edit-message" hidden></div>
    </form>

    <h2 class="section-title">Adicionar identificador</h2>
    <form id="identifier-form" class="form-card wide">
      <div class="form-grid">
        <div class="form-group">
          <label>Tipo</label>
          <select name="type">
            <option value="gtin13">GTIN-13</option>
            <option value="gtin8">GTIN-8</option>
            <option value="gtin12">GTIN-12</option>
            <option value="gtin14">GTIN-14</option>
            <option value="upc">UPC</option>
            <option value="ean">EAN</option>
            <option value="manufacturer_code">Código do fabricante</option>
            <option value="other">Outro</option>
          </select>
        </div>
        <div class="form-group"><label>Código</label><input name="value" required /></div>
        <div class="form-group full"><label>Motivo *</label><input name="reason" required value="Identificador adicional" /></div>
      </div>
      <div class="form-actions"><button type="submit" class="btn">Enviar contribuição</button></div>
      <div class="form-message" id="identifier-message" hidden></div>
    </form>
  `;

  document.getElementById("edit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const payload = { reason: data.reason };
    for (const key of ["name", "brand", "category", "manufacturer"]) {
      if (data[key]) payload[key] = data[key];
    }
    await submitContribution(`/products/${encodeURIComponent(productId)}`, "PUT", payload, "edit-message");
  });

  document.getElementById("identifier-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const payload = { product_id: productId, type: data.type, value: data.value, reason: data.reason };
    await submitContribution("/identifiers", "POST", payload, "identifier-message");
  });
}

async function submitContribution(url, method, payload, messageId) {
  const messageEl = document.getElementById(messageId);
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
  el.hidden = false;
  el.className = `form-message ${kind}`;
  el.textContent = text;
}

loadProduct();
