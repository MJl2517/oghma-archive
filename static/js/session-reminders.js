const sessionReminderRoot = document.querySelector("[data-session-reminder]");
const sessionReminderEventsSource = document.querySelector("[data-global-session-calendar-events]");
const sessionReminderStorageKey = "ogma.sessionReminderDismissals";
const sessionReminderDayMs = 24 * 60 * 60 * 1000;

function sessionReminderNumber(value, fallback, min, max) {
  const number = Number.parseInt(value, 10);
  if (Number.isNaN(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

function sessionReminderEvents() {
  try {
    const events = JSON.parse(sessionReminderEventsSource?.textContent || "[]");
    return Array.isArray(events) ? events : [];
  } catch {
    return [];
  }
}

function sessionReminderDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.valueOf()) ? null : date;
}

function sessionReminderToday() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function sessionReminderReadDismissals() {
  try {
    const value = JSON.parse(window.localStorage.getItem(sessionReminderStorageKey) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function sessionReminderWriteDismissals(dismissals) {
  try {
    window.localStorage.setItem(sessionReminderStorageKey, JSON.stringify(dismissals));
  } catch {
    // Ignore unavailable browser storage; the reminder can still be shown.
  }
}

function sessionReminderKey(event) {
  return [
    event.id || "session",
    event.campaign_slug || "",
    event.world_date || "",
    event.session_number || "",
  ].join(":");
}

function sessionReminderCleanupDismissals(dismissals, nowMs) {
  Object.entries(dismissals).forEach(([key, value]) => {
    if (!value || Number(value.until || 0) <= nowMs) delete dismissals[key];
  });
  return dismissals;
}

function sessionReminderIsDismissed(event, dismissals, nowMs) {
  return Number(dismissals[sessionReminderKey(event)]?.until || 0) > nowMs;
}

function sessionReminderPlanned(event) {
  return event?.status === "В планах" || event?.status === "Р’ РїР»Р°РЅР°С…";
}

function sessionReminderSessionLabel(event) {
  const number = Number(event.session_number || 0);
  return number === 0 ? "Нулевая сессия" : `Сессия #${number}`;
}

function sessionReminderDayLabel(daysUntil) {
  if (daysUntil === 0) return "сегодня";
  if (daysUntil === 1) return "завтра";
  if (daysUntil >= 2 && daysUntil <= 4) return `через ${daysUntil} дня`;
  return `через ${daysUntil} дней`;
}

function sessionReminderUpcomingEvents() {
  if (!sessionReminderRoot || sessionReminderRoot.dataset.sessionRemindersEnabled !== "true") return [];
  const warningDays = sessionReminderNumber(sessionReminderRoot.dataset.sessionReminderDays, 3, 0, 30);
  const today = sessionReminderToday();
  return sessionReminderEvents()
    .map((event) => {
      const date = sessionReminderDate(event.world_date);
      if (!date || !sessionReminderPlanned(event)) return null;
      const daysUntil = Math.round((date - today) / sessionReminderDayMs);
      if (daysUntil < 0 || daysUntil > warningDays) return null;
      return { ...event, daysUntil };
    })
    .filter(Boolean)
    .sort((a, b) => a.daysUntil - b.daysUntil || String(a.campaign_name || "").localeCompare(String(b.campaign_name || ""), "ru-RU"));
}

function sessionReminderDismiss(event, untilMs) {
  const dismissals = sessionReminderReadDismissals();
  dismissals[sessionReminderKey(event)] = { until: untilMs };
  sessionReminderWriteDismissals(dismissals);
  sessionReminderRoot.hidden = true;
  sessionReminderRoot.classList.remove("is-visible");
}

function sessionReminderRender() {
  if (!sessionReminderRoot) return;
  const nowMs = Date.now();
  const dismissals = sessionReminderCleanupDismissals(sessionReminderReadDismissals(), nowMs);
  sessionReminderWriteDismissals(dismissals);

  const events = sessionReminderUpcomingEvents().filter((event) => !sessionReminderIsDismissed(event, dismissals, nowMs));
  if (!events.length) {
    sessionReminderRoot.hidden = true;
    sessionReminderRoot.classList.remove("is-visible");
    return;
  }

  const event = events[0];
  const intervalHours = sessionReminderNumber(sessionReminderRoot.dataset.sessionReminderIntervalHours, 12, 1, 168);
  const tomorrow = sessionReminderToday();
  tomorrow.setDate(tomorrow.getDate() + 1);
  sessionReminderRoot.replaceChildren();

  const card = document.createElement("section");
  card.className = "session-reminder-card";

  const copy = document.createElement("div");
  copy.className = "session-reminder-copy";

  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "Скоро игра";

  const title = document.createElement("strong");
  title.textContent = `${sessionReminderDayLabel(event.daysUntil)} · ${event.campaign_name || "Кампейн"}`;

  const details = document.createElement("span");
  details.textContent = `${sessionReminderSessionLabel(event)}${event.title ? ` · ${event.title}` : ""}`;

  copy.append(kicker, title, details);
  if (events.length > 1) {
    const extra = document.createElement("small");
    extra.textContent = `Ещё запланировано: ${events.length - 1}`;
    copy.append(extra);
  }

  const actions = document.createElement("div");
  actions.className = "session-reminder-actions";

  const openLink = document.createElement("a");
  openLink.href = event.url || "#";
  openLink.textContent = "Открыть";

  const dismissButton = document.createElement("button");
  dismissButton.type = "button";
  dismissButton.textContent = "Скрыть";
  dismissButton.addEventListener("click", () => {
    sessionReminderDismiss(event, Date.now() + intervalHours * 60 * 60 * 1000);
  });

  const tomorrowButton = document.createElement("button");
  tomorrowButton.type = "button";
  tomorrowButton.textContent = "До завтра";
  tomorrowButton.addEventListener("click", () => {
    sessionReminderDismiss(event, tomorrow.getTime());
  });

  actions.append(openLink, dismissButton, tomorrowButton);
  card.append(copy, actions);
  sessionReminderRoot.append(card);
  sessionReminderRoot.hidden = false;
  window.requestAnimationFrame(() => sessionReminderRoot.classList.add("is-visible"));
}

sessionReminderRender();
window.addEventListener("storage", (event) => {
  if (event.key === sessionReminderStorageKey) sessionReminderRender();
});
