// Estado de sessao/chave compartilhado entre paginas (localStorage).
const AUTH_KEYS = {
  username: "prodbr_username",
  apiKey: "prodbr_api_key",
  sessionToken: "prodbr_session_token",
};

function getAuth() {
  return {
    username: localStorage.getItem(AUTH_KEYS.username),
    apiKey: localStorage.getItem(AUTH_KEYS.apiKey),
    sessionToken: localStorage.getItem(AUTH_KEYS.sessionToken),
  };
}

function isLoggedIn() {
  const a = getAuth();
  return !!a.username && (!!a.apiKey || !!a.sessionToken);
}

function setAuthFromRegister(username, apiKey) {
  localStorage.setItem(AUTH_KEYS.username, username);
  localStorage.setItem(AUTH_KEYS.apiKey, apiKey);
  localStorage.removeItem(AUTH_KEYS.sessionToken);
}

function setAuthFromLogin(username, sessionToken) {
  localStorage.setItem(AUTH_KEYS.username, username);
  localStorage.setItem(AUTH_KEYS.sessionToken, sessionToken);
  localStorage.removeItem(AUTH_KEYS.apiKey);
}

function clearAuth() {
  Object.values(AUTH_KEYS).forEach((k) => localStorage.removeItem(k));
}

function authHeaders() {
  const a = getAuth();
  if (a.sessionToken) return { Authorization: `Bearer ${a.sessionToken}` };
  if (a.apiKey) return { "X-API-Key": a.apiKey };
  return {};
}

async function authFetch(url, options = {}) {
  const headers = { ...(options.headers || {}), ...authHeaders() };
  return fetch(url, { ...options, headers });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str ?? "");
  return div.innerHTML;
}

function timeAgo(isoString) {
  const then = new Date(isoString + (isoString.endsWith("Z") ? "" : "Z"));
  const diffSec = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000));
  const steps = [
    [60, "s"],
    [60, "min"],
    [24, "h"],
    [30, "d"],
    [12, "m"],
    [Infinity, "a"],
  ];
  let value = diffSec;
  let unit = "s";
  for (const [size, label] of steps) {
    if (value < size) {
      unit = label;
      break;
    }
    value = Math.floor(value / size);
    unit = label;
  }
  if (unit === "s" && value < 5) return "agora mesmo";
  return `há ${value}${unit}`;
}

const AVATAR_COLORS = ["#0a5f38", "#7a4fd6", "#c2410c", "#0369a1", "#a21caf", "#b91c1c", "#15803d"];

function avatarHtml(username) {
  const name = username || "?";
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const color = AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
  const letter = name.charAt(0).toUpperCase();
  return `<span class="avatar" style="background:${color}">${escapeHtml(letter)}</span>`;
}

// Nivel publico de contribuidor (Iniciante/Editor/Renomado/Mestre/Supremo),
// calculado no backend a partir de edicoes aplicadas - ver app/reputation_tiers.py.
function tierBadgeHtml(profile) {
  return `<span class="rep-badge" style="color:${profile.tier_color};background:color-mix(in srgb, ${profile.tier_color} 16%, transparent)" title="${profile.edit_count} edição(ões) aplicada(s)">${escapeHtml(profile.tier_name)}</span>`;
}

// Glossario de termos tecnicos - usado nos icones de ajuda (help-icon)
// espalhados pelos formularios (NCM, CEST, GTIN, aliquotas...).
const GLOSSARY = {
  gtin: "Código numérico que identifica um produto de forma única — o que está no código de barras. GTIN-13 é o mais comum no Brasil; GTIN-8/12/14 variam só no número de dígitos (embalagens menores/maiores, caixas, paletes).",
  ncm: "Nomenclatura Comum do Mercosul — código de 8 dígitos que classifica o produto para fins fiscais. Define quais impostos incidem sobre ele.",
  cest: "Código Especificador da Substituição Tributária — identifica o produto dentro do regime de Substituição Tributária do ICMS. Nem todo produto tem um.",
  uf: "Sigla do estado. Sem UF definida, a regra vale como padrão nacional — usada quando não há regra específica para o estado consultado.",
  origin: "Código da tabela de Origem da Mercadoria do ICMS (0 a 8) — indica se o produto é nacional, importado etc.",
  icms: "Imposto sobre Circulação de Mercadorias e Serviços — principal imposto estadual sobre a venda do produto.",
  ipi: "Imposto sobre Produtos Industrializados — imposto federal cobrado na saída de produtos industrializados.",
  pis: "Contribuição federal sobre o faturamento das empresas.",
  cofins: "Contribuição federal para a seguridade social, também sobre o faturamento.",
  cbs: "Contribuição sobre Bens e Serviços — novo tributo federal da Reforma Tributária (EC 132/2023), substitui PIS/COFINS/IPI.",
  ibs: "Imposto sobre Bens e Serviços — novo tributo da Reforma Tributária, substitui ICMS/ISS.",
  ii: "Imposto de Importação — federal, alíquota-base definida pela Tarifa Externa Comum (TEC) do Mercosul.",
  fcp: "Fundo de Combate à Pobreza — adicional estadual sobre o ICMS, previsto na Constituição.",
  country: "País do Mercosul a que a regra fiscal se refere. O NCM é comum ao bloco, mas cada país tributa com regras próprias.",
};

function helpIcon(key) {
  const text = GLOSSARY[key];
  if (!text) return "";
  return `<span class="help-icon" tabindex="0" data-tip="${escapeHtml(text)}" title="${escapeHtml(text)}">?</span>`;
}

// Categorias sugeridas (datalist) - cobre as verticais prioritarias do
// ProdBR, mas o campo aceita qualquer texto digitado, nao e uma lista
// fechada.
const CATEGORY_SUGGESTIONS = [
  "Pet > Ração Cães",
  "Pet > Ração Gatos",
  "Pet > Petiscos",
  "Pet > Acessórios",
  "Mecânica > Ignição",
  "Mecânica > Freios",
  "Mecânica > Suspensão",
  "Mecânica > Filtros",
  "Mecânica > Lubrificantes",
  "Ferragens > Ferramentas Manuais",
  "Ferragens > Ferramentas Elétricas",
  "Ferragens > Fixação (Parafusos e Porcas)",
  "Agropecuária > Defensivos Agrícolas",
  "Agropecuária > Medicamentos Veterinários",
  "Agropecuária > Irrigação",
  "Pesca > Iscas e Anzóis",
  "Pesca > Carretilhas e Molinetes",
  "Pesca > Linhas",
  "Elétrica > Material Elétrico",
  "Elétrica > Fios e Cabos",
  "Hidráulica > Conexões",
  "Hidráulica > Registros e Válvulas",
];

function injectCategoryDatalist() {
  if (document.getElementById("category-suggestions")) return;
  const datalist = document.createElement("datalist");
  datalist.id = "category-suggestions";
  datalist.innerHTML = CATEGORY_SUGGESTIONS.map((c) => `<option value="${escapeHtml(c)}">`).join("");
  document.body.appendChild(datalist);
}

function actionLabel(action) {
  return { create: "criou", update: "editou", delete: "removeu" }[action] || action;
}

function entityLabel(entityType) {
  return (
    { product: "produto", identifier: "identificador", fiscal_rule: "regra fiscal", ncm_classification: "NCM" }[entityType] ||
    entityType
  );
}

function initNav() {
  const guest = document.getElementById("nav-guest");
  const userBox = document.getElementById("nav-user");
  const usernameEl = document.getElementById("nav-username");
  const logoutBtn = document.getElementById("nav-logout");
  const modLink = document.getElementById("nav-mod");

  if (isLoggedIn()) {
    const { username } = getAuth();
    guest.hidden = true;
    userBox.hidden = false;
    usernameEl.innerHTML = `${avatarHtml(username)} ${escapeHtml(username)}`;

    fetch(`/users/${encodeURIComponent(username)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((profile) => {
        if (!profile) return;
        usernameEl.innerHTML = `${avatarHtml(username)} ${escapeHtml(username)} ${tierBadgeHtml(profile)}`;
        if (profile.role === "moderator" || profile.role === "admin") {
          modLink.hidden = false;
        }
      })
      .catch(() => {});
  } else {
    guest.hidden = false;
    userBox.hidden = true;
  }

  logoutBtn?.addEventListener("click", () => {
    clearAuth();
    window.location.href = "/";
  });

  const searchBox = document.getElementById("global-search");
  if (searchBox) {
    searchBox.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && searchBox.value.trim()) {
        window.location.href = `/?q=${encodeURIComponent(searchBox.value.trim())}`;
      }
    });
  }
}

// Roda imediatamente (nao espera DOMContentLoaded) para garantir que o
// <datalist> ja exista quando os scripts de pagina (que rodam depois,
// na ordem do documento) montarem seus formularios.
injectCategoryDatalist();

document.addEventListener("DOMContentLoaded", initNav);
