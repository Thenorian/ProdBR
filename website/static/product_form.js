// Formulário de cadastro e edição de produto. Salva direto na API pública com o token.

const form = document.querySelector("[data-product-form]");
const message = document.querySelector("[data-form-message]");
const productId = form.dataset.productId;
const isEditing = productId !== "";

requireTokenBeforeEditing(form);

// Escolher o NCM na tabela oficial.
document.querySelector("[data-pick-ncm]").addEventListener("click", () => {
  openPicker({
    title: "Pesquisar NCM",
    placeholder: "Código (ex: 2203) ou palavra (ex: cerveja)",
    minimumLength: 2,
    initialText: form.elements.ncm.value,
    search: async (text) => {
      const result = await callApi("GET", `/ncm?q=${encodeURIComponent(text)}&limit=50`);
      if (!result.ok) {
        return null;
      }
      return result.data.items.map((ncm) => ({
        title: ncm.code + (ncm.in_force ? "" : " (fora de vigor)"),
        details: ncm.full_description,
        value: ncm,
      }));
    },
    onChoose: (ncm) => {
      form.elements.ncm.value = ncm.code;
      document.querySelector("[data-ncm-description]").textContent = ncm.full_description;
    },
  });
});

// Escolher uma categoria que já existe, ou usar o texto digitado como categoria nova.
let allCategories = null;

document.querySelector("[data-pick-category]").addEventListener("click", () => {
  openPicker({
    title: "Escolher categoria",
    placeholder: "Parte do nome. Ex: cerveja",
    initialText: form.elements.category.value,
    search: async (text) => {
      if (allCategories === null) {
        const result = await callApi("GET", "/categories");
        if (!result.ok) {
          return null;
        }
        allCategories = result.data.items;
      }
      const lowerText = text.toLowerCase();
      return allCategories
        .filter((category) => category.path.toLowerCase().includes(lowerText))
        .slice(0, 50)
        .map((category) => ({
          title: category.path,
          details: category.ncm_code ? `NCM padrão ${category.ncm_code}` : "",
          value: category.path,
        }));
    },
    onChoose: (path) => {
      form.elements.category.value = path;
    },
    typedTextOption: {
      label: (text) => `Usar "${text}" como categoria nova`,
      onChoose: (text) => {
        form.elements.category.value = text;
      },
    },
  });
});

// Escolher a empresa dona do produto.
const companyName = document.querySelector("[data-company-name]");
const removeCompanyButton = document.querySelector("[data-remove-company]");

function setCompany(company) {
  form.elements.company_id.value = company ? company.id : "";
  companyName.textContent = company ? company.name : "Nenhuma escolhida";
  removeCompanyButton.hidden = !company;
}

document.querySelector("[data-pick-company]").addEventListener("click", () => {
  openPicker({
    title: "Escolher empresa",
    placeholder: "Nome, CNPJ ou marca",
    initialText: form.elements.brand.value || form.elements.manufacturer.value,
    search: async (text) => {
      const result = await callApi("GET", `/companies?q=${encodeURIComponent(text)}&limit=50`);
      if (!result.ok) {
        return null;
      }
      return result.data.items.map((company) => ({
        title: company.name,
        details: [company.legal_name, company.city, company.uf].filter(Boolean).join(" · "),
        value: company,
      }));
    },
    onChoose: setCompany,
    createOption: { label: "Cadastrar empresa", url: "/empresa/nova" },
  });
});

removeCompanyButton.addEventListener("click", () => setCompany(null));

// NCM e CEST são só números: se colar "2203.00.00", vira "22030000".
for (const fieldName of ["ncm", "cest"]) {
  form.elements[fieldName].addEventListener("input", (event) => {
    event.target.value = event.target.value.replace(/[^0-9]/g, "");
  });
}

function textOrNull(value) {
  const text = value.trim();
  return text === "" ? null : text;
}

// Uma linha por código: "7891000100103, 6x350ml". A embalagem depois da vírgula é opcional.
function barcodesFromText(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "")
    .map((line) => {
      const [barcode, ...packageParts] = line.split(",");
      const packageText = packageParts.join(",").trim();
      return packageText === "" ? barcode.trim() : { barcode: barcode.trim(), package: packageText };
    });
}

function productFromForm() {
  const fields = new FormData(form);
  const origin = fields.get("origin");

  return {
    name: fields.get("name").trim(),
    brand: textOrNull(fields.get("brand")),
    manufacturer: textOrNull(fields.get("manufacturer")),
    manufacturer_code: textOrNull(fields.get("manufacturer_code")),
    description: textOrNull(fields.get("description")),
    category: textOrNull(fields.get("category")),
    barcodes: barcodesFromText(fields.get("barcodes")),
    ncm: textOrNull(fields.get("ncm")),
    cest: textOrNull(fields.get("cest")),
    origin: origin === "" ? null : Number(origin),
    company_id: textOrNull(fields.get("company_id")),
    commercial_unit: textOrNull(fields.get("commercial_unit")),
    source: textOrNull(fields.get("source")),
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
    ? await callApi("PUT", `/products/${encodeURIComponent(productId)}`, productFromForm())
    : await callApi("POST", "/products", productFromForm());

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

  const savedProductId = isEditing ? productId : result.data.id;
  window.location.href = `/produto/${encodeURIComponent(savedProductId)}`;
});
