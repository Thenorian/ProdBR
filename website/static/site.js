// Guarda o token no navegador e conversa com a API. Usado por todas as páginas.

const TOKEN_KEY = "prodbr_token";
const USERNAME_KEY = "prodbr_username";

function savedToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function savedUsername() {
  return localStorage.getItem(USERNAME_KEY);
}

function saveSignIn(username, token) {
  localStorage.setItem(USERNAME_KEY, username);
  localStorage.setItem(TOKEN_KEY, token);
}

function signOut() {
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(TOKEN_KEY);
}

// Chama a API e devolve { ok, status, data }. O token vai junto quando existe.
async function callApi(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (savedToken()) {
    headers["X-API-Key"] = savedToken();
  }

  try {
    const response = await fetch(window.PRODBR_API_URL + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { detail: "Sem conexão com a API." } };
  }
}

// A API devolve o erro em "detail": às vezes texto, às vezes lista de campos inválidos.
function errorMessage(data) {
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data.detail)) {
    return data.detail.map((problem) => `${problem.loc.slice(-1)[0]}: ${problem.msg}`).join(" ");
  }
  return "Não foi possível salvar.";
}

function showMessage(element, text, kind) {
  element.textContent = text;
  element.dataset.kind = kind;
}

function showSignedInUserInMenu() {
  const accountLink = document.querySelector("[data-account-link]");
  if (accountLink && savedUsername()) {
    accountLink.textContent = savedUsername();
  }
}

// Botões de copiar (data-copy). Um ouvinte só para a página inteira.
// Primeiro o jeito que não pede permissão (execCommand). O navigator.clipboard
// pode ficar travado esperando permissão em alguns navegadores, então fica de reserva.
async function copyToClipboard(text) {
  const hiddenField = document.createElement("textarea");
  hiddenField.value = text;
  hiddenField.setAttribute("readonly", "");
  hiddenField.className = "copy-helper";
  document.body.appendChild(hiddenField);
  hiddenField.select();

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (error) {
    copied = false;
  }
  hiddenField.remove();

  if (!copied) {
    await navigator.clipboard.writeText(text);
  }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) {
    return;
  }

  try {
    await copyToClipboard(button.dataset.copy);
    button.dataset.copied = "true";
    setTimeout(() => delete button.dataset.copied, 1500);
  } catch (error) {
    button.title = "Não foi possível copiar";
  }
});

showSignedInUserInMenu();
