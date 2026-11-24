// Formulário de cadastro e edição de empresa. Salva direto na API pública com o token.

const form = document.querySelector("[data-company-form]");
const message = document.querySelector("[data-form-message]");
const companyId = form.dataset.companyId;
const isEditing = companyId !== "";

if (!savedToken()) {
  document.querySelector("[data-needs-token]").hidden = false;
}

function textOrNull(value) {
  const text = (value || "").trim();
  return text === "" ? null : text;
}

function brandsFromText(text) {
  return (text || "").split("\n").map((brand) => brand.trim()).filter((brand) => brand !== "");
}

function companyFromForm() {
  const fields = new FormData(form);
  return {
    name: fields.get("name").trim(),
    brands: brandsFromText(fields.get("brands")),
    legal_name: textOrNull(fields.get("legal_name")),
    cnpj: textOrNull(fields.get("cnpj")),
    description: textOrNull(fields.get("description")),
    website: textOrNull(fields.get("website")),
    phone: textOrNull(fields.get("phone")),
    address: textOrNull(fields.get("address")),
    city: textOrNull(fields.get("city")),
    uf: textOrNull(fields.get("uf")),
    source: textOrNull(fields.get("source")),
    reason: fields.get("reason").trim(),
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!savedToken()) {
    showMessage(message, "Entre com o seu token para salvar.", "error");
    return;
  }

  const submitButton = form.querySelector("[type=submit]");
  submitButton.disabled = true;
  showMessage(message, "Salvando...", "info");

  const result = isEditing
    ? await callApi("PUT", `/companies/${encodeURIComponent(companyId)}`, companyFromForm())
    : await callApi("POST", "/companies", companyFromForm());

  submitButton.disabled = false;

  if (!result.ok) {
    showMessage(message, errorMessage(result.data), "error");
    return;
  }

  const wentToVoting = result.status === 202;
  if (wentToVoting) {
    window.location.href = `/fila#${encodeURIComponent(result.data.pending_change.id)}`;
    return;
  }

  const savedCompanyId = isEditing ? companyId : result.data.id;
  window.location.href = `/empresa/${encodeURIComponent(savedCompanyId)}`;
});
