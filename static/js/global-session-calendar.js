let globalSessionCalendarMonth = null;
let globalSessionCalendarEventsByDate = new Map();

function loadGlobalSessionCalendarEvents() {
  const source = document.querySelector("[data-global-session-calendar-events]");
  try {
    const events = JSON.parse(source?.textContent || "[]");
    return Array.isArray(events) ? events.filter((event) => event?.world_date) : [];
  } catch {
    return [];
  }
}

function globalSessionCalendarDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function globalSessionCalendarLabel(event) {
  const number = Number(event.session_number || 0);
  return number === 0 ? "Нулевая" : `#${number}`;
}

function isGlobalPlannedSession(event) {
  return event?.status === "В планах" || event?.status === "Р’ РїР»Р°РЅР°С…";
}

function initialGlobalSessionCalendarMonth(events) {
  const dates = events
    .map((event) => new Date(`${event.world_date}T00:00:00`))
    .filter((date) => !Number.isNaN(date.valueOf()))
    .sort((a, b) => b - a);
  const base = dates[0] || new Date();
  return new Date(base.getFullYear(), base.getMonth(), 1);
}

function hideGlobalSessionCalendarTooltip() {
  const popover = document.querySelector("[data-global-session-calendar-popover]");
  if (!popover) return;
  popover.hidden = true;
  popover.classList.remove("is-visible");
}

function hideGlobalSessionChoice() {
  const choice = document.querySelector("[data-global-session-choice]");
  if (!choice) return;
  choice.hidden = true;
  choice.classList.remove("is-visible");
}

function showGlobalSessionChoice(dateKey, events) {
  const modal = document.querySelector("[data-global-session-calendar-modal]");
  const choice = modal?.querySelector("[data-global-session-choice]");
  const title = choice?.querySelector("[data-global-session-choice-title]");
  const list = choice?.querySelector("[data-global-session-choice-list]");
  if (!modal || !choice || !title || !list || !events?.length) return;

  const date = new Date(`${dateKey}T00:00:00`);
  title.textContent = Number.isNaN(date.valueOf())
    ? dateKey
    : date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  list.replaceChildren();

  events.forEach((event) => {
    const link = document.createElement("a");
    link.className = "global-session-choice-item";
    link.href = event.url || "#";

    const campaign = document.createElement("strong");
    campaign.textContent = event.campaign_name || "Кампейн";

    const details = document.createElement("span");
    details.textContent = `${globalSessionCalendarLabel(event)} ${event.title || ""}`.trim();

    const status = document.createElement("em");
    status.textContent = isGlobalPlannedSession(event) ? "План" : "Игра";

    link.append(campaign, details, status);
    list.append(link);
  });

  hideGlobalSessionCalendarTooltip();
  choice.hidden = false;
  choice.classList.add("is-visible");
}

function showGlobalSessionCalendarTooltip(cell) {
  const modal = document.querySelector("[data-global-session-calendar-modal]");
  const popover = modal?.querySelector("[data-global-session-calendar-popover]");
  const text = cell?.dataset.calendarTooltip || "";
  if (!modal || !popover || !cell || !text) return;
  popover.textContent = text;
  popover.hidden = false;
  popover.classList.add("is-visible");

  const panelRect = modal.querySelector(".session-calendar-panel")?.getBoundingClientRect();
  const cellRect = cell.getBoundingClientRect();
  const popoverRect = popover.getBoundingClientRect();
  if (!panelRect) return;

  const gap = 10;
  let left = cellRect.left - panelRect.left;
  let top = cellRect.bottom - panelRect.top + gap;
  const maxLeft = panelRect.width - popoverRect.width - gap;
  left = Math.max(gap, Math.min(left, Math.max(gap, maxLeft)));
  if (top + popoverRect.height > panelRect.height - gap) {
    top = cellRect.top - panelRect.top - popoverRect.height - gap;
  }
  popover.style.left = `${left}px`;
  popover.style.top = `${Math.max(gap, top)}px`;
}

function renderGlobalSessionCalendar() {
  const modal = document.querySelector("[data-global-session-calendar-modal]");
  const grid = modal?.querySelector("[data-global-session-calendar-grid]");
  const title = modal?.querySelector("[data-global-session-calendar-month]");
  const empty = modal?.querySelector("[data-global-session-calendar-empty]");
  const popover = modal?.querySelector("[data-global-session-calendar-popover]");
  if (!modal || !grid || !title) return;

  const events = loadGlobalSessionCalendarEvents();
  if (!globalSessionCalendarMonth) globalSessionCalendarMonth = initialGlobalSessionCalendarMonth(events);
  const currentMonth = new Date(globalSessionCalendarMonth.getFullYear(), globalSessionCalendarMonth.getMonth(), 1);
  const eventsByDate = new Map();
  events.forEach((event) => {
    const list = eventsByDate.get(event.world_date) || [];
    list.push(event);
    eventsByDate.set(event.world_date, list);
  });
  globalSessionCalendarEventsByDate = eventsByDate;

  title.textContent = currentMonth.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  if (empty) empty.hidden = events.length > 0;
  if (popover) popover.hidden = true;
  hideGlobalSessionChoice();
  grid.innerHTML = "";

  const firstWeekday = (currentMonth.getDay() + 6) % 7;
  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  for (let index = 0; index < firstWeekday; index += 1) {
    const blank = document.createElement("span");
    blank.className = "session-calendar-day is-empty";
    grid.appendChild(blank);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
    const key = globalSessionCalendarDateKey(date);
    const dayEvents = eventsByDate.get(key) || [];
    const hasPlanned = dayEvents.some(isGlobalPlannedSession);
    const hasCompleted = dayEvents.some((event) => !isGlobalPlannedSession(event));
    const hasMultiple = dayEvents.length > 1;
    const cell = document.createElement(dayEvents.length ? "button" : "span");
    cell.className = [
      "session-calendar-day",
      dayEvents.length ? "has-session" : "",
      hasMultiple ? "has-multiple-sessions" : "",
      hasCompleted ? "has-completed-session" : "",
      hasPlanned ? "has-planned-session" : "",
    ].filter(Boolean).join(" ");

    if (dayEvents.length) {
      const fullLabel = dayEvents
        .map((event) => {
          const state = isGlobalPlannedSession(event) ? "План" : "Игра";
          return `${state} · ${event.campaign_name || ""} · ${globalSessionCalendarLabel(event)} ${event.title || ""}`.trim();
        })
        .join(", ");
      cell.type = "button";
      cell.dataset.globalCalendarDate = key;
      if (!hasMultiple) cell.dataset.globalCalendarHref = dayEvents[0].url || "";
      cell.dataset.calendarTooltip = fullLabel;
      cell.setAttribute("aria-label", `${key}: ${fullLabel}`);
    }

    const number = document.createElement("strong");
    number.textContent = String(day);
    cell.appendChild(number);
    if (dayEvents.length) {
      const label = document.createElement("span");
      label.textContent = dayEvents.length === 1
        ? `${globalSessionCalendarLabel(dayEvents[0])} ${dayEvents[0].campaign_name || ""}`.trim()
        : `${dayEvents.length} сессии`;
      cell.appendChild(label);
      if (hasMultiple) {
        const marker = document.createElement("em");
        marker.className = "session-calendar-count";
        marker.textContent = String(dayEvents.length);
        cell.appendChild(marker);
      }
    }
    grid.appendChild(cell);
  }
}

function openGlobalSessionCalendar() {
  const modal = document.querySelector("[data-global-session-calendar-modal]");
  if (!modal) return;
  globalSessionCalendarMonth = globalSessionCalendarMonth || initialGlobalSessionCalendarMonth(loadGlobalSessionCalendarEvents());
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  renderGlobalSessionCalendar();
}

function closeGlobalSessionCalendar() {
  const modal = document.querySelector("[data-global-session-calendar-modal]");
  if (!modal) return;
  hideGlobalSessionCalendarTooltip();
  hideGlobalSessionChoice();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector(".map-modal.is-open")) document.body.classList.remove("has-modal");
}

window.renderGlobalSessionCalendar = renderGlobalSessionCalendar;

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-open-global-session-calendar]")) {
    openGlobalSessionCalendar();
    return;
  }
  if (event.target.closest("[data-close-global-session-calendar]")) {
    closeGlobalSessionCalendar();
    return;
  }
  if (event.target.closest("[data-close-global-session-choice]")) {
    hideGlobalSessionChoice();
    return;
  }
  const prev = event.target.closest("[data-global-session-calendar-prev]");
  if (prev && globalSessionCalendarMonth) {
    globalSessionCalendarMonth = new Date(globalSessionCalendarMonth.getFullYear(), globalSessionCalendarMonth.getMonth() - 1, 1);
    renderGlobalSessionCalendar();
    return;
  }
  const next = event.target.closest("[data-global-session-calendar-next]");
  if (next && globalSessionCalendarMonth) {
    globalSessionCalendarMonth = new Date(globalSessionCalendarMonth.getFullYear(), globalSessionCalendarMonth.getMonth() + 1, 1);
    renderGlobalSessionCalendar();
    return;
  }
  const sessionDay = event.target.closest("[data-global-calendar-date]");
  if (sessionDay?.dataset.globalCalendarHref) {
    window.location.href = sessionDay.dataset.globalCalendarHref;
    return;
  }
  if (sessionDay?.dataset.globalCalendarDate) {
    const events = globalSessionCalendarEventsByDate.get(sessionDay.dataset.globalCalendarDate) || [];
    showGlobalSessionChoice(sessionDay.dataset.globalCalendarDate, events);
  }
});

document.addEventListener("mouseover", (event) => {
  const cell = event.target.closest("[data-global-session-calendar-modal] [data-calendar-tooltip]");
  if (cell) showGlobalSessionCalendarTooltip(cell);
});

document.addEventListener("focusin", (event) => {
  const cell = event.target.closest("[data-global-session-calendar-modal] [data-calendar-tooltip]");
  if (cell) showGlobalSessionCalendarTooltip(cell);
});

document.addEventListener("mouseout", (event) => {
  if (event.target.closest("[data-global-session-calendar-modal] [data-calendar-tooltip]")) {
    hideGlobalSessionCalendarTooltip();
  }
});

document.addEventListener("focusout", (event) => {
  if (event.target.closest("[data-global-session-calendar-modal] [data-calendar-tooltip]")) {
    hideGlobalSessionCalendarTooltip();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.querySelector("[data-global-session-calendar-modal].is-open")) {
    if (document.querySelector("[data-global-session-choice].is-visible")) {
      hideGlobalSessionChoice();
    } else {
      closeGlobalSessionCalendar();
    }
  }
});
