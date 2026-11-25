// Formulário de cadastro e edição de empresa. Salva direto na API pública com o token.
// Marcas e telefones são tabelas editáveis; cada estabelecimento (CNPJ) é editado num modal.

const form = document.querySelector("[data-company-form]");
const message = document.querySelector("[data-form-message]");
const companyId = form.dataset.companyId;
const isEditing = companyId !== "";

requireTokenBeforeEditing(form);

function textOrNull(value) {
  const text = (value || "").trim();
  return text === "" ? null : text;
}

function formattedCnpj(cnpj) {
  const characters = (cnpj || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  if (characters.length !== 14) {
    return cnpj || "—";
  }
  return `${characters.slice(0, 2)}.${characters.slice(2, 5)}.${characters.slice(5, 8)}/${characters.slice(8, 12)}-${characters.slice(12)}`;
}

// ---------- Estabelecimento: modal com os campos e CEP pelo ViaCEP ----------

const establishmentDialog = document.querySelector("[data-establishment-dialog]");
const establishmentForm = document.querySelector("[data-establishment-form]");
const establishmentMessage = document.querySelector("[data-establishment-message]");
const zipCodeStatus = document.querySelector("[data-zip-code-status]");
const ESTABLISHMENT_FIELDS = [
  "cnpj", "legal_name", "state_registration", "is_headquarters", "zip_code", "street",
  "number", "complement", "district", "city", "city_ibge_code", "uf",
];

let rowBeingEdited = null;

function hiddenField(row, field) {
  return row.querySelector(`[data-column="${field}"]`);
}

function openEstablishmentDialog(row) {
  rowBeingEdited = row;
  for (const field of ESTABLISHMENT_FIELDS) {
    const value = hiddenField(row, field).value;
    if (field === "is_headquarters") {
      establishmentForm.elements.is_headquarters.checked = value === "true";
    } else if (field === "cnpj") {
      establishmentForm.elements.cnpj.value = value ? formattedCnpj(value) : "";
    } else {
      establishmentForm.elements[field].value = value;
    }
  }
  showMessage(establishmentMessage, "", "info");
  zipCodeStatus.textContent = "";
  establishmentDialog.showModal();
  establishmentForm.elements.cnpj.focus();
}

function closeEstablishmentDialog() {
  // Linha nova que foi cancelada sem preencher nada sai da tabela.
  if (rowBeingEdited && rowBeingEdited.dataset.isNew === "true") {
    rowBeingEdited.remove();
    showEmptyTableMessage("establishments");
  }
  rowBeingEdited = null;
  establishmentDialog.close();
}

function showEstablishmentSummary(row) {
  const city = [hiddenField(row, "city").value, hiddenField(row, "uf").value].filter(Boolean).join(" / ");
  row.querySelector('[data-show="is_headquarters"]').textContent = hiddenField(row, "is_headquarters").value === "true" ? "Matriz" : "Filial";
  row.querySelector('[data-show="cnpj"]').textContent = hiddenField(row, "cnpj").value ? formattedCnpj(hiddenField(row, "cnpj").value) : "—";
  row.querySelector('[data-show="legal_name"]').textContent = hiddenField(row, "legal_name").value || "—";
  row.querySelector('[data-show="city"]').textContent = city || "—";
}

document.querySelector("[data-new-establishment]").addEventListener("click", () => {
  addEditableTableRow("establishments");
  const rows = document.querySelectorAll("[data-establishment-row]");
  const newRow = rows[rows.length - 1];
  newRow.dataset.isNew = "true";
  if (rows.length === 1) {
    hiddenField(newRow, "is_headquarters").value = "true";
  }
  openEstablishmentDialog(newRow);
});

document.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit-establishment]");
  if (editButton) {
    openEstablishmentDialog(editButton.closest("tr"));
  }
});

document.querySelector("[data-close-establishment]").addEventListener("click", closeEstablishmentDialog);
establishmentDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  closeEstablishmentDialog();
});

establishmentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const fields = new FormData(establishmentForm);
  const hasSomething = ["cnpj", "legal_name", "zip_code", "street", "city"].some((field) => textOrNull(fields.get(field)));
  if (!hasSomething) {
    showMessage(establishmentMessage, "Preencha ao menos o CNPJ, a razão social ou o endereço.", "error");
    return;
  }

  const isHeadquarters = establishmentForm.elements.is_headquarters.checked;
  if (isHeadquarters) {
    // Uma matriz só: marcar esta desmarca as outras.
    for (const otherRow of document.querySelectorAll("[data-establishment-row]")) {
      hiddenField(otherRow, "is_headquarters").value = "";
      showEstablishmentSummary(otherRow);
    }
  }

  for (const field of ESTABLISHMENT_FIELDS) {
    hiddenField(rowBeingEdited, field).value = field === "is_headquarters"
      ? (isHeadquarters ? "true" : "")
      : (fields.get(field) || "").trim();
  }
  showEstablishmentSummary(rowBeingEdited);
  delete rowBeingEdited.dataset.isNew;
  rowBeingEdited = null;
  establishmentDialog.close();
});

// CEP completo (8 dígitos): busca no ViaCEP e preenche logradouro, bairro, cidade, UF e código IBGE.
// Só o CEP sai do navegador; número e complemento continuam por conta de quem preenche.
let latestZipCodeSearch = "";

establishmentForm.elements.zip_code.addEventListener("input", async (event) => {
  const digits = event.target.value.replace(/\D/g, "");
  if (digits.length !== 8 || digits === latestZipCodeSearch) {
    return;
  }
  latestZipCodeSearch = digits;
  zipCodeStatus.textContent = "Buscando o CEP...";

  try {
    const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
    const address = await response.json();
    if (digits !== latestZipCodeSearch) {
      return;
    }
    if (!response.ok || address.erro) {
      zipCodeStatus.textContent = "CEP não encontrado. Preencha o endereço à mão.";
      return;
    }

    establishmentForm.elements.zip_code.value = `${digits.slice(0, 5)}-${digits.slice(5)}`;
    establishmentForm.elements.street.value = address.logradouro || establishmentForm.elements.street.value;
    establishmentForm.elements.district.value = address.bairro || establishmentForm.elements.district.value;
    establishmentForm.elements.city.value = address.localidade || "";
    establishmentForm.elements.uf.value = address.uf || "";
    establishmentForm.elements.city_ibge_code.value = address.ibge || "";
    zipCodeStatus.textContent = "Endereço preenchido pelo CEP.";
    establishmentForm.elements.number.focus();
  } catch (error) {
    zipCodeStatus.textContent = "Não foi possível consultar o CEP. Preencha o endereço à mão.";
  }
});

// ---------- Envio ----------

function establishmentsFromTable() {
  return editableTableRows("establishments").map((row) => ({
    ...row,
    is_headquarters: row.is_headquarters === "true",
  }));
}

function companyFromForm() {
  const fields = new FormData(form);
  return {
    name: fields.get("name").trim(),
    description: textOrNull(fields.get("description")),
    website: textOrNull(fields.get("website")),
    source: textOrNull(fields.get("source")),
    establishments: establishmentsFromTable(),
    phones: editableTableRows("phones"),
    brands: editableTableRows("brands").map((row) => row.brand),
    reason: fields.get("reason").trim(),
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  // O token pode ter vencido com o formulário aberto: pede de novo sem perder o que foi digitado.
  if (!(await askForToken())) {
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

  // A página da empresa fica no CNPJ quando ela tem um; sem CNPJ, no id.
  const savedCompany = isEditing ? result.data.company : result.data;
  window.location.href = `/empresa/${encodeURIComponent(savedCompany.cnpj || savedCompany.id)}`;
});
