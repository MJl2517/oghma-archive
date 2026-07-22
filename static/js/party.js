const partyToast = document.querySelector("[data-party-toast]");
const partyUpload = document.querySelector("[data-party-upload]");
const partyFileInput = document.querySelector("[data-party-file-input]");
const partyFileCount = document.querySelector("[data-party-file-count]");
const partyEncounterModal = document.querySelector("[data-party-encounter-modal]");
const partyEncounterContent = document.querySelector("[data-party-encounter-content]");
const partyEncounterDataNode = document.querySelector("[data-party-encounter-data]");
const partyEncounterData = (() => {
  try {
    return JSON.parse(partyEncounterDataNode?.textContent || "{}");
  } catch (_error) {
    return {};
  }
})();

function showPartyToast(message = "Скопировано") {
  if (!partyToast) return;
  partyToast.textContent = message;
  partyToast.classList.add("is-visible");
  window.clearTimeout(showPartyToast.timer);
  showPartyToast.timer = window.setTimeout(() => partyToast.classList.remove("is-visible"), 1600);
}

function escapePartyHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function copyPartyValue(value) {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    showPartyToast();
  } catch (_error) {
    showPartyToast("Не удалось скопировать");
  }
}

function openPartySheet(memberId) {
  const modal = Array.from(document.querySelectorAll("[data-party-sheet]")).find((item) => item.dataset.partySheet === memberId);
  if (!modal) return;
  modal.setAttribute("aria-hidden", "false");
  modal.classList.add("is-open");
  document.body.classList.add("modal-open");
  const url = new URL(window.location.href);
  url.searchParams.set("member", memberId);
  window.history.replaceState({}, "", url.toString());
}

function closePartySheet(modal) {
  if (!modal) return;
  modal.setAttribute("aria-hidden", "true");
  modal.classList.remove("is-open");
  document.body.classList.remove("modal-open");
  const url = new URL(window.location.href);
  url.searchParams.delete("member");
  window.history.replaceState({}, "", url.toString());
}

function setPartyTab(button) {
  const dialog = button.closest("[data-party-sheet]");
  const tab = button.dataset.partyTab;
  if (!dialog || !tab) return;
  dialog.querySelectorAll("[data-party-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
  dialog.querySelectorAll("[data-party-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.partyPanel === tab));
}

async function savePartyState(panel, field, value) {
  const url = panel?.dataset.partyStateUrl;
  const campaignSlug = panel?.dataset.campaignSlug;
  if (!url || !campaignSlug) return false;
  const form = new FormData();
  form.set("campaign_slug", campaignSlug);
  form.set("field", field);
  form.set("value", String(value));
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Requested-With": "fetch" },
    body: form,
  });
  return response.ok;
}

async function savePartyAttendance(input) {
  const url = input?.dataset.partyStateUrl;
  const campaignSlug = input?.dataset.campaignSlug;
  if (!url || !campaignSlug) return false;
  const form = new FormData();
  form.set("campaign_slug", campaignSlug);
  form.set("field", "is_present");
  form.set("value", input.checked ? "1" : "0");
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Requested-With": "fetch" },
    body: form,
  });
  return response.ok;
}

async function stepPartyMetric(button) {
  const metric = button.closest("[data-party-state-field]");
  const panel = button.closest("[data-party-state-url]");
  const valueNode = metric?.querySelector("[data-party-state-value]");
  if (!metric || !panel || !valueNode) return;
  const step = Number.parseInt(button.dataset.partyStep || "0", 10);
  const current = Number.parseInt(valueNode.textContent || "0", 10) || 0;
  const next = Math.max(0, current + step);
  valueNode.textContent = String(next);
  const ok = await savePartyState(panel, metric.dataset.partyStateField, next);
  if (!ok) {
    valueNode.textContent = String(current);
    showPartyToast("Не удалось сохранить");
  }
}

function formatPartyNumber(value) {
  return Number(value || 0).toLocaleString("ru-RU");
}

function renderPartyEncounterRows(rows, renderRow, emptyColspan) {
  if (!rows?.length) {
    return `<tr><td colspan="${emptyColspan}">Нет подходящих вариантов в пределах бюджета.</td></tr>`;
  }
  return rows.map(renderRow).join("");
}

function renderPartyEncounterModal() {
  if (!partyEncounterContent) return;
  if (!partyEncounterData?.ok) {
    partyEncounterContent.innerHTML = `
      <section class="empty-state maps-empty party-encounter-empty">
        <strong>${partyEncounterData?.message || "Не удалось рассчитать бюджет."}</strong>
        <span>Проверьте, что у персонажей группы указан уровень от 1 до 20.</span>
      </section>
    `;
    return;
  }

  const roster = partyEncounterData.members
    .map((member) => `<span>${escapePartyHtml(member.name)} <strong>${escapePartyHtml(member.level)} ур.</strong></span>`)
    .join("");
  const budgets = partyEncounterData.difficulties
    .map((difficulty) => `
      <article class="party-encounter-budget-card">
        <span>${escapePartyHtml(difficulty.label)}</span>
        <strong>${formatPartyNumber(difficulty.budget)} XP</strong>
      </article>
    `)
    .join("");
  const difficultyTabs = partyEncounterData.difficulties
    .map((difficulty, index) => `
      <button type="button" class="${index === 1 ? "is-active" : ""}" data-party-encounter-tab="${escapePartyHtml(difficulty.key)}">
        ${escapePartyHtml(difficulty.label)}
      </button>
    `)
    .join("");
  const difficultyPanels = partyEncounterData.difficulties
    .map((difficulty, index) => {
      const singleRows = renderPartyEncounterRows(difficulty.single, (item) => `
        <tr>
          <td>ПО ${escapePartyHtml(item.cr)}</td>
          <td>${formatPartyNumber(item.xp)}</td>
          <td>${item.count}</td>
          <td>${formatPartyNumber(item.total)}</td>
          <td>${formatPartyNumber(item.left)}</td>
          <td>${item.notes?.length ? escapePartyHtml(item.notes.join("; ")) : "—"}</td>
        </tr>
      `, 6);
      const bossRows = renderPartyEncounterRows(difficulty.boss_minions, (item) => `
        <tr>
          <td>1 x ПО ${escapePartyHtml(item.boss_cr)}</td>
          <td>${item.minion_count} x ПО ${escapePartyHtml(item.minion_cr)}</td>
          <td>${formatPartyNumber(item.total)}</td>
          <td>${formatPartyNumber(item.left)}</td>
        </tr>
      `, 4);
      const pairRows = renderPartyEncounterRows(difficulty.pairs, (item) => `
        <tr>
          <td>1 x ПО ${escapePartyHtml(item.left_cr)}</td>
          <td>1 x ПО ${escapePartyHtml(item.right_cr)}</td>
          <td>${formatPartyNumber(item.total)}</td>
          <td>${formatPartyNumber(item.left)}</td>
        </tr>
      `, 4);
      return `
        <section class="party-encounter-panel ${index === 1 ? "is-active" : ""}" data-party-encounter-panel="${escapePartyHtml(difficulty.key)}">
          <div class="party-encounter-panel-head">
            <h3>${escapePartyHtml(difficulty.label)} сложность</h3>
            <strong>${formatPartyNumber(difficulty.budget)} XP</strong>
          </div>
          <div class="party-encounter-tables">
            <article>
              <h4>Одинаковые существа</h4>
              <div class="party-encounter-table-wrap">
                <table>
                  <thead><tr><th>ПО</th><th>XP</th><th>Кол-во</th><th>Итого</th><th>Остаток</th><th>Риск</th></tr></thead>
                  <tbody>${singleRows}</tbody>
                </table>
              </div>
            </article>
            <article>
              <h4>Лидер + миньоны</h4>
              <div class="party-encounter-table-wrap">
                <table>
                  <thead><tr><th>Лидер</th><th>Миньоны</th><th>Итого</th><th>Остаток</th></tr></thead>
                  <tbody>${bossRows}</tbody>
                </table>
              </div>
            </article>
            <article>
              <h4>Два сильных существа</h4>
              <div class="party-encounter-table-wrap">
                <table>
                  <thead><tr><th>Существо 1</th><th>Существо 2</th><th>Итого</th><th>Остаток</th></tr></thead>
                  <tbody>${pairRows}</tbody>
                </table>
              </div>
            </article>
          </div>
        </section>
      `;
    })
    .join("");
  const warnings = partyEncounterData.warnings
    .map((warning) => `<li>${escapePartyHtml(warning)}</li>`)
    .join("");

  partyEncounterContent.innerHTML = `
    <div class="party-encounter-summary">
      <article><span>Персонажей</span><strong>${partyEncounterData.count}</strong></article>
      <article><span>Средний уровень</span><strong>${partyEncounterData.average_level}</strong></article>
      <article><span>Уровни</span><strong>${escapePartyHtml(partyEncounterData.level_summary)}</strong></article>
    </div>
    <div class="party-encounter-roster">${roster}</div>
    <div class="party-encounter-budgets">${budgets}</div>
    <div class="party-encounter-tabs">${difficultyTabs}</div>
    ${difficultyPanels}
    <section class="party-encounter-warnings">
      <h3>Уточнения и риски</h3>
      <ul>${warnings}</ul>
    </section>
  `;
}

function openPartyEncounterModal() {
  if (!partyEncounterModal) return;
  renderPartyEncounterModal();
  partyEncounterModal.setAttribute("aria-hidden", "false");
  partyEncounterModal.classList.add("is-open");
  document.body.classList.add("modal-open");
}

function closePartyEncounterModal() {
  if (!partyEncounterModal) return;
  partyEncounterModal.setAttribute("aria-hidden", "true");
  partyEncounterModal.classList.remove("is-open");
  document.body.classList.remove("modal-open");
}

function setPartyEncounterTab(button) {
  const key = button.dataset.partyEncounterTab;
  if (!key || !partyEncounterContent) return;
  partyEncounterContent.querySelectorAll("[data-party-encounter-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
  partyEncounterContent.querySelectorAll("[data-party-encounter-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.partyEncounterPanel === key));
}

if (partyFileInput && partyFileCount) {
  partyFileInput.addEventListener("change", () => {
    const count = partyFileInput.files?.length || 0;
    partyFileCount.textContent = count ? `${count} JSON` : "JSON";
  });
}

if (partyUpload) {
  ["dragenter", "dragover"].forEach((eventName) => {
    partyUpload.addEventListener(eventName, (event) => {
      event.preventDefault();
      partyUpload.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    partyUpload.addEventListener(eventName, () => partyUpload.classList.remove("is-dragover"));
  });
  partyUpload.addEventListener("drop", (event) => {
    event.preventDefault();
    if (!partyFileInput || !event.dataTransfer?.files?.length) return;
    partyFileInput.files = event.dataTransfer.files;
    partyFileInput.dispatchEvent(new Event("change"));
  });
}

document.addEventListener("change", (event) => {
  const attendanceInput = event.target.closest("[data-party-attendance]");
  if (!attendanceInput) return;
  const previous = !attendanceInput.checked;
  attendanceInput.disabled = true;
  savePartyAttendance(attendanceInput).then((ok) => {
    if (!ok) {
      attendanceInput.checked = previous;
      attendanceInput.disabled = false;
      showPartyToast("Не удалось сохранить присутствие");
      return;
    }
    window.location.reload();
  }).catch(() => {
    attendanceInput.checked = previous;
    attendanceInput.disabled = false;
    showPartyToast("Не удалось сохранить присутствие");
  });
});

document.addEventListener("click", (event) => {
  const encounterOpenButton = event.target.closest("[data-open-party-encounter]");
  if (encounterOpenButton) {
    event.preventDefault();
    event.stopPropagation();
    openPartyEncounterModal();
    return;
  }

  const encounterCloseButton = event.target.closest("[data-close-party-encounter]");
  if (encounterCloseButton) {
    closePartyEncounterModal();
    return;
  }

  const encounterTabButton = event.target.closest("[data-party-encounter-tab]");
  if (encounterTabButton) {
    setPartyEncounterTab(encounterTabButton);
    return;
  }

  const openButton = event.target.closest("[data-open-party-sheet]");
  if (openButton) {
    openPartySheet(openButton.dataset.openPartySheet);
    return;
  }

  const closeButton = event.target.closest("[data-close-party-sheet]");
  if (closeButton) {
    closePartySheet(closeButton.closest("[data-party-sheet]"));
    return;
  }

  const tabButton = event.target.closest("[data-party-tab]");
  if (tabButton) {
    setPartyTab(tabButton);
    return;
  }

  const copyButton = event.target.closest("[data-party-copy]");
  if (copyButton) {
    copyPartyValue(copyButton.dataset.partyCopy);
    return;
  }

  const diceButton = event.target.closest("[data-party-dice]");
  if (diceButton) {
    const diceInput = document.querySelector("[data-dice-expression]");
    if (diceInput) {
      diceInput.value = diceButton.dataset.partyDice;
      showPartyToast("Формула перенесена в кости");
    } else {
      copyPartyValue(diceButton.dataset.partyDice);
    }
    return;
  }

  const stepButton = event.target.closest("[data-party-step]");
  if (stepButton) {
    stepPartyMetric(stepButton);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const openEncounterModal = document.querySelector('[data-party-encounter-modal][aria-hidden="false"]');
  if (openEncounterModal) {
    closePartyEncounterModal();
    return;
  }
  const openModal = document.querySelector('[data-party-sheet][aria-hidden="false"]');
  if (openModal) closePartySheet(openModal);
});

document.querySelector("[data-party-foundry-job-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submitter = event.submitter;
  const endpoint = submitter?.formAction || form.action;
  form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    showPartyToast("Выполняю локальную операцию Foundry...");
    const result = await window.startLocalJob(endpoint, {
      method: "POST",
      body: new FormData(form),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    });
    if (!result.campaign_slug) throw new Error("campaign_not_found");
    const url = new URL("/party", window.location.origin);
    url.searchParams.set("campaign", result.campaign_slug);
    url.searchParams.set("notice", result.notice || "foundry-folder-error");
    if (result.notice === "foundry-synced") {
      url.searchParams.set("imported", String(result.imported || 0));
      url.searchParams.set("updated", String(result.updated || 0));
      url.searchParams.set("errors", String(result.errors || 0));
    }
    window.location.assign(url);
  } catch {
    form.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    showPartyToast("Не удалось выполнить локальную операцию Foundry.");
  }
});

const initialOpenMember = document.querySelector("[data-open-party-member]")?.dataset.openPartyMember;
if (initialOpenMember) openPartySheet(initialOpenMember);
