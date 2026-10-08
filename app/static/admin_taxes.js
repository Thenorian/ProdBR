// Admin: paises, subdivisoes e tributos (com traducao). Tudo via
// /admin/countries, /admin/countries/{id}/states e /admin/tax-types.
const adminEl = document.getElementById("taxes-admin");
const LEVELS = { national: "Nacional", state: "Por UF/província" };
const UNITS = { percent: "%", amount: "Valor fixo" };
const LANGS = ["pt", "es", "en"];
let countries = [];
let currentCountry = null;

async function loadAdmin(selectId) {
  if (!isLoggedIn()) {
    adminEl.innerHTML = `<p class="error">Você precisa <a href="/login">entrar</a> com uma conta de administrador.</p>`;
    return;
  }
  const me = await fetch(`/users/${encodeURIComponent(getAuth().username)}`).then((r) => (r.ok ? r.json() : null));
  if (!me || me.role !== "admin") {
    adminEl.innerHTML = `<p class="error">Acesso restrito a administradores.</p>`;
    return;
  }
  countries = await fetch("/countries").then((r) => r.json());
  currentCountry = countries.find((c) => c.id === selectId) || countries.find((c) => c.id === currentCountry?.id) || countries[0] || null;
  await render();
}

async function render() {
  const options = countries
    .map((c) => `<option value="${escapeHtml(c.id)}" ${currentCountry && c.id === currentCountry.id ? "selected" : ""}>${escapeHtml(c.name)} (${escapeHtml(c.id)})</option>`)
    .join("");
  let body = '<p class="empty">Nenhum país cadastrado.</p>';
  if (currentCountry) {
    const id = encodeURIComponent(currentCountry.id);
    const [states, taxes] = await Promise.all([
      fetch(`/countries/${id}/states`).then((r) => r.json()),
      fetch(`/countries/${id}/tax-types?include_inactive=true`).then((r) => r.json()),
    ]);
    body = countryHtml(currentCountry) + taxesHtml(taxes) + statesHtml(states);
  }
  adminEl.innerHTML = `
    <div class="admin-taxes-bar">
      <label>País <select id="country-select">${options}</select></label>
      <button type="button" class="btn btn-sm btn-outline" id="new-country-btn">+ Novo país</button>
    </div>
    <form id="new-country-form" class="admin-taxes-box" hidden>
      <h3>Novo país</h3>
      <div class="form-grid">
        <div class="form-group"><label>Código ISO (2 letras)</label><input name="id" maxlength="2" required placeholder="CL" /></div>
        <div class="form-group"><label>Nome</label><input name="name" required placeholder="Chile" /></div>
        <div class="form-group"><label>Idioma</label><input name="language" value="es" required placeholder="es-CL" /></div>
        <div class="form-group"><label>Nome da subdivisão</label><input name="subdivision_label" value="Provincia" required /></div>
      </div>
      <div class="form-actions"><button type="submit" class="btn btn-sm">Cadastrar país</button></div>
    </form>
    <div class="form-message" id="admin-message" hidden></div>
    ${body}`;
  bind();
}

function countryHtml(c) {
  return `
    <form id="country-form" class="admin-taxes-box">
      <h3>${escapeHtml(c.name)} <span class="form-hint">(${escapeHtml(c.id)})</span></h3>
      <div class="form-grid">
        <div class="form-group"><label>Nome</label><input name="name" value="${escapeHtml(c.name)}" required /></div>
        <div class="form-group"><label>Idioma padrão das respostas</label><input name="language" value="${escapeHtml(c.language || "")}" required /></div>
        <div class="form-group"><label>Nome da subdivisão</label><input name="subdivision_label" value="${escapeHtml(c.subdivision_label || "")}" required /></div>
      </div>
      <div class="form-actions"><button type="submit" class="btn btn-sm btn-outline">Salvar país</button></div>
    </form>`;
}

function taxRowHtml(t) {
  const isNew = !t;
  t = t || { code: "", name: "", translations: {}, level: "national", unit: "percent", active: true, sort_order: 0 };
  const tr = t.translations || {};
  const select = (name, map, value) =>
    `<select name="${name}">${Object.entries(map).map(([k, v]) => `<option value="${k}" ${k === value ? "selected" : ""}>${v}</option>`).join("")}</select>`;
  return `
    <tr data-id="${isNew ? "" : t.id}" class="${t.active ? "" : "tax-inactive"}">
      <td>${isNew ? '<input name="code" maxlength="20" required placeholder="IVA" />' : `<b>${escapeHtml(t.code)}</b>${t.column ? '<br><span class="form-hint">padrão</span>' : ""}`}</td>
      <td><input name="name" value="${escapeHtml(t.name)}" required placeholder="Nome oficial" /></td>
      ${LANGS.map((l) => `<td><input name="tr_${l}" value="${escapeHtml(tr[l] || "")}" placeholder="${l}" /></td>`).join("")}
      <td>${select("level", LEVELS, t.level)}</td>
      <td>${select("unit", UNITS, t.unit)}</td>
      <td><input name="default_rate" type="number" min="0" step="0.01" value="${t.default_rate ?? ""}" /></td>
      <td><input name="default_source" value="${escapeHtml(t.default_source || "")}" placeholder="Lei/ato" /></td>
      <td><input name="sort_order" type="number" step="1" value="${t.sort_order ?? 0}" class="input-narrow" /></td>
      <td><input name="active" type="checkbox" ${t.active ? "checked" : ""} /></td>
      <td><button type="button" class="btn btn-sm ${isNew ? "" : "btn-outline"} save-tax">${isNew ? "Adicionar" : "Salvar"}</button></td>
    </tr>`;
}

function taxesHtml(taxes) {
  return `
    <div class="admin-taxes-box">
      <h3>Tributos</h3>
      <div class="table-scroll">
        <table class="fiscal-table admin-taxes-table">
          <thead><tr>
            <th>Código</th><th>Nome oficial</th><th>Português</th><th>Espanhol</th><th>Inglês</th>
            <th>Esfera</th><th>Unidade</th><th>Alíquota geral</th><th>Fonte da geral</th><th>Ordem</th><th>Ativo</th><th></th>
          </tr></thead>
          <tbody>${taxes.map(taxRowHtml).join("")}${taxRowHtml(null)}</tbody>
        </table>
      </div>
      <p class="form-hint">Tributo não é apagado (regras antigas podem usar): desmarque <b>Ativo</b> para tirar da consulta. A última linha cadastra um tributo novo.</p>
    </div>`;
}

function statesHtml(states) {
  const label = escapeHtml(currentCountry.subdivision_label || "UF");
  return `
    <div class="admin-taxes-box">
      <h3>${label} (${states.length})</h3>
      <ul class="state-chips">
        ${states.map((s) => `<li><b>${escapeHtml(s.code)}</b> ${escapeHtml(s.name)} <button type="button" class="link-btn remove-state" data-code="${escapeHtml(s.code)}" title="Remover">×</button></li>`).join("")}
      </ul>
      <form id="state-form" class="inline-form">
        <input name="code" maxlength="5" required placeholder="Código" class="input-narrow" />
        <input name="name" required placeholder="Nome" />
        <button type="submit" class="btn btn-sm btn-outline">Adicionar</button>
      </form>
    </div>`;
}

function message(kind, text) {
  const el = document.getElementById("admin-message");
  el.hidden = false;
  el.className = `form-message ${kind}`;
  el.textContent = text;
}

async function send(url, method, payload) {
  const res = await authFetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (res.status === 204) return true;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail;
    message("error", detail || `Erro ${res.status}`);
    return false;
  }
  return body;
}

function bind() {
  document.getElementById("country-select")?.addEventListener("change", (e) => {
    currentCountry = countries.find((c) => c.id === e.target.value);
    render();
  });
  const newForm = document.getElementById("new-country-form");
  document.getElementById("new-country-btn").addEventListener("click", () => {
    newForm.hidden = !newForm.hidden;
  });
  newForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(newForm).entries());
    const created = await send("/admin/countries", "POST", data);
    if (created) await loadAdmin(created.id);
  });

  document.getElementById("country-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const saved = await send(`/admin/countries/${encodeURIComponent(currentCountry.id)}`, "PUT", data);
    if (saved) {
      await loadAdmin(saved.id);
      message("success", "País salvo.");
    }
  });

  adminEl.querySelectorAll(".save-tax").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const row = btn.closest("tr");
      const val = (name) => row.querySelector(`[name="${name}"]`);
      const translations = {};
      for (const l of LANGS) if (val(`tr_${l}`).value.trim()) translations[l] = val(`tr_${l}`).value.trim();
      const rate = val("default_rate").value;
      const payload = {
        name: val("name").value.trim(),
        translations: Object.keys(translations).length ? translations : null,
        level: val("level").value,
        unit: val("unit").value,
        default_rate: rate === "" ? null : Number(rate),
        default_source: val("default_source").value.trim() || null,
        sort_order: Number(val("sort_order").value || 0),
        active: val("active").checked,
      };
      const id = row.dataset.id;
      let saved;
      if (id) {
        saved = await send(`/admin/tax-types/${id}`, "PUT", payload);
      } else {
        saved = await send("/admin/tax-types", "POST", { ...payload, country_id: currentCountry.id, code: val("code").value.trim() });
      }
      if (saved) {
        await render();
        message("success", `Tributo ${saved.code} salvo.`);
      }
    })
  );

  document.getElementById("state-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const saved = await send(`/admin/countries/${encodeURIComponent(currentCountry.id)}/states`, "POST", data);
    if (saved) {
      await render();
      message("success", `${saved.name} adicionado.`);
    }
  });

  // Remover pede um segundo clique (sem confirm() nativo).
  adminEl.querySelectorAll(".remove-state").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!btn.classList.contains("confirm")) {
        btn.classList.add("confirm");
        btn.textContent = "remover?";
        return;
      }
      const ok = await send(`/admin/countries/${encodeURIComponent(currentCountry.id)}/states/${encodeURIComponent(btn.dataset.code)}`, "DELETE");
      if (ok) {
        await render();
        message("success", `${btn.dataset.code} removido.`);
      }
    })
  );
}

loadAdmin();
