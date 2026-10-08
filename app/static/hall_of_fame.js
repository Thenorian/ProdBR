const podiumEl = document.getElementById("podium");
const rowsEl = document.getElementById("hof-rows");
const MEDALS = ["1º", "2º", "3º"];

async function loadHallOfFame() {
  try {
    const res = await fetch("/hall-of-fame?limit=100");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (err) {
    rowsEl.innerHTML = `<tr><td colspan="5" class="error">Erro ao carregar: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function render(people) {
  if (people.length === 0) {
    podiumEl.innerHTML = "";
    rowsEl.innerHTML = `<tr><td colspan="5" class="empty">Ninguém contribuiu ainda — <a href="/new">seja o primeiro</a>.</td></tr>`;
    return;
  }
  podiumEl.innerHTML = people
    .slice(0, 3)
    .map(
      (p, i) => `
      <div class="hof-place hof-place-${i + 1}">
        <div class="hof-medal">${MEDALS[i]}</div>
        <div class="hof-name">${avatarHtml(p.username)} ${escapeHtml(p.username)}</div>
        <div>${tierBadgeHtml(p)}</div>
        <div class="hof-count">${p.edit_count.toLocaleString("pt-BR")} edições</div>
      </div>`
    )
    .join("");
  rowsEl.innerHTML = people
    .map(
      (p) => `
      <tr>
        <td>${p.rank}</td>
        <td>${avatarHtml(p.username)} ${escapeHtml(p.username)}</td>
        <td>${tierBadgeHtml(p)}</td>
        <td>${p.edit_count.toLocaleString("pt-BR")}</td>
        <td>${new Date(p.created_at + "Z").toLocaleDateString("pt-BR")}</td>
      </tr>`
    )
    .join("");
}

loadHallOfFame();
