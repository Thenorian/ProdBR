// Tabela editável para campos que são listas (códigos de barras, marcas...).
// Em vez de um campo de texto livre, cada item é uma linha com os próprios campos,
// um botão "Remover" na linha e um botão "Adicionar" embaixo da tabela.
//
// No HTML:
//   <table data-editable-table="barcodes">
//     <tbody>...linhas já existentes...</tbody>
//   </table>
//   <template data-row-template="barcodes"><tr>...<button data-remove-row>...</tr></template>
//   <button data-add-row="barcodes">Adicionar</button>
//
// Cada campo da linha tem data-column="nome": editableTableRows("barcodes") devolve
// [{nome: valor, ...}, ...], com "" virando null e campos type=number virando número.

function editableTableBody(name) {
  return document.querySelector(`[data-editable-table="${name}"] tbody`);
}

function addEditableTableRow(name) {
  const template = document.querySelector(`[data-row-template="${name}"]`);
  const newRow = template.content.firstElementChild.cloneNode(true);
  editableTableBody(name).appendChild(newRow);
  showEmptyTableMessage(name);
  newRow.querySelector("input, select")?.focus();
}

function showEmptyTableMessage(name) {
  const emptyMessage = document.querySelector(`[data-empty-table="${name}"]`);
  if (emptyMessage) {
    emptyMessage.hidden = editableTableBody(name).rows.length > 0;
  }
}

function editableTableRows(name) {
  return [...editableTableBody(name).rows].map((row) => {
    const values = {};
    for (const field of row.querySelectorAll("[data-column]")) {
      const text = field.value.trim();
      if (text === "") {
        values[field.dataset.column] = null;
      } else if (field.type === "number") {
        values[field.dataset.column] = Number(text);
      } else {
        values[field.dataset.column] = text;
      }
    }
    return values;
  });
}

document.addEventListener("click", (event) => {
  const addButton = event.target.closest("[data-add-row]");
  if (addButton) {
    addEditableTableRow(addButton.dataset.addRow);
    return;
  }

  const removeButton = event.target.closest("[data-remove-row]");
  if (removeButton) {
    const table = removeButton.closest("[data-editable-table]");
    removeButton.closest("tr").remove();
    showEmptyTableMessage(table.dataset.editableTable);
  }
});

document.querySelectorAll("[data-editable-table]").forEach((table) => showEmptyTableMessage(table.dataset.editableTable));
