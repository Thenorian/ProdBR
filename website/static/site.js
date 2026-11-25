// Guarda o token no navegador e conversa com a API. Usado por todas as páginas.

const TOKEN_KEY = "prodbr_token";
const USERNAME_KEY = "prodbr_username";
const SIGNED_IN_AT_KEY = "prodbr_signed_in_at";
const SIGN_IN_DURATION_IN_DAYS = 30;
const MILLISECONDS_IN_A_DAY = 24 * 60 * 60 * 1000;

// O token vale no navegador por 30 dias a partir do login. Depois disso é pedido de novo.
function savedToken() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    return null;
  }

  const signedInAt = Number(localStorage.getItem(SIGNED_IN_AT_KEY));
  if (!signedInAt) {
    // Login de antes da validade existir: a contagem dos 30 dias começa agora.
    localStorage.setItem(SIGNED_IN_AT_KEY, String(Date.now()));
    return token;
  }

  const daysSinceSignIn = (Date.now() - signedInAt) / MILLISECONDS_IN_A_DAY;
  if (daysSinceSignIn > SIGN_IN_DURATION_IN_DAYS) {
    signOut();
    return null;
  }
  return token;
}

function savedUsername() {
  return savedToken() ? localStorage.getItem(USERNAME_KEY) : null;
}

function saveSignIn(username, token) {
  localStorage.setItem(USERNAME_KEY, username);
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(SIGNED_IN_AT_KEY, String(Date.now()));
}

function signOut() {
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(SIGNED_IN_AT_KEY);
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

// Entrar com um token já existente. Devolve { ok, data } do GET /contributors/me.
async function signInWithToken(token) {
  const response = await fetch(window.PRODBR_API_URL + "/contributors/me", { headers: { "X-API-Key": token } })
    .catch(() => null);
  if (!response) {
    return { ok: false, data: { detail: "Sem conexão com a API." } };
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return { ok: false, data: { detail: "Token inválido." } };
  }

  saveSignIn(data.username, token);
  showSignedInUserInMenu();
  return { ok: true, data };
}

// Criar um acesso novo. O token volta uma única vez em data.token.
async function createContributor(username) {
  const result = await callApi("POST", "/contributors", { username });
  if (result.ok) {
    saveSignIn(result.data.username, result.data.token);
    showSignedInUserInMenu();
  }
  return result;
}

// Modal que pede o token ANTES de começar a editar, para ninguém perder o que digitou.
// Devolve uma Promise que termina quando a pessoa entrou (true) ou desistiu (false).
function askForToken() {
  if (savedToken()) {
    return Promise.resolve(true);
  }

  const dialog = document.createElement("dialog");
  dialog.className = "modal";
  dialog.innerHTML = `
    <h2 class="modal__title">Entre para editar</h2>
    <p class="muted">Seu acesso fica salvo neste navegador por 30 dias.</p>

    <form class="form" data-token-form>
      <label class="field">
        <span class="field__label">Já tenho um token</span>
        <input class="field__input" name="token" autocomplete="off" required>
      </label>
      <button class="button button--primary" type="submit">Entrar</button>
    </form>

    <form class="form modal__section" data-create-form>
      <label class="field">
        <span class="field__label">Novo por aqui? Escolha um nome de usuário</span>
        <input class="field__input" name="username" minlength="3" maxlength="40" pattern="[a-zA-Z0-9_.\\-]+" required>
      </label>
      <button class="button" type="submit">Criar meu token</button>
    </form>

    <div class="modal__section" data-new-token hidden>
      <p><strong>Guarde o seu token.</strong> Ele aparece só agora.</p>
      <pre class="code-block" data-token-value></pre>
      <button class="button button--primary" type="button" data-continue>Já guardei, continuar</button>
    </div>

    <p class="form__message" data-modal-message role="status"></p>
    <button class="button button--quiet modal__close" type="button" data-cancel>Cancelar</button>
  `;
  document.body.appendChild(dialog);

  const message = dialog.querySelector("[data-modal-message]");

  return new Promise((resolve) => {
    function finish(signedIn) {
      dialog.close();
      dialog.remove();
      resolve(signedIn);
    }

    dialog.addEventListener("cancel", () => finish(false));
    dialog.querySelector("[data-cancel]").addEventListener("click", () => finish(false));
    dialog.querySelector("[data-continue]").addEventListener("click", () => finish(true));

    dialog.querySelector("[data-token-form]").addEventListener("submit", async (event) => {
      event.preventDefault();
      const token = new FormData(event.target).get("token").trim();
      const result = await signInWithToken(token);
      if (!result.ok) {
        showMessage(message, errorMessage(result.data), "error");
        return;
      }
      finish(true);
    });

    dialog.querySelector("[data-create-form]").addEventListener("submit", async (event) => {
      event.preventDefault();
      const username = new FormData(event.target).get("username").trim();
      const result = await createContributor(username);
      if (!result.ok) {
        showMessage(message, errorMessage(result.data), "error");
        return;
      }
      dialog.querySelector("[data-token-form]").hidden = true;
      dialog.querySelector("[data-create-form]").hidden = true;
      dialog.querySelector("[data-token-value]").textContent = result.data.token;
      dialog.querySelector("[data-new-token]").hidden = false;
      showMessage(message, "", "info");
    });

    dialog.showModal();
  });
}

// Formulário de edição: fica travado até a pessoa entrar com o token.
// Se ela desistir, volta para a página anterior (nada foi digitado ainda).
async function requireTokenBeforeEditing(form) {
  form.inert = true;
  const signedIn = await askForToken();
  if (!signedIn) {
    history.length > 1 ? history.back() : (window.location.href = "/");
    return false;
  }
  form.inert = false;
  await showVotingNotice(form);
  return true;
}

// Iniciante: avisa antes de editar que a alteração vai para a votação da comunidade.
async function showVotingNotice(form) {
  const result = await callApi("GET", "/contributors/me");
  if (!result.ok || !result.data.changes_need_votes) {
    return;
  }
  const notice = document.createElement("p");
  notice.className = "notice notice--info";
  notice.textContent = "Suas alterações vão para a votação da comunidade antes de entrar na base.";
  form.prepend(notice);
}

showSignedInUserInMenu();
