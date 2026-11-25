// Gráfico de preço: com o mouse (ou o dedo) em cima, uma linha vertical e um balão
// mostram o preço mais perto. E o formulário para informar um preço novo.

const BRAZILIAN_MONEY = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function brazilianDate(text) {
  const [year, month, day] = text.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

function setUpPriceChart(figure) {
  const svg = figure.querySelector("svg");
  const crosshair = figure.querySelector("[data-crosshair]");
  const hoverPoint = figure.querySelector("[data-hover-point]");
  const tooltip = figure.querySelector("[data-tooltip]");
  const points = JSON.parse(figure.querySelector("[data-chart-points]").textContent);

  function nearestPoint(chartX) {
    return points.reduce((nearest, point) =>
      Math.abs(point.x - chartX) < Math.abs(nearest.x - chartX) ? point : nearest);
  }

  function showPointAt(event) {
    const box = svg.getBoundingClientRect();
    const chartX = ((event.clientX - box.left) / box.width) * svg.viewBox.baseVal.width;
    const point = nearestPoint(chartX);

    crosshair.setAttribute("x1", point.x);
    crosshair.setAttribute("x2", point.x);
    hoverPoint.setAttribute("cx", point.x);
    hoverPoint.setAttribute("cy", point.y);
    crosshair.hidden = false;
    hoverPoint.hidden = false;

    const place = [point.city, point.uf].filter(Boolean).join(" / ");
    tooltip.replaceChildren();
    const price = document.createElement("strong");
    price.textContent = BRAZILIAN_MONEY.format(point.price) + (point.is_promotion ? " (promoção)" : "");
    const details = document.createElement("span");
    details.textContent = [brazilianDate(point.reported_at), place, point.contributor].filter(Boolean).join(" · ");
    tooltip.append(price, details);
    tooltip.hidden = false;

    const pixelsPerChartUnit = box.width / svg.viewBox.baseVal.width;
    const left = point.x * pixelsPerChartUnit;
    const tooltipFitsOnTheRight = left + tooltip.offsetWidth + 16 < box.width;
    tooltip.style.left = `${tooltipFitsOnTheRight ? left + 12 : left - tooltip.offsetWidth - 12}px`;
    tooltip.style.top = `${point.y * pixelsPerChartUnit - tooltip.offsetHeight - 8}px`;
  }

  function hidePoint() {
    crosshair.hidden = true;
    hoverPoint.hidden = true;
    tooltip.hidden = true;
  }

  svg.addEventListener("pointermove", showPointAt);
  svg.addEventListener("pointerdown", showPointAt);
  svg.addEventListener("pointerleave", hidePoint);
}

document.querySelectorAll("[data-price-chart]").forEach(setUpPriceChart);

// Informar preço: pede o token antes de abrir o formulário, para não perder o que for digitado.
const priceForm = document.querySelector("[data-price-form]");
const priceMessage = document.querySelector("[data-price-message]");

document.querySelector("[data-open-price-form]").addEventListener("click", async (event) => {
  if (!(await askForToken())) {
    return;
  }
  event.target.hidden = true;
  priceForm.hidden = false;
  priceForm.elements.price.focus();
});

priceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!(await askForToken())) {
    return;
  }

  const fields = new FormData(priceForm);
  const price = Number(String(fields.get("price")).replace(/\./g, "").replace(",", "."));
  if (!(price > 0)) {
    showMessage(priceMessage, "Preço inválido. Ex: 12,90", "error");
    return;
  }

  const report = {
    price,
    barcode: fields.get("barcode") || null,
    uf: fields.get("uf") || null,
    city: fields.get("city").trim() || null,
    is_promotion: fields.get("is_promotion") === "on",
  };

  const result = await callApi("POST", `/products/${encodeURIComponent(priceForm.dataset.productId)}/prices`, report);
  if (!result.ok) {
    showMessage(priceMessage, errorMessage(result.data), "error");
    return;
  }

  if (result.data.recorded === "unchanged") {
    showMessage(priceMessage, "Esse já era o seu último preço informado. Nada mudou.", "info");
    return;
  }
  window.location.hash = "preco";
  window.location.reload();
});
