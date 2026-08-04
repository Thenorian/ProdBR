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

function actionLabel(action) {
  return { create: "criou", update: "editou", delete: "removeu" }[action] || action;
}

function entityLabel(entityType) {
  return { product: "produto", identifier: "identificador", fiscal_rule: "regra fiscal" }[entityType] || entityType;
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
        usernameEl.innerHTML = `${avatarHtml(username)} ${escapeHtml(username)} <span class="rep-badge">rep ${profile.reputation}</span>`;
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

document.addEventListener("DOMContentLoaded", initNav);
