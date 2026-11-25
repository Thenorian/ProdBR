// Votar na fila: um clique em "A favor" ou "Contra" manda o voto com o token de quem entrou.

const queueMessage = document.querySelector("[data-queue-message]");

document.addEventListener("click", async (event) => {
  const voteButton = event.target.closest("[data-vote]");
  if (!voteButton) {
    return;
  }

  if (!(await askForToken())) {
    return;
  }

  const pendingChangeId = voteButton.dataset.pendingChange;
  const vote = Number(voteButton.dataset.vote);

  voteButton.disabled = true;
  const result = await callApi("POST", `/pending-changes/${encodeURIComponent(pendingChangeId)}/votes`, { vote });
  voteButton.disabled = false;

  if (!result.ok) {
    showMessage(queueMessage, errorMessage(result.data), "error");
    return;
  }

  window.location.reload();
});
