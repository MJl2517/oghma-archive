const partyGlobalModal = document.querySelector("[data-party-global-modal]");
const partyGlobalTitle = document.querySelector("[data-party-global-title]");
const partyGlobalSubtitle = document.querySelector("[data-party-global-subtitle]");
const partyGlobalContent = document.querySelector("[data-party-global-content]");
let partyGlobalLoaded = false;
const partyGlobalFloatingTooltip = partyGlobalModal ? document.createElement("div") : null;

if (partyGlobalFloatingTooltip) {
  partyGlobalFloatingTooltip.className = "party-global-floating-tooltip";
  partyGlobalFloatingTooltip.setAttribute("role", "tooltip");
  document.body.appendChild(partyGlobalFloatingTooltip);
}

function escapePartyGlobalHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortPartyGlobalList(items, limit = 3) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!list.length) return "—";
  const visible = list.slice(0, limit).join(", ");
  return list.length > limit ? `${visible} +${list.length - limit}` : visible;
}

function partyGlobalTooltip(label, items) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  return `${label}: ${list.length ? list.join(", ") : "—"}`;
}

function partyGlobalTooltipWrap(text, tooltip, className = "") {
  const safeClass = className ? ` ${className}` : "";
  const full = tooltip || text || "—";
  return `
    <span class="party-global-tooltip-wrap${safeClass}" tabindex="0" data-party-global-tooltip="${escapePartyGlobalHtml(full)}">
      <span class="party-global-cut">${escapePartyGlobalHtml(text || "—")}</span>
    </span>
  `;
}

function renderPartyGlobalEmpty(message) {
  if (!partyGlobalContent) return;
  partyGlobalContent.innerHTML = `<section class="empty-state maps-empty party-global-empty"><strong>${escapePartyGlobalHtml(message)}</strong></section>`;
}

function movePartyGlobalTooltip(clientX, clientY) {
  if (!partyGlobalFloatingTooltip) return;
  const gap = 14;
  const maxLeft = window.innerWidth - partyGlobalFloatingTooltip.offsetWidth - 12;
  const maxTop = window.innerHeight - partyGlobalFloatingTooltip.offsetHeight - 12;
  partyGlobalFloatingTooltip.style.left = `${Math.max(12, Math.min(clientX + gap, maxLeft))}px`;
  partyGlobalFloatingTooltip.style.top = `${Math.max(12, Math.min(clientY + gap, maxTop))}px`;
}

function showPartyGlobalTooltip(target, event) {
  if (!partyGlobalFloatingTooltip || !target) return;
  const text = target.getAttribute("data-party-global-tooltip");
  if (!text) return;
  partyGlobalFloatingTooltip.textContent = text;
  partyGlobalFloatingTooltip.classList.add("is-visible");
  if (event?.clientX && event?.clientY) {
    movePartyGlobalTooltip(event.clientX, event.clientY);
  } else {
    const rect = target.getBoundingClientRect();
    movePartyGlobalTooltip(rect.left, rect.bottom);
  }
}

function hidePartyGlobalTooltip() {
  partyGlobalFloatingTooltip?.classList.remove("is-visible");
}

function renderPartyGlobal(payload) {
  if (!partyGlobalContent || !partyGlobalTitle || !partyGlobalSubtitle) return;
  if (!payload.ok) {
    partyGlobalTitle.textContent = "Сводка группы";
    partyGlobalSubtitle.textContent = "";
    renderPartyGlobalEmpty(payload.message || "Не удалось загрузить группу.");
    return;
  }

  const members = payload.members || [];
  partyGlobalTitle.textContent = payload.campaign?.name ? `Группа: ${payload.campaign.name}` : "Сводка группы";
  partyGlobalSubtitle.textContent = members.length
    ? `Персонажей: ${payload.count || members.length}${payload.average_level ? ` · средний уровень ${payload.average_level}` : ""}`
    : "В избранном мире пока нет персонажей группы.";

  if (!members.length) {
    renderPartyGlobalEmpty("Группа избранного мира пока пуста.");
    return;
  }

  const passiveHeaders = (payload.passive_labels || [])
    .map((skill) => `<th title="${escapePartyGlobalHtml(skill.label)}">${escapePartyGlobalHtml(skill.short)}</th>`)
    .join("");

  const memberRows = members.map((member) => {
    const passiveCells = (member.passives || [])
      .map((skill) => {
        const marker = skill.prof_marker ? `<span class="party-passive-marker" title="${escapePartyGlobalHtml(skill.prof_label || "")}">${escapePartyGlobalHtml(skill.prof_marker)}</span>` : "";
        return `<td class="${skill.is_best ? "is-best" : ""}">${marker}${escapePartyGlobalHtml(skill.value || "—")}</td>`;
      })
      .join("");
    const languagesFull = partyGlobalTooltip("Языки", member.languages);
    const toolsFull = partyGlobalTooltip("Владения", member.tools);
    return `
      <tr>
        <th>${partyGlobalTooltipWrap(member.name, member.name)}</th>
        <td>${escapePartyGlobalHtml(member.ac || "—")}</td>
        <td>${escapePartyGlobalHtml(member.speed || "—")}</td>
        <td class="party-global-prof">${partyGlobalTooltipWrap(shortPartyGlobalList(member.languages, 2), languagesFull)}</td>
        <td class="party-global-prof">${partyGlobalTooltipWrap(shortPartyGlobalList(member.tools, 2), toolsFull)}</td>
        ${passiveCells}
      </tr>
    `;
  }).join("");

  partyGlobalContent.innerHTML = `
    <div class="party-global-aggregate">
      <span class="party-global-aggregate-item" tabindex="0" data-party-global-tooltip="${escapePartyGlobalHtml(partyGlobalTooltip("Все языки", payload.languages))}">
        <strong>Языки</strong><em>${escapePartyGlobalHtml(shortPartyGlobalList(payload.languages, 8))}</em>
      </span>
      <span class="party-global-aggregate-item" tabindex="0" data-party-global-tooltip="${escapePartyGlobalHtml(partyGlobalTooltip("Все владения", payload.tools))}">
        <strong>Владения</strong><em>${escapePartyGlobalHtml(shortPartyGlobalList(payload.tools, 8))}</em>
      </span>
    </div>
    <div class="party-global-table-wrap">
      <table class="party-global-table">
        <thead>
          <tr>
            <th>Имя</th>
            <th>КД</th>
            <th>Ск.</th>
            <th>Языки</th>
            <th>Владения</th>
            ${passiveHeaders}
          </tr>
        </thead>
        <tbody>${memberRows}</tbody>
      </table>
    </div>
  `;
}

async function loadPartyGlobalSummary() {
  if (!partyGlobalContent) return;
  renderPartyGlobalEmpty("Загружаю группу избранного мира...");
  const response = await fetch("/party/favorite-summary", {
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  renderPartyGlobal(payload);
  partyGlobalLoaded = true;
}

function openPartyGlobalSummary() {
  if (!partyGlobalModal) return;
  partyGlobalModal.setAttribute("aria-hidden", "false");
  partyGlobalModal.classList.add("is-open");
  document.body.classList.add("modal-open");
  loadPartyGlobalSummary().catch(() => renderPartyGlobalEmpty("Не удалось загрузить сводку группы."));
}

function closePartyGlobalSummary() {
  if (!partyGlobalModal) return;
  partyGlobalModal.setAttribute("aria-hidden", "true");
  partyGlobalModal.classList.remove("is-open");
  document.body.classList.remove("modal-open");
}

document.addEventListener("keydown", (event) => {
  const isPartySummaryHotkey = event.key.toLowerCase() === "g" || event.key.toLowerCase() === "п" || event.code === "KeyG";
  if (event.altKey && !event.ctrlKey && !event.metaKey && isPartySummaryHotkey) {
    event.preventDefault();
    if (partyGlobalModal?.classList.contains("is-open")) {
      closePartyGlobalSummary();
    } else {
      openPartyGlobalSummary();
    }
    return;
  }
  if (event.key === "Escape" && partyGlobalModal?.classList.contains("is-open")) {
    closePartyGlobalSummary();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-party-global]")) {
    closePartyGlobalSummary();
  }
});

document.addEventListener("mouseover", (event) => {
  const target = event.target.closest("[data-party-global-tooltip]");
  if (target && partyGlobalModal?.contains(target)) {
    showPartyGlobalTooltip(target, event);
  }
});

document.addEventListener("mousemove", (event) => {
  if (partyGlobalFloatingTooltip?.classList.contains("is-visible")) {
    movePartyGlobalTooltip(event.clientX, event.clientY);
  }
});

document.addEventListener("mouseout", (event) => {
  const target = event.target.closest("[data-party-global-tooltip]");
  if (target && !target.contains(event.relatedTarget)) {
    hidePartyGlobalTooltip();
  }
});

document.addEventListener("focusin", (event) => {
  const target = event.target.closest("[data-party-global-tooltip]");
  if (target && partyGlobalModal?.contains(target)) {
    showPartyGlobalTooltip(target);
  }
});

document.addEventListener("focusout", (event) => {
  if (event.target.closest("[data-party-global-tooltip]")) {
    hidePartyGlobalTooltip();
  }
});
