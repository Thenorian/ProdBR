// Modal de busca para escolher um item de outro cadastro (NCM, categoria, empresa...),
// como na OS do OS-Mechanical: digita, aparecem os resultados, clica e o item é escolhido.
//
//   openPicker({
//     title: "Escolher NCM",
//     placeholder: "Código ou descrição",
//     minimumLength: 2,
//     search: async (text) => [{ title: "2203.00.00", details: "Cervejas de malte", value: {...} }],
//     onChoose: (value) => { ... },
//     createOption: { label: "Cadastrar empresa", url: "/empresa/nova" },          (opcional, abre em outra aba)
//     typedTextOption: { label: (text) => `Usar "${text}"`, onChoose: (text) => {} }  (opcional)
//   });

const PICKER_SEARCH_DELAY_IN_MILLISECONDS = 300;

function openPicker(options) {
  const dialog = document.createElement("dialog");
  dialog.className = "modal modal--picker";
  dialog.innerHTML = `
    <h2 class="modal__title"></h2>
    <input class="field__input picker__search" type="search" autocomplete="off">
    <p class="muted small picker__status" role="status"></p>
    <ul class="picker__results"></ul>
    <div class="picker__extra"></div>
    <button class="button button--quiet modal__close" type="button" data-cancel>Fechar</button>
  `;
  document.body.appendChild(dialog);

  const searchInput = dialog.querySelector(".picker__search");
  const status = dialog.querySelector(".picker__status");
  const resultList = dialog.querySelector(".picker__results");
  const extra = dialog.querySelector(".picker__extra");
  const minimumLength = options.minimumLength || 0;

  dialog.querySelector(".modal__title").textContent = options.title;
  searchInput.placeholder = options.placeholder || "Pesquisar";

  function close() {
    dialog.close();
    dialog.remove();
  }

  function choose(value) {
    options.onChoose(value);
    close();
  }

  function showResults(items) {
    resultList.replaceChildren();
    for (const item of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "picker__item";

      const title = document.createElement("strong");
      title.textContent = item.title;
      button.appendChild(title);

      if (item.details) {
        const details = document.createElement("span");
        details.className = "muted small";
        details.textContent = item.details;
        button.appendChild(details);
      }

      button.addEventListener("click", () => choose(item.value));
      const listItem = document.createElement("li");
      listItem.appendChild(button);
      resultList.appendChild(listItem);
    }
  }

  function showExtraOptions(text) {
    extra.replaceChildren();

    if (options.typedTextOption && text) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button";
      button.textContent = options.typedTextOption.label(text);
      button.addEventListener("click", () => {
        options.typedTextOption.onChoose(text);
        close();
      });
      extra.appendChild(button);
    }

    if (options.createOption) {
      const link = document.createElement("a");
      link.className = "button button--quiet";
      link.href = options.createOption.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = `Não encontrou? ${options.createOption.label} (abre em outra aba)`;
      extra.appendChild(link);
    }
  }

  // Só a última busca digitada vale: uma resposta atrasada não apaga a mais nova.
  let latestSearchNumber = 0;

  async function runSearch() {
    const text = searchInput.value.trim();
    const searchNumber = ++latestSearchNumber;
    showExtraOptions(text);

    if (text.length < minimumLength) {
      resultList.replaceChildren();
      status.textContent = `Digite ao menos ${minimumLength} caracteres.`;
      return;
    }

    status.textContent = "Buscando...";
    let items;
    try {
      items = await options.search(text);
    } catch (error) {
      items = null;
    }
    if (searchNumber !== latestSearchNumber) {
      return;
    }

    if (items === null) {
      status.textContent = "Não foi possível buscar. Tente de novo.";
      return;
    }
    status.textContent = items.length ? "" : "Nada encontrado.";
    showResults(items);
  }

  let searchTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, PICKER_SEARCH_DELAY_IN_MILLISECONDS);
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      clearTimeout(searchTimer);
      runSearch();
    }
  });

  dialog.querySelector("[data-cancel]").addEventListener("click", close);
  dialog.addEventListener("cancel", close);

  searchInput.value = options.initialText || "";
  dialog.showModal();
  searchInput.focus();
  runSearch();
}
