const root = document.getElementById("ncm-root");
const ncmCode = window.NCM_CODE;

let currentNcm = null;
let currentRevisions = [];

async function loadNcm() {
  try {
    const res = await fetch(`/ncm/${encodeURIComponent(ncmCode)}`);
    if (res.status === 404) {
      renderNotFound();
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const ncm = await res.json();

    const revisionsRes = await fetch(`/revisions?entity_type=ncm_classification&entity_id=${encodeURIComponent(ncmCode)}&limit=10`);
    const revisions = revisionsRes.ok ? await revisionsRes.json() : [];

    // Colunas da tabela de regras = tributos de cada pais (cadastrados
    // pelo admin), entao carrega antes de desenhar.
    await Promise.all([...new Set(ncm.fiscal_rules.map((r) => r.country))].map(getTaxTypes));

    currentNcm = ncm;
    currentRevisions = revisions;
    render(ncm, revisions);
  } catch (err) {
    root.innerHTML = `<p class="error">Erro ao carregar: ${err.message}</p>`;
  }
}

function renderNotFound() {
  const canCreate = isLoggedIn();
  root.innerHTML = `
    <div class="page-header">
      <h1>NCM ${escapeHtml(ncmCode)}</h1>
      <p>Essa classificação ainda não foi cadastrada no ProdBR.</p>
    </div>
    ${
      canCreate
        ? `
      <div class="product-form-wrap is-editing" id="create-wrap">
        <div class="product-form">
          <h2>Cadastrar esta classificação</h2>
          <form id="create-form">
            <div class="form-grid">
              <div class="form-group full">
                <label>Descrição oficial (TIPI/Mercosul)*</label>
                <textarea name="description" required></textarea>
              </div>
              <div class="form-group">
                <label>Capítulo (2 dígitos)</label>
                <input name="chapter" maxlength="2" value="${escapeHtml(ncmCode.slice(0, 2))}" />
              </div>
              <div class="form-group">
                <label>Unidade estatística</label>
                <input name="unit" placeholder="UN, KG..." />
              </div>
              <div class="form-group full">
                <label>Fonte*</label>
                <input name="source" required placeholder="Ex: TIPI, Receita Federal" />
              </div>
              <div class="form-group full">
                <label>Motivo da alteração*</label>
                <input name="reason" required placeholder="Por que você está cadastrando isso?" />
              </div>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn">Cadastrar</button>
            </div>
          </form>
          <div class="form-message" id="create-message" hidden></div>
        </div>
      </div>`
        : `<p class="form-hint"><a href="/login">Entre</a> para cadastrar esta classificação.</p>`
    }
  `;

  if (canCreate) {
    document.getElementById("create-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const messageEl = document.getElementById("create-message");
      const data = Object.fromEntries(new FormData(e.target).entries());
      const payload = {
        ncm: ncmCode,
        description: data.description,
        chapter: data.chapter || null,
        unit: data.unit || null,
        source: data.source,
        reason: data.reason,
      };
      try {
        const res = await authFetch("/ncm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await res.json();
        if (res.status === 202) {
          showMessage(messageEl, "success", "Enviado para moderação.");
        } else if (res.ok) {
          showMessage(messageEl, "success", "Cadastrado! Recarregando...");
          setTimeout(loadNcm, 900);
        } else {
          showMessage(messageEl, "error", errorText(body.detail));
        }
      } catch (err) {
        showMessage(messageEl, "error", err.message);
      }
    });
  }
}

function pct(value) {
  return value == null ? "—" : `${String(value).replace(".", ",")}%`;
}

// Resumo dos tributos: o que sai direto do NCM (IPI/II oficiais, da TIPI e
// da TEC, atualizados sozinhos) e o que depende da empresa/UF/operacao -
// por isso nao existe "o ICMS do NCM" nem "o CST do NCM".
function taxSummary(rules) {
  const today = new Date().toISOString().slice(0, 10);
  const official = (rules || []).find(
    (r) => r.source && r.source.startsWith("Oficial:") && !r.uf && (!r.valid_until || r.valid_until >= today)
  );
  const federal = official
    ? `
      <table class="fiscal-table tax-summary">
        <tbody>
          <tr><th>IPI${helpIcon("ipi")}</th><td>${official.ipi_rate == null && official.notes && official.notes.startsWith("IPI: NT") ? "NT (não tributado)" : pct(official.ipi_rate)}</td></tr>
          <tr><th>II${helpIcon("ii")}</th><td>${pct(official.ii_rate)} <span class="form-hint">(só na importação)</span></td></tr>
        </tbody>
      </table>
      ${official.notes ? `<p class="form-hint">${escapeHtml(official.notes)}</p>` : ""}
      <p class="form-hint">Fonte: ${escapeHtml(official.source)} · atualizado automaticamente todo dia.</p>`
    : '<p class="empty">Ainda sem IPI/II oficial carregado para este NCM.</p>';
  return `
    <div class="tax-box">
      <h4>Federais — oficial, direto do NCM</h4>
      ${federal}
      <h4>Dependem da empresa, do estado e da operação</h4>
      <ul class="about-list tax-depends">
        <li><b>ICMS / FCP</b> — alíquota de cada estado (e às vezes redução de base, isenção ou ICMS-ST pelo CEST). Veja/cadastre por UF nas regras abaixo.</li>
        <li><b>CST / CSOSN</b> — não vêm do NCM: dependem do regime da empresa (Simples Nacional usa CSOSN, ex. 102 ou 500 com ST; regime normal usa CST, ex. 00, 20, 60) e da operação.</li>
        <li><b>PIS / COFINS</b> — dependem do regime: cumulativo (0,65% + 3%), não cumulativo (1,65% + 7,6%) ou Simples (dentro do DAS). Alguns NCMs são monofásicos ou alíquota zero — registre nas observações da regra.</li>
        <li><b>CBS / IBS</b> — reforma tributária. Em 2026 é ano de teste (CBS 0,9% + IBS 0,1%, destacados na nota e compensáveis); cobrança efetiva começa em 2027.</li>
      </ul>
    </div>`;
}

function ruleTaxValue(rule, tax) {
  const value = tax.column ? rule[tax.column] : (rule.rates || {})[tax.code];
  return value == null ? null : value;
}

function fiscalRulesTable(rules) {
  if (!rules || rules.length === 0) {
    return '<p class="empty">Nenhuma regra fiscal cadastrada para este NCM ainda.</p>';
  }
  const byCountry = new Map();
  for (const r of rules) {
    if (!byCountry.has(r.country)) byCountry.set(r.country, []);
    byCountry.get(r.country).push(r);
  }
  return [...byCountry.entries()]
    .map(([country, group]) => {
      const types = taxTypesCache.get(country) || [];
      const rows = group
        .map(
          (f) => `
        <tr>
          <td>${f.uf ? escapeHtml(f.uf) : "Nacional"}</td>
          ${types.map((t) => `<td>${ruleTaxValue(f, t) ?? "—"}</td>`).join("")}
          <td>${f.valid_until ? `${f.valid_from} a ${f.valid_until}` : `desde ${f.valid_from}`}</td>
        </tr>
        <tr class="fiscal-source"><td colspan="${types.length + 2}">${f.notes ? `${escapeHtml(f.notes)} · ` : ""}Fonte: ${escapeHtml(f.source)}</td></tr>`
        )
        .join("");
      return `
      <div class="ncm-country-group">
        <h4>${escapeHtml(country)}</h4>
        <div class="table-scroll">
        <table class="fiscal-table">
          <thead><tr>
            <th>Escopo</th>
            ${types.map((t) => `<th><span title="${escapeHtml(t.name)}">${escapeHtml(t.code.replace(/_/g, " "))}</span>${helpIcon(t.code.toLowerCase())}</th>`).join("")}
            <th>Vigência</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
        </div>
      </div>`;
    })
    .join("");
}

function productsList(products, total) {
  if (!products || products.length === 0) {
    return '<p class="empty">Nenhum produto usa esta classificação ainda.</p>';
  }
  const items = products
    .map((p) => `<li><a href="/view/products/${encodeURIComponent(p.id)}">${escapeHtml(p.name)}</a>${p.brand ? ` — ${escapeHtml(p.brand)}` : ""}</li>`)
    .join("");
  const more = total > products.length ? `<p class="form-hint">e mais ${total - products.length} produto(s).</p>` : "";
  return `<ul class="about-list">${items}</ul>${more}`;
}

function render(ncm, revisions) {
  root.innerHTML = `
    <div class="article-header">
      <h1>NCM ${escapeHtml(ncm.ncm)}</h1>
      <div class="article-subtitle">
        ${ncm.chapter ? `<span class="ncm-chapter">capítulo ${escapeHtml(ncm.chapter)}</span> · ` : ""}
        ${ncm.product_count} produto(s) classificado(s) aqui
      </div>
    </div>

    <div class="tab-bar">
      <button class="tab-btn active" data-tab="article">Classificação</button>
      <button class="tab-btn" data-tab="products">Produtos</button>
      <button class="tab-btn" data-tab="history">Histórico</button>
    </div>

    <div class="tab-panel active" id="tab-article">
      <div class="product-form-wrap" id="ncm-form-wrap">
        <div class="product-form">
          <div class="product-form-header">
            <h2>Descrição oficial${helpIcon("ncm")}</h2>
            <button type="button" id="edit-toggle" class="btn btn-outline btn-sm view-only">✎ Editar</button>
          </div>

          <form id="ncm-form">
            <fieldset id="ncm-fieldset" disabled>
              <div class="form-grid">
                <div class="form-group full">
                  <label>Descrição</label>
                  <textarea name="description">${escapeHtml(ncm.description)}</textarea>
                </div>
                <div class="form-group">
                  <label>Capítulo</label>
                  <input name="chapter" value="${escapeHtml(ncm.chapter ?? "")}" maxlength="2" />
                </div>
                <div class="form-group">
                  <label>Unidade estatística</label>
                  <input name="unit" value="${escapeHtml(ncm.unit ?? "")}" />
                </div>
                <div class="form-group full">
                  <label>Fonte</label>
                  <input name="source" value="${escapeHtml(ncm.source)}" />
                </div>
              </div>
            </fieldset>
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

      <h3 class="section-title">Tributos</h3>
      ${taxSummary(ncm.fiscal_rules)}

      <h3 class="section-title">Regras fiscais${helpIcon("uf")}</h3>
      <div id="fiscal-table-wrap">${fiscalRulesTable(ncm.fiscal_rules)}</div>

      <div id="fiscal-manage" hidden>
        <div class="fiscal-manage-actions">
          <button type="button" id="new-fiscal-btn" class="btn btn-sm btn-outline">+ Nova regra fiscal</button>
          ${
            ncm.fiscal_rules.length
              ? `
            <select id="edit-fiscal-select">
              <option value="">Editar regra existente...</option>
              ${ncm.fiscal_rules
                .map((f) => `<option value="${f.id}">${escapeHtml(f.country)} · ${f.uf ? "UF " + escapeHtml(f.uf) : "Nacional"} · desde ${f.valid_from}</option>`)
                .join("")}
            </select>
            <button type="button" id="edit-fiscal-btn" class="btn btn-sm btn-outline">Editar selecionada</button>`
              : ""
          }
        </div>
        <div id="fiscal-form-wrap"></div>
      </div>
      <p class="form-hint" id="fiscal-login-hint"><a href="/login">Entre</a> para cadastrar ou editar regras fiscais deste NCM.</p>
    </div>

    <div class="tab-panel" id="tab-products">
      ${productsList([], 0)}
      <div id="ncm-products-list"><p class="empty">Carregando produtos...</p></div>
    </div>

    <div class="tab-panel" id="tab-history">
      <div class="history-list">${renderHistory(revisions)}</div>
    </div>
  `;
  // remove o placeholder duplicado da lista de produtos
  document.querySelector("#tab-products .about-list")?.remove();
  document.querySelector("#tab-products .empty")?.remove();

  root.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      activateTab(btn.dataset.tab);
      if (btn.dataset.tab === "products") loadProducts();
    });
  });

  wireEditing(ncm);
  wireFiscalManagement(ncm);

  const initialTab = new URLSearchParams(window.location.search).get("tab");
  if (initialTab) {
    activateTab(initialTab);
    if (initialTab === "products") loadProducts();
  }
}

async function loadProducts() {
  const el = document.getElementById("ncm-products-list");
  if (el.dataset.loaded) return;
  try {
    const res = await fetch(`/products?ncm=${encodeURIComponent(ncmCode)}&limit=10`);
    const data = res.ok ? await res.json() : { items: [], total: 0 };
    el.innerHTML = productsList(data.items, data.total);
    el.dataset.loaded = "1";
  } catch (err) {
    el.innerHTML = `<p class="error">Erro ao carregar produtos: ${err.message}</p>`;
  }
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

function wireEditing(ncm) {
  const wrap = document.getElementById("ncm-form-wrap");
  const fieldset = document.getElementById("ncm-fieldset");
  const toggleBtn = document.getElementById("edit-toggle");
  const cancelBtn = document.getElementById("cancel-edit");
  const form = document.getElementById("ncm-form");
  const messageEl = document.getElementById("edit-message");

  if (!isLoggedIn()) {
    toggleBtn.replaceWith(document.createTextNode(""));
    const hint = document.createElement("p");
    hint.className = "form-hint view-only";
    hint.innerHTML = '<a href="/login">Entre</a> para editar esta classificação.';
    wrap.querySelector(".product-form-header").appendChild(hint);
  } else {
    toggleBtn.addEventListener("click", () => setEditing(true));
    cancelBtn.addEventListener("click", () => {
      setEditing(false);
      render(currentNcm, currentRevisions);
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
    const payload = {
      reason,
      description: data.description || null,
      chapter: data.chapter || null,
      unit: data.unit || null,
      source: data.source || null,
    };
    try {
      const res = await authFetch(`/ncm/${encodeURIComponent(ncmCode)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (res.status === 202) {
        showMessage(messageEl, "success", "Reputação insuficiente para aplicar direto — enviado para moderação.");
      } else if (res.ok) {
        showMessage(messageEl, "success", "Contribuição aplicada. Recarregando...");
        setTimeout(loadNcm, 900);
      } else {
        showMessage(messageEl, "error", errorText(body.detail));
      }
    } catch (err) {
      showMessage(messageEl, "error", err.message);
    }
  });
}

// Campos fixos da regra; as aliquotas vem dos tributos do pais escolhido
// (GET /countries/{pais}/tax-types), cadastrados pelo admin.
const FISCAL_FIELDS = [
  ["cest", "CEST", "text", { maxlength: 7 }],
  ["origin", "Origem (0-8)", "number", { min: 0, max: 8, step: 1 }],
  ["valid_from", "Vigente desde", "date", { required: true }],
  ["valid_until", "Vigente até (vazio = sem fim)", "date", {}],
];

const taxTypesCache = new Map();
async function getTaxTypes(countryId) {
  if (!taxTypesCache.has(countryId)) {
    const res = await fetch(`/countries/${encodeURIComponent(countryId)}/tax-types`);
    taxTypesCache.set(countryId, res.ok ? await res.json() : []);
  }
  return taxTypesCache.get(countryId);
}

function taxInputsHtml(types, rule) {
  if (!types.length) {
    return '<p class="form-hint full">Nenhum tributo cadastrado para este país ainda — um administrador cadastra em Ferramentas › Países e tributos.</p>';
  }
  return types
    .map((t) => {
      const value = rule ? ruleTaxValue(rule, t) : null;
      const unit = t.unit === "amount" ? "valor" : "%";
      const hint = t.default_rate != null ? `geral: ${t.default_rate}${t.unit === "amount" ? "" : "%"}` : "";
      return `
      <div class="form-group">
        <label title="${escapeHtml(t.name)}">${escapeHtml(t.code.replace(/_/g, " "))} (${unit})</label>
        <input name="tax:${escapeHtml(t.code)}" type="number" min="0" step="0.01" value="${value ?? ""}" placeholder="${escapeHtml(hint)}" />
      </div>`;
    })
    .join("");
}

let countriesCache = null;
async function getCountries() {
  if (!countriesCache) {
    const res = await fetch("/countries");
    countriesCache = res.ok ? await res.json() : [];
  }
  return countriesCache;
}
async function getStates(countryId) {
  const res = await fetch(`/countries/${encodeURIComponent(countryId)}/states`);
  return res.ok ? await res.json() : [];
}

function stateOptionsHtml(states, selectedCode) {
  const options = [`<option value="">Nacional (padrão)</option>`]
    .concat(states.map((s) => `<option value="${escapeHtml(s.code)}" ${s.code === selectedCode ? "selected" : ""}>${escapeHtml(s.name)} (${escapeHtml(s.code)})</option>`));
  return options.join("");
}

async function fiscalRuleFormHtml(rule) {
  const v = (field, fallback = "") => (rule && rule[field] != null ? rule[field] : fallback);
  const attrs = (extra) =>
    Object.entries(extra)
      .map(([k, val]) => (val === true ? k : `${k}="${val}"`))
      .join(" ");
  const fields = FISCAL_FIELDS.map(([name, label, type, extra]) => `
      <div class="form-group">
        <label>${label}</label>
        <input name="${name}" type="${type}" value="${escapeHtml(String(v(name, "")))}" ${attrs(extra)} />
      </div>`).join("");

  const selectedCountry = v("country", "BR") || "BR";
  const [countries, states, types] = await Promise.all([getCountries(), getStates(selectedCountry), getTaxTypes(selectedCountry)]);
  const label = (countries.find((c) => c.id === selectedCountry) || {}).subdivision_label || "UF";
  const countryOptionsHtml = countries
    .map((c) => `<option value="${escapeHtml(c.id)}" ${c.id === selectedCountry ? "selected" : ""}>${escapeHtml(c.name)} (${escapeHtml(c.id)})</option>`)
    .join("");

  return `
    <form id="fiscal-form" class="fiscal-form">
      <div class="form-grid">
        <div class="form-group">
          <label>País${helpIcon("country")}</label>
          <select name="country" id="fiscal-country-select">${countryOptionsHtml}</select>
        </div>
        <div class="form-group">
          <label id="fiscal-uf-label">${escapeHtml(label)}${helpIcon("uf")}</label>
          <select name="uf" id="fiscal-uf-select">${stateOptionsHtml(states, v("uf", ""))}</select>
        </div>
        ${fields}
        <div class="form-group full"><h4 class="tax-inputs-title">Alíquotas</h4></div>
        <div class="tax-inputs full" id="fiscal-tax-inputs">${taxInputsHtml(types, rule)}</div>
        <div class="form-group full">
          <label>Fonte</label>
          <input name="source" value="${escapeHtml(v("source"))}" required />
        </div>
        <div class="form-group full">
          <label>Observações</label>
          <textarea name="notes">${escapeHtml(v("notes"))}</textarea>
        </div>
        <div class="form-group full">
          <label>Motivo da alteração *</label>
          <input name="reason" required placeholder="Por que você está ${rule ? "mudando" : "cadastrando"} isso?" />
        </div>
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-sm">${rule ? "Salvar regra fiscal" : "Cadastrar regra fiscal"}</button>
        <button type="button" id="cancel-fiscal-form" class="btn btn-outline btn-sm">Cancelar</button>
      </div>
      <div class="form-message" id="fiscal-form-message" hidden></div>
    </form>`;
}

function wireFiscalManagement(ncm) {
  const manage = document.getElementById("fiscal-manage");
  const hint = document.getElementById("fiscal-login-hint");
  if (!isLoggedIn()) {
    manage.hidden = true;
    hint.hidden = false;
    return;
  }
  manage.hidden = false;
  hint.hidden = true;

  const formWrap = document.getElementById("fiscal-form-wrap");
  const newBtn = document.getElementById("new-fiscal-btn");
  const editBtn = document.getElementById("edit-fiscal-btn");
  const editSelect = document.getElementById("edit-fiscal-select");

  newBtn.addEventListener("click", () => showFiscalForm(null));
  editBtn?.addEventListener("click", () => {
    const id = editSelect.value;
    if (!id) return;
    const rule = ncm.fiscal_rules.find((f) => String(f.id) === id);
    showFiscalForm(rule);
  });

  async function showFiscalForm(rule) {
    formWrap.innerHTML = '<p class="empty">Carregando...</p>';
    formWrap.innerHTML = await fiscalRuleFormHtml(rule);
    const form = document.getElementById("fiscal-form");
    const messageEl = document.getElementById("fiscal-form-message");
    document.getElementById("cancel-fiscal-form").addEventListener("click", () => {
      formWrap.innerHTML = "";
    });
    document.getElementById("fiscal-country-select").addEventListener("change", async (e) => {
      const [countries, states, types] = await Promise.all([getCountries(), getStates(e.target.value), getTaxTypes(e.target.value)]);
      const country = countries.find((c) => c.id === e.target.value) || {};
      document.getElementById("fiscal-uf-label").firstChild.textContent = country.subdivision_label || "UF";
      document.getElementById("fiscal-uf-select").innerHTML = stateOptionsHtml(states, null);
      // Trocar de pais numa regra existente: nao reaproveita aliquotas do outro pais.
      document.getElementById("fiscal-tax-inputs").innerHTML = taxInputsHtml(types, rule && rule.country === e.target.value ? rule : null);
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      const payload = {
        reason: data.reason,
        ncm: ncmCode,
        source: data.source,
        notes: data.notes || null,
        country: data.country || "BR",
        uf: data.uf || null,
      };
      for (const [name] of FISCAL_FIELDS) {
        payload[name] = data[name] === "" ? null : data[name];
      }
      // Todas as aliquotas por codigo do tributo; o servidor manda as que
      // tem coluna propria (ICMS, IPI...) pra coluna certa.
      payload.rates = {};
      for (const [name, value] of Object.entries(data)) {
        if (name.startsWith("tax:")) payload.rates[name.slice(4)] = value === "" ? null : Number(value);
      }
      const url = rule ? `/fiscal-rules/${rule.id}` : "/fiscal-rules";
      const method = rule ? "PUT" : "POST";
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
          showMessage(messageEl, "success", "Regra fiscal salva. Recarregando...");
          setTimeout(loadNcm, 900);
        } else {
          showMessage(messageEl, "error", errorText(body.detail));
        }
      } catch (err) {
        showMessage(messageEl, "error", err.message);
      }
    });
  }
}

function showMessage(el, kind, text) {
  if (!kind) return;
  el.hidden = false;
  el.className = `form-message ${kind}`;
  el.textContent = text;
}

loadNcm();

// Erro da API legivel: 422 do FastAPI vem como lista ({loc, msg}); o resto como texto.
function errorText(detail) {
  if (!detail) return "Erro ao enviar.";
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}
