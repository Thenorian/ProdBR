// Formulário de cadastro e edição de produto. Salva direto na API pública com o token.

const form = document.querySelector("[data-product-form]");
const message = document.querySelector("[data-form-message]");
const productId = form.dataset.productId;
const isEditing = productId !== "";

if (!savedToken()) {
  document.querySelector("[data-needs-token]").hidden = false;
}

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
    commercial_unit: textOrNull(fields.get("commercial_unit")),
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
    ? await callApi("PUT", `/products/${encodeURIComponent(productId)}`, productFromForm())
    : await callApi("POST", "/products", productFromForm());

  submitButton.disabled = false;

  if (!result.ok) {
    showMessage(message, errorMessage(result.data), "error");
    return;
  }

  const savedProductId = isEditing ? productId : result.data.id;
  window.location.href = `/produto/${encodeURIComponent(savedProductId)}`;
});
