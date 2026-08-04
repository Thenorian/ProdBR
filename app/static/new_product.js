if (!isLoggedIn()) {
  document.getElementById("guest-notice").hidden = false;
} else {
  document.getElementById("product-form").hidden = false;
}

document.getElementById("product-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const messageEl = document.getElementById("message");
  messageEl.hidden = true;

  const data = Object.fromEntries(new FormData(e.target).entries());
  Object.keys(data).forEach((key) => {
    if (data[key] === "") delete data[key];
  });

  try {
    const res = await authFetch("/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await res.json();

    messageEl.hidden = false;
    if (res.status === 202) {
      messageEl.className = "form-message success";
      messageEl.textContent = "Reputação insuficiente para aplicar direto — enviado para a fila de moderação.";
    } else if (res.ok) {
      messageEl.className = "form-message success";
      messageEl.innerHTML = `Produto criado! <a href="/view/products/${encodeURIComponent(body.id)}">Ver produto</a>`;
      e.target.reset();
    } else {
      messageEl.className = "form-message error";
      messageEl.textContent = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join(" ")
        : body.detail || "Erro ao cadastrar.";
    }
  } catch (err) {
    messageEl.hidden = false;
    messageEl.className = "form-message error";
    messageEl.textContent = err.message;
  }
});
