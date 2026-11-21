// Entrar no estilo Git: um nome de usuário e um token. Nada de e-mail ou senha.

const message = document.querySelector("[data-form-message]");
const signedInPanel = document.querySelector("[data-signed-in]");
const signedOutPanels = document.querySelector("[data-signed-out]");
const newTokenPanel = document.querySelector("[data-new-token]");

function showCurrentState() {
  const isSignedIn = savedToken() !== null;
  signedInPanel.hidden = !isSignedIn;
  signedOutPanels.hidden = isSignedIn;
  document.querySelector("[data-current-username]").textContent = savedUsername() || "";
}

document.querySelector("[data-create-contributor]").addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = new FormData(event.target).get("username").trim();

  const result = await callApi("POST", "/contributors", { username });
  if (!result.ok) {
    showMessage(message, errorMessage(result.data), "error");
    return;
  }

  saveSignIn(result.data.username, result.data.token);
  document.querySelector("[data-token-value]").textContent = result.data.token;
  newTokenPanel.hidden = false;
  showMessage(message, "", "info");
  showCurrentState();
  showSignedInUserInMenu();
});

document.querySelector("[data-use-token]").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = new FormData(event.target).get("token").trim();

  localStorage.setItem(TOKEN_KEY, token);
  const result = await callApi("GET", "/contributors/me");
  if (!result.ok) {
    signOut();
    showMessage(message, "Token inválido.", "error");
    return;
  }

  saveSignIn(result.data.username, token);
  showMessage(message, "", "info");
  showCurrentState();
  showSignedInUserInMenu();
});

document.querySelector("[data-sign-out]").addEventListener("click", () => {
  signOut();
  newTokenPanel.hidden = true;
  showCurrentState();
  document.querySelector("[data-account-link]").textContent = "Entrar";
});

document.querySelector("[data-copy-token]").addEventListener("click", async () => {
  await navigator.clipboard.writeText(document.querySelector("[data-token-value]").textContent);
  showMessage(message, "Token copiado.", "success");
});

showCurrentState();
