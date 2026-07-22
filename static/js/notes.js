let notesPage = document.querySelector("[data-notes-page]");
const notesToast = document.querySelector("[data-notes-toast]");
let noteTagFilters = document.querySelector("[data-note-tag-filters]");

let includedNoteTags = new Set((noteTagFilters?.dataset.activeTags || "").split("||").filter(Boolean).map(normalizeNoteTag));
let excludedNoteTags = new Set((noteTagFilters?.dataset.excludedTags || "").split("||").filter(Boolean).map(normalizeNoteTag));
let draggedNoteTagItem = null;
let noteTagOrderDirty = false;
let pendingNoteTagRenameForm = null;
let pendingConfirmAction = null;
let notesRefreshController = null;
let noteStatsRefreshController = null;
let noteFilterDebounce = null;
let initialNoteOpened = false;
const noteAutosaveTimers = new WeakMap();
const noteAutosaveControllers = new WeakMap();
const noteAutosaveStatsRefresh = new WeakMap();
let sessionCalendarMonth = null;

function showNotesToast(message) {
  if (!notesToast) return;
  notesToast.textContent = message;
  notesToast.classList.add("is-visible");
  window.setTimeout(() => notesToast.classList.remove("is-visible"), 1700);
}

function normalizeNoteTag(tag) {
  return tag.trim().toLocaleLowerCase("ru-RU");
}

function displayNoteTagsFromSet(tagSet) {
  const tags = [];
  document.querySelectorAll("[data-note-tag-item]").forEach((chip) => {
    if (tagSet.has(normalizeNoteTag(chip.dataset.noteTag))) tags.push(chip.dataset.noteTag);
  });
  return tags;
}

function updateNoteFilterChips() {
  const hasFilters = includedNoteTags.size > 0 || excludedNoteTags.size > 0;
  document.querySelectorAll("[data-note-tag-item]").forEach((chip) => {
    const tag = normalizeNoteTag(chip.dataset.noteTag);
    chip.classList.toggle("is-included", includedNoteTags.has(tag));
    chip.classList.toggle("is-excluded", excludedNoteTags.has(tag));
    chip.classList.toggle("is-muted", hasFilters && !includedNoteTags.has(tag) && !excludedNoteTags.has(tag));
  });
}

function noteFilterUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("tag");
  url.searchParams.delete("exclude_tag");
  displayNoteTagsFromSet(includedNoteTags).forEach((tag) => url.searchParams.append("tag", tag));
  displayNoteTagsFromSet(excludedNoteTags).forEach((tag) => url.searchParams.append("exclude_tag", tag));
  return url.toString();
}

function syncNoteFilterState() {
  notesPage = document.querySelector("[data-notes-page]");
  noteTagFilters = document.querySelector("[data-note-tag-filters]");
  includedNoteTags = new Set((noteTagFilters?.dataset.activeTags || "").split("||").filter(Boolean).map(normalizeNoteTag));
  excludedNoteTags = new Set((noteTagFilters?.dataset.excludedTags || "").split("||").filter(Boolean).map(normalizeNoteTag));
}

function replaceWithFreshElement(documentFragment, selector) {
  const current = document.querySelector(selector);
  const fresh = documentFragment.querySelector(selector);
  if (current && fresh) current.replaceWith(fresh);
}

function clearNoteUrlParam() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("note")) return;
  url.searchParams.delete("note");
  window.history.replaceState({}, "", url.toString());
}

async function refreshSessionStatsPanel() {
  const current = document.querySelector(".session-stats-wrap");
  if (!current) return;
  noteStatsRefreshController?.abort();
  noteStatsRefreshController = new AbortController();
  const response = await fetch(window.location.href, {
    headers: { "X-Requested-With": "fetch" },
    signal: noteStatsRefreshController.signal,
  });
  if (!response.ok) throw new Error("Session stats refresh failed.");
  const html = await response.text();
  const freshDocument = new DOMParser().parseFromString(html, "text/html");
  replaceWithFreshElement(freshDocument, ".session-stats-wrap");
  replaceWithFreshElement(freshDocument, "[data-session-calendar-events]");
  replaceWithFreshElement(freshDocument, "[data-global-session-calendar-events]");
  if (document.querySelector("[data-session-calendar-modal].is-open")) renderSessionCalendar();
  if (document.querySelector("[data-global-session-calendar-modal].is-open")) window.renderGlobalSessionCalendar?.();
}

function shouldRefreshSessionStats(control) {
  return ["status", "world_date", "prep_hours", "play_hours"].includes(control?.name || "");
}

function loadSessionCalendarEvents() {
  const source = document.querySelector("[data-session-calendar-events]");
  try {
    const events = JSON.parse(source?.textContent || "[]");
    return Array.isArray(events) ? events.filter((event) => event?.world_date) : [];
  } catch {
    return [];
  }
}

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function dateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function sessionCalendarLabel(event) {
  const number = Number(event.session_number || 0);
  return number === 0 ? "\u041d\u0443\u043b\u0435\u0432\u0430\u044f" : `#${number}`;
}

function isPlannedSessionEvent(event) {
  return event?.status === "\u0412 \u043f\u043b\u0430\u043d\u0430\u0445";
}

function initialSessionCalendarMonth(events) {
  const dates = events
    .map((event) => new Date(`${event.world_date}T00:00:00`))
    .filter((date) => !Number.isNaN(date.valueOf()))
    .sort((a, b) => b - a);
  const base = dates[0] || new Date();
  return new Date(base.getFullYear(), base.getMonth(), 1);
}

function renderSessionCalendar() {
  const modal = document.querySelector("[data-session-calendar-modal]");
  const grid = modal?.querySelector("[data-session-calendar-grid]");
  const title = modal?.querySelector("[data-session-calendar-month]");
  const empty = modal?.querySelector("[data-session-calendar-empty]");
  const popover = modal?.querySelector("[data-session-calendar-popover]");
  if (!modal || !grid || !title) return;

  const events = loadSessionCalendarEvents();
  if (!sessionCalendarMonth) sessionCalendarMonth = initialSessionCalendarMonth(events);
  const currentMonth = new Date(sessionCalendarMonth.getFullYear(), sessionCalendarMonth.getMonth(), 1);
  const eventsByDate = new Map();
  events.forEach((event) => {
    const list = eventsByDate.get(event.world_date) || [];
    list.push(event);
    eventsByDate.set(event.world_date, list);
  });

  title.textContent = currentMonth.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  if (empty) empty.hidden = events.length > 0;
  if (popover) popover.hidden = true;
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
    const key = dateKey(date);
    const dayEvents = eventsByDate.get(key) || [];
    const hasPlanned = dayEvents.some(isPlannedSessionEvent);
    const hasCompleted = dayEvents.some((event) => !isPlannedSessionEvent(event));
    const cell = document.createElement(dayEvents.length ? "button" : "span");
    cell.className = [
      "session-calendar-day",
      dayEvents.length ? "has-session" : "",
      hasCompleted ? "has-completed-session" : "",
      hasPlanned ? "has-planned-session" : "",
    ].filter(Boolean).join(" ");
    const fullLabel = dayEvents
      .map((event) => `${isPlannedSessionEvent(event) ? "\u041f\u043b\u0430\u043d" : "\u0418\u0433\u0440\u0430"} · ${sessionCalendarLabel(event)} ${event.title || ""}`.trim())
      .join(", ");
    if (dayEvents.length) {
      cell.type = "button";
      cell.dataset.openCalendarSession = dayEvents[0].id;
      cell.dataset.calendarTooltip = fullLabel;
      cell.setAttribute("aria-label", `${key}: ${fullLabel}`);
    }
    const number = document.createElement("strong");
    number.textContent = String(day);
    cell.appendChild(number);
    if (dayEvents.length) {
      const label = document.createElement("span");
      label.textContent = dayEvents.length === 1
        ? `${sessionCalendarLabel(dayEvents[0])} ${dayEvents[0].title || ""}`.trim()
        : `${dayEvents.length} \u0441\u0435\u0441\u0441\u0438\u0438`;
      cell.appendChild(label);
    }
    grid.appendChild(cell);
  }
}

function hideSessionCalendarTooltip() {
  const popover = document.querySelector("[data-session-calendar-popover]");
  if (!popover) return;
  popover.hidden = true;
  popover.classList.remove("is-visible");
}

function showSessionCalendarTooltip(cell) {
  const modal = document.querySelector("[data-session-calendar-modal]");
  const popover = modal?.querySelector("[data-session-calendar-popover]");
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

function openSessionCalendar() {
  const modal = document.querySelector("[data-session-calendar-modal]");
  if (!modal) return;
  sessionCalendarMonth = sessionCalendarMonth || initialSessionCalendarMonth(loadSessionCalendarEvents());
  renderSessionCalendar();
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeSessionCalendar() {
  const modal = document.querySelector("[data-session-calendar-modal]");
  if (!modal) return;
  hideSessionCalendarTooltip();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open, .material-preview-modal.is-open, .note-confirm-modal.is-open, [data-note-tag-order-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function ensureReferenceOptionsLoaded(picker) {
  const list = picker?.querySelector("[data-note-reference-options]");
  if (!list || list.dataset.referenceOptionsLoaded === "true") return;
  const template = document.querySelector("[data-note-reference-options-template]");
  if (!template) return;
  list.replaceChildren(template.content.cloneNode(true));
  list.dataset.referenceOptionsLoaded = "true";
}

function filterReferenceOptions(input) {
  if (!input) return;
  const query = normalizeReferenceQuery(input.value);
  const picker = input.closest("[data-note-reference-picker]");
  ensureReferenceOptionsLoaded(picker);
  let visibleCount = 0;
  picker?.querySelectorAll("[data-add-note-reference]").forEach((button) => {
    const haystack = normalizeReferenceQuery(
      `${button.dataset.referenceGroup} ${button.dataset.referenceLabel} ${button.dataset.referenceId} ${button.dataset.referenceUrl} ${button.dataset.referenceTerms}`
    );
    const url = normalizeReferenceQuery(button.dataset.referenceUrl);
    const id = normalizeReferenceQuery(button.dataset.referenceId);
    const isVisible = query.length >= 2 && (haystack.includes(query) || (url && query.includes(url)) || (id && query.includes(id)));
    button.hidden = !isVisible;
    button.style.display = isVisible ? "" : "none";
    if (isVisible) visibleCount += 1;
  });
  picker?.querySelectorAll("[data-reference-result-group]").forEach((group) => {
    const hasVisibleResult = [...group.querySelectorAll("[data-add-note-reference]")].some((button) => !button.hidden);
    group.hidden = query.length < 2 || !hasVisibleResult;
  });
  const empty = picker?.querySelector("[data-reference-empty]");
  if (empty) {
    empty.hidden = visibleCount > 0;
    empty.textContent = query.length < 2
      ? "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043c\u0438\u043d\u0438\u043c\u0443\u043c 2 \u0441\u0438\u043c\u0432\u043e\u043b\u0430 \u0438\u043b\u0438 \u0432\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443/\u043f\u0443\u0442\u044c."
      : "\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e.";
  }
  hydrateReferencePreviewImages(picker);
}

async function refreshNotesPage(url, { pushState = true } = {}) {
  const activeElement = document.activeElement;
  const focusState = activeElement?.matches?.('.session-filter-row input[name="q"]')
    ? {
        selector: '.session-filter-row input[name="q"]',
        value: activeElement.value,
        selectionStart: activeElement.selectionStart,
        selectionEnd: activeElement.selectionEnd,
      }
    : null;
  notesRefreshController?.abort();
  notesRefreshController = new AbortController();
  const response = await fetch(url, {
    headers: { "X-Requested-With": "fetch" },
    signal: notesRefreshController.signal,
  });
  if (!response.ok) throw new Error("Notes page refresh failed.");

  const html = await response.text();
  const freshDocument = new DOMParser().parseFromString(html, "text/html");
  const latestFocusState = focusState
    ? (() => {
        const liveInput = document.querySelector(focusState.selector);
        return liveInput
          ? {
              ...focusState,
              value: liveInput.value || "",
              selectionStart: liveInput.selectionStart ?? focusState.selectionStart,
              selectionEnd: liveInput.selectionEnd ?? focusState.selectionEnd,
            }
          : focusState;
      })()
    : null;
  replaceWithFreshElement(freshDocument, "[data-notes-page]");
  replaceWithFreshElement(freshDocument, "[data-note-tag-editor]");
  replaceWithFreshElement(freshDocument, "[data-note-tag-rename-modal]");
  replaceWithFreshElement(freshDocument, "[data-note-tag-order-modal]");
  replaceWithFreshElement(freshDocument, ".notes-list-panel");
  replaceWithFreshElement(freshDocument, "[data-note-create-modal]");
  replaceWithFreshElement(freshDocument, "[data-session-calendar-events]");

  document.querySelectorAll(".note-view-modal, .note-edit-modal:not(.note-create-modal)").forEach((modal) => modal.remove());
  freshDocument.querySelectorAll(".note-view-modal, .note-edit-modal:not(.note-create-modal)").forEach((modal) => {
    const createModal = document.querySelector("[data-note-create-modal]");
    if (createModal) createModal.before(modal);
  });

  if (pushState) window.history.pushState({}, "", url);
  initializeNotesPage();
  if (latestFocusState) {
    const nextInput = document.querySelector(latestFocusState.selector);
    if (nextInput) {
      nextInput.value = latestFocusState.value;
      nextInput.focus({ preventScroll: true });
      if (Number.isInteger(latestFocusState.selectionStart) && Number.isInteger(latestFocusState.selectionEnd)) {
        nextInput.setSelectionRange(latestFocusState.selectionStart, latestFocusState.selectionEnd);
      }
    }
  }
}

async function submitNotesFormAjax(form) {
  if (!form) throw new Error("Missing notes form.");
  const response = await fetch(form.action, {
    method: form.method || "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "fetch" },
  });
  if (!response.ok) throw new Error("Notes form request failed.");
  await refreshNotesPage(window.location.href, { pushState: false });
}

function setNoteAutosaveState(form, state) {
  const label = form?.querySelector("[data-note-autosave-state]");
  if (!label) return;
  label.dataset.state = state;
  if (state === "saving") label.textContent = "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u044e...";
  else if (state === "saved") label.textContent = "\u0410\u0432\u0442\u043e\u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e";
  else if (state === "error") label.textContent = "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0430\u0432\u0442\u043e\u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c";
  else label.textContent = "";
}

async function autosaveNoteForm(form, { refreshStats = false } = {}) {
  if (!form?.matches("[data-note-autosave]")) return;
  refreshStats = refreshStats || noteAutosaveStatsRefresh.get(form) === true;
  noteAutosaveStatsRefresh.delete(form);
  noteAutosaveControllers.get(form)?.abort();
  const controller = new AbortController();
  noteAutosaveControllers.set(form, controller);
  setNoteAutosaveState(form, "saving");
  try {
    const response = await fetch(form.action, {
      method: form.method || "POST",
      body: new FormData(form),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Autosave failed.");
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Autosave failed.");
    setNoteAutosaveState(form, "saved");
    if (refreshStats) await refreshSessionStatsPanel().catch(() => {});
  } catch (error) {
    if (error.name === "AbortError") return;
    setNoteAutosaveState(form, "error");
  }
}

function scheduleNoteAutosave(form, { refreshStats = false } = {}) {
  if (!form?.matches("[data-note-autosave]")) return;
  window.clearTimeout(noteAutosaveTimers.get(form));
  if (refreshStats) noteAutosaveStatsRefresh.set(form, true);
  setNoteAutosaveState(form, "saving");
  noteAutosaveTimers.set(form, window.setTimeout(() => autosaveNoteForm(form), 900));
}

function notesFilterUrlFromForm(form) {
  const url = new URL(form.action, window.location.origin);
  const formData = new FormData(form);
  formData.forEach((value, key) => {
    if (String(value).trim()) url.searchParams.append(key, value);
  });
  return url.toString();
}

function submitNotesFilterAjax(form) {
  const url = notesFilterUrlFromForm(form);
  return refreshNotesPage(url).catch(() => form.submit());
}

function normalizeReferenceQuery(value) {
  const raw = String(value || "").trim().toLocaleLowerCase("ru-RU").replaceAll("\\", "/");
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    return `${parsed.pathname}${parsed.search}${parsed.hash}`.toLocaleLowerCase("ru-RU");
  } catch {
    return raw;
  }
}

function tagsFromInput(input) {
  return input.value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setInputTags(input, tags) {
  const seen = new Set();
  const normalized = [];
  tags.forEach((tag) => {
    const clean = tag.trim();
    const key = normalizeNoteTag(clean);
    if (clean && !seen.has(key)) {
      seen.add(key);
      normalized.push(clean);
    }
  });
  input.value = normalized.join(", ");
  syncNoteTagButtons(input.closest("[data-note-form]"));
}

function syncNoteTagButtons(form) {
  if (!form) return;
  const input = form.querySelector('input[name="tags"]');
  if (!input) return;
  const activeTags = new Set(tagsFromInput(input).map(normalizeNoteTag));
  form.querySelectorAll("[data-insert-note-tag]").forEach((button) => {
    button.classList.toggle("is-active", activeTags.has(normalizeNoteTag(button.dataset.insertNoteTag)));
  });
}

function toggleNoteTag(input, tag) {
  const current = tagsFromInput(input);
  const key = normalizeNoteTag(tag);
  const hasTag = current.some((item) => normalizeNoteTag(item) === key);
  setInputTags(input, hasTag ? current.filter((item) => normalizeNoteTag(item) !== key) : [...current, tag]);
}

function referenceTypeLabel(type) {
  if (type === "character") return "NPC";
  if (type === "map") return "\u041a\u0430\u0440\u0442\u044b";
  if (type === "scene") return "\u0421\u0446\u0435\u043d\u044b";
  if (type === "god") return "\u0411\u043e\u0433\u0438";
  if (type === "generator") return "\u0413\u0435\u043d\u0435\u0440\u0430\u0442\u043e\u0440\u044b";
  return type || "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function hydrateReferencePreviewImages(scope = document) {
  if (!scope) return;
  scope.querySelectorAll("[data-reference-preview-src]").forEach((image) => {
    const button = image.closest("[data-add-note-reference]");
    if (button?.hidden || button?.style.display === "none") return;
    if (!image.src) {
      image.src = image.dataset.referencePreviewSrc;
    }
  });
}

async function copyTextToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const fallback = document.createElement("textarea");
    fallback.value = text;
    document.body.appendChild(fallback);
    fallback.select();
    document.execCommand("copy");
    fallback.remove();
  }
}

async function blobToPng(blob) {
  if (blob.type === "image/png") return blob;
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d");
  context.drawImage(bitmap, 0, 0);
  bitmap.close?.();
  return new Promise((resolve, reject) => {
    canvas.toBlob((pngBlob) => {
      if (pngBlob) resolve(pngBlob);
      else reject(new Error("Could not prepare PNG."));
    }, "image/png");
  });
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function copyImageWithSelectionFallback(blob) {
  const dataUrl = await blobToDataUrl(await blobToPng(blob));
  const holder = document.createElement("div");
  const image = document.createElement("img");
  holder.contentEditable = "true";
  holder.style.position = "fixed";
  holder.style.left = "-10000px";
  holder.style.top = "0";
  holder.style.width = "1px";
  holder.style.height = "1px";
  holder.style.overflow = "hidden";
  image.src = dataUrl;
  holder.appendChild(image);
  document.body.appendChild(holder);
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
  });
  const selection = window.getSelection();
  const range = document.createRange();
  selection.removeAllRanges();
  range.selectNode(image);
  selection.addRange(range);
  holder.focus();
  const copied = document.execCommand("copy");
  selection.removeAllRanges();
  holder.remove();
  if (!copied) throw new Error("Legacy image copy failed.");
}

async function copyPngBlobViaServer(pngBlob) {
  const formData = new FormData();
  formData.append("image", pngBlob, "clipboard.png");
  await window.startLocalJob("/clipboard/copy-image", { method: "POST", body: formData });
}

async function copyImageToClipboard(imageUrl) {
  if (!imageUrl) throw new Error("Missing image URL.");
  const response = await fetch(imageUrl);
  if (!response.ok) throw new Error("Image fetch failed.");
  const sourceBlob = await response.blob();
  const pngBlob = await blobToPng(sourceBlob);

  if (navigator.clipboard?.write && typeof ClipboardItem !== "undefined" && window.isSecureContext) {
    try {
      await navigator.clipboard.write([new ClipboardItem({ [pngBlob.type]: pngBlob })]);
      return;
    } catch {
      // Fall back to server-assisted PNG copy below.
    }
  }

  try {
    await copyPngBlobViaServer(pngBlob);
    return;
  } catch {
    // Fall back to selection copy below.
  }

  await copyImageWithSelectionFallback(pngBlob);
}

async function copyImageViaServer(copyImageUrl) {
  if (!copyImageUrl) throw new Error("Missing image copy endpoint.");
  const formData = new FormData();
  formData.append("scope", "shared");
  formData.append("campaign_slug", notesPage?.dataset.campaignSlug || "");
  await window.startLocalJob(copyImageUrl, {
    method: "POST",
    body: formData,
  });
}

function shouldCopyImageInBrowser(imageUrl) {
  const cleanUrl = String(imageUrl || "").split("?", 1)[0].toLocaleLowerCase("ru-RU");
  return cleanUrl.endsWith(".webp") || cleanUrl.endsWith(".avif");
}

async function copyMaterialImage(copyImageUrl, browserImageUrl) {
  if (shouldCopyImageInBrowser(browserImageUrl)) {
    await copyImageToClipboard(browserImageUrl);
    return;
  }
  try {
    await copyImageViaServer(copyImageUrl);
  } catch (serverError) {
    await copyImageToClipboard(serverError.clipboardImageUrl || browserImageUrl);
  }
}

function renderMarkdown(value) {
  const renderInline = (input) => escapeHtml(input)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\[\[([^\]]+)\]\]/g, '<span class="note-wiki-link">$1</span>')
    .replace(/\[([^\]\n|]+?)\s*\|\s*([^\]\n]+?)\]/g, (_match, label, target) => {
      const href = String(target || "").trim();
      if (/^https?:\/\//i.test(href)) {
        return `<a class="rule-inline-link" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${label.trim()}</a>`;
      }
      return `<span class="rule-inline-link" title="${escapeHtml(href)}">${label.trim()}</span>`;
    })
    .replace(/\[([^\]\n]+?)\]\(([^)\n]+?)\)/g, (_match, label, href) => {
      const safeHref = String(href || "").trim();
      const isExternal = /^https?:\/\//i.test(safeHref);
      const isInternal = safeHref.startsWith("/") && !safeHref.startsWith("//") && !safeHref.includes("\\");
      if (!isExternal && !isInternal) return _match;
      const target = isExternal ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<a class="rule-inline-link" href="${escapeHtml(safeHref)}"${target}>${label.trim()}</a>`;
    })
    .replace(/\{([^{}|\n]+)\|([^{}\n]+)\}/g, (_match, color, text) => {
      const colors = {
        red: "red", "РєСЂР°СЃРЅС‹Р№": "red", "РєСЂР°СЃРЅР°СЏ": "red",
        green: "green", "Р·РµР»С‘РЅС‹Р№": "green", "Р·РµР»РµРЅС‹Р№": "green", "Р·РµР»С‘РЅР°СЏ": "green", "Р·РµР»РµРЅР°СЏ": "green",
        blue: "blue", "СЃРёРЅРёР№": "blue", "СЃРёРЅСЏСЏ": "blue",
        gold: "gold", "Р·РѕР»РѕС‚Рѕ": "gold", "Р¶С‘Р»С‚С‹Р№": "gold", "Р¶РµР»С‚С‹Р№": "gold",
        aqua: "aqua", "Р±РёСЂСЋР·РѕРІС‹Р№": "aqua",
        purple: "purple", "С„РёРѕР»РµС‚РѕРІС‹Р№": "purple",
      };
      const className = colors[String(color || "").trim().toLocaleLowerCase("ru-RU")];
      return className ? `<span class="rule-color rule-color-${className}">${text}</span>` : _match;
    })
    .replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, "<em>$1</em>")
    .replace(/(?<!\w)_([^_\n]+?)_(?!\w)/g, "<u>$1</u>");

  const blocks = String(value || "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  if (!blocks.length) return '<div class="rich-text"><p>РўРµРєСЃС‚Р° РїРѕРєР° РЅРµС‚.</p></div>';

  const html = blocks
    .map((block) => {
      const linked = renderInline(block);
      if (linked.startsWith("### ")) return `<h3>${linked.slice(4)}</h3>`;
      if (linked.startsWith("## ")) return `<h2>${linked.slice(3)}</h2>`;
      if (linked.startsWith("# ")) return `<h1>${linked.slice(2)}</h1>`;
      return `<p>${linked.replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
  return `<div class="rich-text">${html}</div>`;
}

function updateReferences(editor) {
  const input = editor.querySelector("[data-note-references-json]");
  const list = editor.querySelector("[data-note-reference-list]");
  if (!input || !list) return;

  let references = [];
  try {
    references = JSON.parse(input.value || "[]");
  } catch {
    references = [];
  }

  list.innerHTML = "";
  references.forEach((reference) => {
    const chip = document.createElement("span");
    chip.className = `note-reference-chip note-reference-chip-${reference.type}`;
    chip.dataset.noteReferenceChip = `${reference.type}:${reference.id}`;

    const kind = document.createElement("span");
    kind.className = "note-reference-kind";
    kind.textContent = referenceTypeLabel(reference.type);
    chip.appendChild(kind);

    const link = document.createElement("a");
    link.href = reference.url || "#";
    link.textContent = reference.label;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    chip.appendChild(link);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.removeNoteReference = `${reference.type}:${reference.id}`;
    remove.setAttribute("aria-label", `\u0423\u0431\u0440\u0430\u0442\u044c \u0441\u0432\u044f\u0437\u044c ${reference.label}`);
    remove.textContent = "\u00d7";
    chip.appendChild(remove);
    list.appendChild(chip);
  });
}

function addReference(editor, button) {
  const input = editor.querySelector("[data-note-references-json]");
  if (!input) return;

  let references = [];
  try {
    references = JSON.parse(input.value || "[]");
  } catch {
    references = [];
  }

  const reference = {
    type: button.dataset.referenceType,
    id: button.dataset.referenceId,
    label: button.dataset.referenceLabel,
    url: button.dataset.referenceUrl,
  };
  const key = `${reference.type}:${reference.id}`;
  if (!references.some((item) => `${item.type}:${item.id}` === key)) {
    references.push(reference);
    input.value = JSON.stringify(references);
    updateReferences(editor);
    showNotesToast("\u0421\u0432\u044f\u0437\u044c \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0430.");
  }
}

function removeReference(editor, key) {
  const input = editor.querySelector("[data-note-references-json]");
  if (!input) return;
  let references = [];
  try {
    references = JSON.parse(input.value || "[]");
  } catch {
    references = [];
  }
  input.value = JSON.stringify(references.filter((item) => `${item.type}:${item.id}` !== key));
  updateReferences(editor);
}

async function openNoteModal(modal) {
  if (!modal) return;
  await closeNoteModals({ refresh: false });
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

async function closeNoteModals({ refresh = true } = {}) {
  clearNoteUrlParam();
  const autosaveForms = [...document.querySelectorAll(".note-edit-modal.is-open [data-note-autosave]")];
  autosaveForms.forEach((form) => window.clearTimeout(noteAutosaveTimers.get(form)));
  document.querySelectorAll(".note-view-modal.is-open, .note-edit-modal.is-open").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  if (!document.querySelector(".material-preview-modal.is-open, .note-confirm-modal.is-open")) {
    document.body.classList.remove("has-modal");
  }
  if (autosaveForms.length) {
    await Promise.all(autosaveForms.map((form) => autosaveNoteForm(form)));
    if (refresh) await refreshNotesPage(window.location.href, { pushState: false }).catch(() => {});
  }
}

function closeMaterialPreview() {
  const modal = document.querySelector("[data-material-preview-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function openNoteConfirm({ kicker = "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435", title, message, actionLabel = "\u0423\u0434\u0430\u043b\u0438\u0442\u044c", onConfirm }) {
  const modal = document.querySelector("[data-note-confirm-modal]");
  if (!modal) return;
  pendingConfirmAction = onConfirm;
  modal.querySelector("[data-note-confirm-kicker]").textContent = kicker;
  modal.querySelector("[data-note-confirm-title]").textContent = title;
  modal.querySelector("[data-note-confirm-message]").textContent = message;
  modal.querySelector("[data-note-confirm-action]").textContent = actionLabel;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeNoteConfirm() {
  const modal = document.querySelector("[data-note-confirm-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  pendingConfirmAction = null;
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open, .material-preview-modal.is-open, [data-note-tag-order-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function updateNoteDeleteActions() {
  const selected = document.querySelectorAll('input[name="note_ids"]:checked').length;
  const button = document.querySelector("[data-open-notes-delete-selected]");
  if (!button) return;
  button.hidden = selected === 0;
  button.disabled = selected === 0;
  const label = button.querySelector("[data-hold-delete-label]");
  const deleteSelectedLabel = "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0435";
  const text = selected ? `${deleteSelectedLabel} (${selected})` : deleteSelectedLabel;
  if (label) label.textContent = text;
  else button.textContent = text;
}

function selectOnlyNoteForDelete(noteId) {
  const deleteForm = document.querySelector("#notes-delete-form");
  if (!deleteForm || !noteId) return null;
  const checkboxes = [...deleteForm.querySelectorAll('input[name="note_ids"]')];
  const target = checkboxes.find((checkbox) => checkbox.value === noteId);
  if (!target) return null;
  checkboxes.forEach((checkbox) => {
    checkbox.checked = checkbox === target;
  });
  updateNoteDeleteActions();
  return deleteForm;
}

function openSingleNoteDeleteConfirm(button) {
  const deleteForm = selectOnlyNoteForDelete(button?.dataset.openNoteDelete);
  if (!deleteForm) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  const label = button.dataset.noteDeleteLabel || "\u0441\u0435\u0441\u0441\u0438\u044e";
  openNoteConfirm({
    kicker: "\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0441\u0435\u0441\u0441\u0438\u0438",
    title: `\u0423\u0434\u0430\u043b\u0438\u0442\u044c ${label}?`,
    message: "\u042d\u0442\u0430 \u0437\u0430\u043f\u0438\u0441\u044c \u0445\u0440\u043e\u043d\u0438\u043a\u0438 \u0431\u0443\u0434\u0435\u0442 \u0443\u0434\u0430\u043b\u0435\u043d\u0430 \u0438\u0437 \u043a\u0430\u043c\u043f\u0435\u0439\u043d\u0430. \u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043d\u0435\u043b\u044c\u0437\u044f \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c.",
    actionLabel: "\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
    onConfirm: async () => {
      try {
        await submitNotesFormAjax(deleteForm);
      } catch {
        showNotesToast("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0435\u0441\u0441\u0438\u044e.");
      }
    },
  });
}

function setupNoteForms() {
  document.querySelectorAll("[data-note-form]").forEach((form) => {
    syncNoteTagButtons(form);
  });
}

function setupNoteOrderDragItems() {
  document.querySelectorAll("[data-note-order-modal-item]").forEach((item) => {
    if (item.dataset.noteDragBound === "true") return;
    item.dataset.noteDragBound = "true";
    item.addEventListener("dragstart", () => {
      draggedNoteTagItem = item;
      item.classList.add("is-dragging");
    });
    item.addEventListener("dragend", () => {
      item.classList.remove("is-dragging");
      draggedNoteTagItem = null;
      updateNoteOrderNumbers();
    });
    item.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (!draggedNoteTagItem || draggedNoteTagItem === item) return;
      const box = item.getBoundingClientRect();
      const after = event.clientY > box.top + box.height / 2;
      item.parentNode.insertBefore(draggedNoteTagItem, after ? item.nextSibling : item);
      noteTagOrderDirty = true;
      updateNoteOrderNumbers();
    });
  });
}

function setupNoteTagDeleteConfirmations() {
  return;
  document.querySelectorAll("[data-confirm-note-tag-delete]").forEach((button) => {
    const form = button.closest("form");
    if (!form || form.dataset.noteDeleteConfirmBound === "true") return;
    form.dataset.noteDeleteConfirmBound = "true";
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const tag = form.dataset.noteTag || "С‚РµРі";
      openNoteConfirm({
        kicker: "РЈРґР°Р»РµРЅРёРµ С‚РµРіР°",
        title: `РЈРґР°Р»РёС‚СЊ В«${tag}В»?`,
        message: button.dataset.confirmNoteTagDelete || "РўРµРі Р±СѓРґРµС‚ СѓРґР°Р»С‘РЅ РёР· СЃРїРёСЃРєР°.",
        actionLabel: "РЈРґР°Р»РёС‚СЊ С‚РµРі",
        onConfirm: async () => {
          try {
            const response = await fetch(form.action, {
              method: "POST",
              body: new FormData(form),
              headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
            });
            if (!response.ok) throw new Error("Tag delete failed.");
            await refreshNotesPage(window.location.href, { pushState: false });
          } catch {
            showNotesToast("РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚РµРі.");
          }
        },
      });
    });
  });
}

function initializeNotesPage() {
  syncNoteFilterState();
  setupNoteForms();
  setupNoteOrderDragItems();
  setupNoteTagDeleteConfirmations();
  updateNoteFilterChips();
  updateNoteDeleteActions();
  if (!initialNoteOpened) {
    const noteId = new URL(window.location.href).searchParams.get("note");
    const modal = noteId ? document.querySelector(`[data-note-view-modal="${CSS.escape(noteId)}"]`) : null;
    if (modal) {
      initialNoteOpened = true;
      openNoteModal(modal);
      clearNoteUrlParam();
    }
  }
}

function updateNoteOrderNumbers() {
  document.querySelectorAll("[data-note-order-modal-item]").forEach((item, index) => {
    const number = item.querySelector("[data-rule-order-number]");
    if (number) number.textContent = String(index + 1);
  });
}

function filterNoteTaxonomyTags(searchInput) {
  const query = normalizeNoteTag(searchInput?.value || "");
  document.querySelectorAll("[data-note-tag-order-item]").forEach((item) => {
    const tag = normalizeNoteTag(item.dataset.noteTag || item.textContent || "");
    const visible = !query || tag.includes(query);
    item.hidden = !visible;
    item.style.display = visible ? "" : "none";
  });
}

function openNoteTagEditor() {
  const modal = document.querySelector("[data-note-tag-editor]");
  const toggle = document.querySelector("[data-toggle-note-tags]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  toggle?.classList.add("is-active");
  toggle?.setAttribute("aria-expanded", "true");
  document.body.classList.add("has-modal");
  window.setTimeout(() => modal.querySelector("[data-note-tag-create-form] input[name='tag']")?.focus(), 30);
}

function closeNoteTagEditor() {
  const modal = document.querySelector("[data-note-tag-editor]");
  const toggle = document.querySelector("[data-toggle-note-tags]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  toggle?.classList.remove("is-active");
  toggle?.setAttribute("aria-expanded", "false");
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open, .material-preview-modal.is-open, .note-confirm-modal.is-open, [data-note-tag-order-modal].is-open, [data-note-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function openNoteTagRenameModal(form) {
  const tag = form?.dataset.noteTag || "";
  const modal = document.querySelector("[data-note-tag-rename-modal]");
  if (!modal || !tag) return;
  pendingNoteTagRenameForm = form;
  const title = modal.querySelector("[data-note-tag-rename-title]");
  if (title) title.textContent = `Переименовать «${tag}»`;
  const input = modal.querySelector("[data-note-tag-rename-input]");
  if (input) input.value = tag;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeNoteTagRenameModal() {
  const modal = document.querySelector("[data-note-tag-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  pendingNoteTagRenameForm = null;
  const input = modal.querySelector("[data-note-tag-rename-input]");
  if (input) input.value = "";
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open, .material-preview-modal.is-open, .note-confirm-modal.is-open, [data-note-tag-order-modal].is-open, [data-note-tag-editor].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

async function saveNoteTagRename() {
  const form = pendingNoteTagRenameForm;
  const oldTag = form?.dataset.noteTag || "";
  const input = document.querySelector("[data-note-tag-rename-input]");
  const newTag = (input?.value || "").trim();
  const campaignSlug = notesPage?.dataset.campaignSlug || document.querySelector("[data-note-tag-create-form] input[name='campaign_slug']")?.value || "";
  const url = document.querySelector("[data-note-tag-editor] .tag-editor-panel")?.dataset.noteTagRenameUrl || "/notes/tags/rename";
  if (!oldTag || !newTag || !campaignSlug) return;
  const body = new FormData();
  body.set("campaign_slug", campaignSlug);
  body.set("old_tag", oldTag);
  body.set("new_tag", newTag);
  const response = await fetch(url, {
    method: "POST",
    body,
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Note tag rename failed.");
  closeNoteTagRenameModal();
  await refreshNotesPage(window.location.href, { pushState: false });
  openNoteTagEditor();
  showNotesToast("Тег переименован.");
}

function openNoteTagOrderModal() {
  const modal = document.querySelector("[data-note-tag-order-modal]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  noteTagOrderDirty = false;
  updateNoteOrderNumbers();
}

async function saveNoteTagOrder() {
  const tags = [...document.querySelectorAll("[data-note-order-modal-item]")]
    .map((item) => item.dataset.noteTag)
    .filter(Boolean);
  const campaignSlug = notesPage?.dataset.campaignSlug;
  const reorderUrl = notesPage?.dataset.noteTagReorderUrl;
  if (!campaignSlug || !reorderUrl || !tags.length) return;

  const response = await fetch(reorderUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
    body: JSON.stringify({ campaign_slug: campaignSlug, tags }),
  });
  if (!response.ok) throw new Error("Note tag order was not saved.");
}

async function closeNoteTagOrderModal({ save = true } = {}) {
  const modal = document.querySelector("[data-note-tag-order-modal]");
  if (!modal) return;
  if (save && noteTagOrderDirty) {
    try {
      await saveNoteTagOrder();
    } catch {
      window.alert("РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РїРѕСЂСЏРґРѕРє С‚РµРіРѕРІ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р·.");
      return;
    }
  }
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open, .material-preview-modal.is-open, .note-confirm-modal.is-open, [data-note-tag-editor].is-open, [data-note-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
  noteTagOrderDirty = false;
}

function renderMaterialPreview(payload) {
  const modal = document.querySelector("[data-material-preview-modal]");
  if (!modal) return;

  const media = modal.querySelector("[data-material-preview-media]");
  const kicker = modal.querySelector("[data-material-preview-kicker]");
  const title = modal.querySelector("[data-material-preview-title]");
  const subtitle = modal.querySelector("[data-material-preview-subtitle]");
  const tags = modal.querySelector("[data-material-preview-tags]");
  const fields = modal.querySelector("[data-material-preview-fields]");
  const page = modal.querySelector("[data-material-preview-page]");
  if (media) {
    const actions = `
      <div class="map-hover-actions material-preview-copy-actions">
        <button class="map-action-button" type="button" data-material-copy-path aria-label="Copy Foundry path" title="Copy Foundry path">&#128279;</button>
        <button class="map-action-button map-image-copy-button" type="button" data-material-copy-image aria-label="Copy image" title="Copy image">
          <span class="map-image-copy-icon" aria-hidden="true"></span>
        </button>
      </div>
    `;
    media.innerHTML = payload.image_url
      ? `<img src="${escapeHtml(payload.image_url)}" alt="${escapeHtml(payload.title || "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b")}">`
      : `<div class="material-preview-placeholder"><span>${escapeHtml(payload.kicker || "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b")}</span></div>`;
    media.insertAdjacentHTML("beforeend", actions);
  }
  if (kicker) kicker.textContent = payload.kicker || "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b";
  if (title) title.textContent = payload.title || "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u0441\u0435\u0441\u0441\u0438\u0438";
  if (subtitle) subtitle.textContent = payload.subtitle || "";
  if (tags) {
    tags.innerHTML = (payload.tags || [])
      .map((tag) => `<span class="material-preview-tag">${escapeHtml(tag)}</span>`)
      .join("") || '<span class="material-preview-tag is-muted">\u0411\u0435\u0437 \u0442\u0435\u0433\u043e\u0432</span>';
  }
  if (fields) {
    fields.innerHTML = (payload.fields || [])
      .map((field) => `
        <button type="button" class="character-copy-field material-preview-field ${field.markdown ? "is-markdown" : ""}" data-material-copy-field="${escapeHtml(field.value || "")}">
          <span>${escapeHtml(field.label || "")}</span>
          <div>${field.markdown ? renderMarkdown(field.value || "") : escapeHtml(field.value || "")}</div>
        </button>
      `)
      .join("");
  }
  if (page) {
    page.href = payload.page_url || "#";
    page.hidden = !payload.page_url;
  }
  const copyPath = modal.querySelector("[data-material-copy-path]");
  const copyImage = modal.querySelector("[data-material-copy-image]");
  if (copyPath) {
    copyPath.dataset.copyFoundryPath = payload.foundry_path || "";
    copyPath.hidden = !payload.foundry_path;
  }
  if (copyImage) {
    copyImage.dataset.copyImageUrl = payload.copy_image_url || "";
    copyImage.dataset.browserImageUrl = payload.image_url || "";
    copyImage.hidden = !payload.copy_image_url;
  }

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

async function openMaterialPreview(button) {
  const endpoint = notesPage?.dataset.materialPreviewEndpoint;
  const campaign = notesPage?.dataset.campaignSlug;
  const type = button.dataset.materialPreviewType;
  const id = button.dataset.materialPreviewId;
  if (!endpoint || !campaign || !type) return;

  const url = new URL(endpoint, window.location.origin);
  url.searchParams.set("campaign", campaign);
  url.searchParams.set("type", type);
  url.searchParams.set("id", id || "");

  try {
    const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    if (!response.ok) throw new Error("preview failed");
    renderMaterialPreview(await response.json());
  } catch {
    showNotesToast("\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.");
  }
}

document.addEventListener("keydown", async (event) => {
  if (event.key !== "Escape") return;
  if (document.querySelector(".note-confirm-modal.is-open")) {
    closeNoteConfirm();
    return;
  }
  if (document.querySelector("[data-note-tag-order-modal].is-open")) {
    closeNoteTagOrderModal({ save: false });
    return;
  }
  if (document.querySelector(".material-preview-modal.is-open")) {
    closeMaterialPreview();
    return;
  }
  if (document.querySelector("[data-session-calendar-modal].is-open")) {
    closeSessionCalendar();
    return;
  }
  await closeNoteModals();
});

document.addEventListener("pointerover", (event) => {
  const calendarDay = event.target.closest("[data-calendar-tooltip]");
  if (calendarDay) showSessionCalendarTooltip(calendarDay);
});

document.addEventListener("pointerout", (event) => {
  const calendarDay = event.target.closest("[data-calendar-tooltip]");
  if (calendarDay && !calendarDay.contains(event.relatedTarget)) hideSessionCalendarTooltip();
});

document.addEventListener("focusin", (event) => {
  const calendarDay = event.target.closest("[data-calendar-tooltip]");
  if (calendarDay) showSessionCalendarTooltip(calendarDay);
});

document.addEventListener("focusout", (event) => {
  const calendarDay = event.target.closest("[data-calendar-tooltip]");
  if (calendarDay && !calendarDay.contains(event.relatedTarget)) hideSessionCalendarTooltip();
});

document.addEventListener("click", async (event) => {
  if (event.target.closest("[data-close-note-confirm]")) {
    closeNoteConfirm();
    return;
  }

  if (event.target.closest("[data-note-confirm-action]")) {
    const action = pendingConfirmAction;
    closeNoteConfirm();
    if (typeof action === "function") action();
    return;
  }

  const materialCloseButton = event.target.closest("[data-close-material-preview]");
  if (materialCloseButton) {
    closeMaterialPreview();
    return;
  }

  if (event.target.closest("[data-close-session-calendar]")) {
    closeSessionCalendar();
    return;
  }

  if (event.target.closest("[data-open-session-calendar]")) {
    openSessionCalendar();
    return;
  }

  if (event.target.closest("[data-session-calendar-prev]")) {
    sessionCalendarMonth = sessionCalendarMonth || initialSessionCalendarMonth(loadSessionCalendarEvents());
    sessionCalendarMonth = new Date(sessionCalendarMonth.getFullYear(), sessionCalendarMonth.getMonth() - 1, 1);
    renderSessionCalendar();
    return;
  }

  if (event.target.closest("[data-session-calendar-next]")) {
    sessionCalendarMonth = sessionCalendarMonth || initialSessionCalendarMonth(loadSessionCalendarEvents());
    sessionCalendarMonth = new Date(sessionCalendarMonth.getFullYear(), sessionCalendarMonth.getMonth() + 1, 1);
    renderSessionCalendar();
    return;
  }

  const calendarSession = event.target.closest("[data-open-calendar-session]");
  if (calendarSession) {
    const sessionId = calendarSession.dataset.openCalendarSession;
    closeSessionCalendar();
    const modal = document.querySelector(`[data-note-view-modal="${CSS.escape(sessionId)}"]`);
    if (modal) {
      await openNoteModal(modal);
    } else {
      const url = new URL(window.location.origin + "/notes");
      url.searchParams.set("campaign", notesPage?.dataset.campaignSlug || "");
      url.searchParams.set("note", sessionId);
      window.location.assign(url.toString());
    }
    return;
  }

  const materialCopyPathButton = event.target.closest("[data-material-copy-path]");
  if (materialCopyPathButton) {
    const foundryPath = materialCopyPathButton.dataset.copyFoundryPath || "";
    if (foundryPath) {
      await copyTextToClipboard(foundryPath);
      showNotesToast("Foundry-\u043f\u0443\u0442\u044c \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d");
      return;
    }
    showNotesToast("Foundry-\u043f\u0443\u0442\u044c \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d");
    return;
  }

  const materialCopyImageButton = event.target.closest("[data-material-copy-image]");
  if (materialCopyImageButton) {
    try {
      showNotesToast("\u0413\u043e\u0442\u043e\u0432\u043b\u044e \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435...");
      await copyMaterialImage(materialCopyImageButton.dataset.copyImageUrl, materialCopyImageButton.dataset.browserImageUrl);
      showNotesToast("\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u043e");
    } catch {
      showNotesToast("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435");
    }
    return;
  }

  const materialCopyField = event.target.closest("[data-material-copy-field]");
  if (materialCopyField) {
    await copyTextToClipboard(materialCopyField.dataset.materialCopyField || "");
    showNotesToast("Поле скопировано");
    return;
  }

  if (event.target.closest("[data-close-note-tag-order]")) {
    closeNoteTagOrderModal({ save: false });
    return;
  }

  if (event.target.closest("[data-open-note-tag-order]")) {
    openNoteTagOrderModal();
    return;
  }

  if (event.target.closest("[data-save-note-tag-order]")) {
    saveNoteTagOrder()
      .then(() => {
        closeNoteTagOrderModal({ save: false });
        return refreshNotesPage(window.location.href, { pushState: false });
      })
      .catch(() => window.alert("РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РїРѕСЂСЏРґРѕРє С‚РµРіРѕРІ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р·."));
    return;
  }

  const closeButton = event.target.closest("[data-close-note-modal]");
  if (closeButton) {
    await closeNoteModals();
    return;
  }

  const resetFilters = event.target.closest("[data-notes-reset-filters]");
  if (resetFilters) {
    event.preventDefault();
    refreshNotesPage(resetFilters.href).catch(() => {
      window.location.href = resetFilters.href;
    });
    return;
  }

  const materialButton = event.target.closest("[data-material-preview-type]");
  if (materialButton) {
    event.preventDefault();
    openMaterialPreview(materialButton);
    return;
  }

  const editButton = event.target.closest("[data-open-note-edit]");
  if (editButton) {
    event.preventDefault();
    await openNoteModal(document.querySelector(`[data-note-edit-modal="${editButton.dataset.openNoteEdit}"]`));
    return;
  }

  const createButton = event.target.closest("[data-open-note-create]");
  if (createButton) {
    event.preventDefault();
    await openNoteModal(document.querySelector("[data-note-create-modal]"));
    return;
  }

  const viewButton = event.target.closest("[data-open-note-view]");
  if (viewButton) {
    event.preventDefault();
    await openNoteModal(document.querySelector(`[data-note-view-modal="${viewButton.dataset.openNoteView}"]`));
    return;
  }

  const singleDeleteButton = event.target.closest("[data-open-note-delete]");
  if (singleDeleteButton) {
    event.preventDefault();
    openSingleNoteDeleteConfirm(singleDeleteButton);
    return;
  }

  const deleteSelectedButton = event.target.closest("[data-open-notes-delete-selected]");
  if (deleteSelectedButton) {
    const selected = document.querySelectorAll('input[name="note_ids"]:checked').length;
    if (!selected) return;
    openNoteConfirm({
      kicker: "\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435 \u0441\u0435\u0441\u0441\u0438\u0439",
      title: `\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0435 \u0441\u0435\u0441\u0441\u0438\u0438 (${selected})?`,
      message: "\u0412\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0435 \u0437\u0430\u043f\u0438\u0441\u0438 \u0445\u0440\u043e\u043d\u0438\u043a\u0438 \u0431\u0443\u0434\u0443\u0442 \u0443\u0434\u0430\u043b\u0435\u043d\u044b \u0438\u0437 \u043a\u0430\u043c\u043f\u0435\u0439\u043d\u0430. \u042d\u0442\u043e \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043d\u0435\u043b\u044c\u0437\u044f \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c.",
      actionLabel: "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0435",
      onConfirm: async () => {
        try {
          await submitNotesFormAjax(document.querySelector("#notes-delete-form"));
        } catch {
          showNotesToast("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0435\u0441\u0441\u0438\u0438.");
        }
      },
    });
    return;
  }

  const deleteAllButton = event.target.closest("[data-open-notes-delete-all]");
  if (deleteAllButton) {
    const total = document.querySelectorAll('input[name="note_ids"]').length;
    openNoteConfirm({
      kicker: "\u041f\u043e\u043b\u043d\u0430\u044f \u043e\u0447\u0438\u0441\u0442\u043a\u0430",
      title: "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u0441\u0435 \u0441\u0435\u0441\u0441\u0438\u0438?",
      message: `\u0411\u0443\u0434\u0435\u0442 \u0443\u0434\u0430\u043b\u0435\u043d\u0430 \u0432\u0441\u044f \u0445\u0440\u043e\u043d\u0438\u043a\u0430 \u043a\u0430\u043c\u043f\u0435\u0439\u043d\u0430: ${total} \u0441\u0435\u0441\u0441\u0438\u0439. \u042d\u0442\u043e \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043d\u0435\u043b\u044c\u0437\u044f \u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c.`,
      actionLabel: "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u0441\u0451",
      onConfirm: async () => {
        try {
          await submitNotesFormAjax(document.querySelector("#notes-delete-all-form"));
        } catch {
          showNotesToast("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0441\u0435\u0441\u0441\u0438\u0438.");
        }
      },
    });
    return;
  }

  const tagButton = event.target.closest("[data-insert-note-tag]");
  if (tagButton) {
    const input = tagButton.closest("[data-note-form]")?.querySelector('input[name="tags"]');
    if (input) {
      toggleNoteTag(input, tagButton.dataset.insertNoteTag);
      scheduleNoteAutosave(input.closest("[data-note-form]"));
    }
  }

  const includeTagButton = event.target.closest("[data-note-include-tag]");
  if (includeTagButton) {
    const tag = normalizeNoteTag(includeTagButton.dataset.noteIncludeTag);
    includedNoteTags.has(tag) ? includedNoteTags.delete(tag) : (includedNoteTags.add(tag), excludedNoteTags.delete(tag));
    updateNoteFilterChips();
    refreshNotesPage(noteFilterUrl()).catch(() => {
      window.location.href = noteFilterUrl();
    });
    return;
  }

  const excludeTagButton = event.target.closest("[data-note-exclude-tag]");
  if (excludeTagButton) {
    const tag = normalizeNoteTag(excludeTagButton.dataset.noteExcludeTag);
    excludedNoteTags.has(tag) ? excludedNoteTags.delete(tag) : (excludedNoteTags.add(tag), includedNoteTags.delete(tag));
    updateNoteFilterChips();
    refreshNotesPage(noteFilterUrl()).catch(() => {
      window.location.href = noteFilterUrl();
    });
    return;
  }

  const tabButton = event.target.closest("[data-note-tab]");
  if (tabButton) {
    const form = tabButton.closest("[data-note-form]");
    const body = form?.querySelector("[data-note-body]");
    const preview = form?.querySelector("[data-note-preview-panel]");
    const write = form?.querySelector("[data-note-write-panel]");
    form?.querySelectorAll("[data-note-tab]").forEach((button) => button.classList.toggle("is-active", button === tabButton));
    if (tabButton.dataset.noteTab === "preview") {
      preview.innerHTML = renderMarkdown(body?.value || "");
      preview.hidden = false;
      write.hidden = true;
    } else {
      preview.hidden = true;
      write.hidden = false;
    }
  }

  const sessionTextTab = event.target.closest("[data-session-text-tab]");
  if (sessionTextTab) {
    const form = sessionTextTab.closest("[data-note-form]");
    const target = sessionTextTab.dataset.sessionTextTab;
    form?.querySelectorAll("[data-session-text-tab]").forEach((button) => {
      button.classList.toggle("is-active", button === sessionTextTab);
    });
    form?.querySelectorAll("[data-session-text-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.sessionTextPanel !== target;
    });
  }

  const statusButton = event.target.closest("[data-session-status-value]");
  if (statusButton) {
    const switcher = statusButton.closest("[data-session-status-switch]");
    const input = switcher?.querySelector("[data-session-status-input]");
    if (input) input.value = statusButton.dataset.sessionStatusValue;
    switcher?.querySelectorAll("[data-session-status-value]").forEach((button) => {
      button.classList.toggle("is-active", button === statusButton);
    });
    scheduleNoteAutosave(statusButton.closest("[data-note-form]"), { refreshStats: true });
  }

  const toggleReferences = event.target.closest("[data-toggle-reference-picker]");
  if (toggleReferences) {
    const picker = toggleReferences.closest("[data-note-reference-editor]")?.querySelector("[data-note-reference-picker]");
    if (picker) {
      picker.hidden = !picker.hidden;
      if (!picker.hidden) {
        ensureReferenceOptionsLoaded(picker);
        filterReferenceOptions(picker.querySelector("[data-reference-search]"));
      }
    }
  }

  const addReferenceButton = event.target.closest("[data-add-note-reference]");
  if (addReferenceButton) {
    const editor = addReferenceButton.closest("[data-note-reference-editor]");
    if (editor) addReference(editor, addReferenceButton);
    const form = addReferenceButton.closest("[data-note-form]");
    window.clearTimeout(noteAutosaveTimers.get(form));
    autosaveNoteForm(form);
  }

  const removeReferenceButton = event.target.closest("[data-remove-note-reference]");
  if (removeReferenceButton) {
    const editor = removeReferenceButton.closest("[data-note-reference-editor]");
    if (editor) removeReference(editor, removeReferenceButton.dataset.removeNoteReference);
    const form = removeReferenceButton.closest("[data-note-form]");
    window.clearTimeout(noteAutosaveTimers.get(form));
    autosaveNoteForm(form);
  }

  const tagToggle = event.target.closest("[data-toggle-note-tags]");
  if (tagToggle) {
    const modal = document.querySelector("[data-note-tag-editor]");
    if (modal?.classList.contains("is-open")) closeNoteTagEditor();
    else openNoteTagEditor();
    return;
  }

  if (event.target.closest("[data-close-note-tags]")) {
    closeNoteTagEditor();
    return;
  }

  const renameNoteTagButton = event.target.closest("[data-note-rename-tag]");
  if (renameNoteTagButton) {
    openNoteTagRenameModal(renameNoteTagButton.closest("[data-note-tag-order-item]"));
    return;
  }

  if (event.target.closest("[data-close-note-tag-rename]")) {
    closeNoteTagRenameModal();
    return;
  }

  if (event.target.closest("[data-save-note-tag-rename]")) {
    saveNoteTagRename().catch(() => showNotesToast("Не удалось переименовать тег."));
    return;
  }
});

document.addEventListener("input", (event) => {
  const autosaveControl = event.target.closest("[data-note-autosave] input, [data-note-autosave] textarea, [data-note-autosave] select");
  if (autosaveControl && !autosaveControl.matches("[data-reference-search]")) {
    scheduleNoteAutosave(autosaveControl.closest("[data-note-form]"), { refreshStats: shouldRefreshSessionStats(autosaveControl) });
  }

  const filterSearch = event.target.closest('.session-filter-row input[name="q"]');
  if (filterSearch) {
    window.clearTimeout(noteFilterDebounce);
    noteFilterDebounce = window.setTimeout(() => {
      const form = filterSearch.closest(".session-filter-row");
      if (form) submitNotesFilterAjax(form);
    }, 360);
  }

  const tagSearch = event.target.closest("[data-note-taxonomy-tag-search]");
  if (tagSearch) {
    filterNoteTaxonomyTags(tagSearch);
    return;
  }

  const input = event.target.closest("[data-reference-search]");
  if (!input) return;
  filterReferenceOptions(input);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.target.closest("[data-note-tag-rename-input]")) {
    event.preventDefault();
    saveNoteTagRename().catch(() => showNotesToast("Не удалось переименовать тег."));
  }
});

document.addEventListener("submit", (event) => {
  const filterForm = event.target.closest(".session-filter-row");
  if (filterForm) {
    event.preventDefault();
    submitNotesFilterAjax(filterForm);
    return;
  }

  const tagCreateForm = event.target.closest("[data-note-tag-create-form]");
  if (tagCreateForm) {
    event.preventDefault();
    fetch(tagCreateForm.action, {
      method: "POST",
      body: new FormData(tagCreateForm),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Tag create failed.");
        return refreshNotesPage(window.location.href, { pushState: false });
      })
      .then(() => showNotesToast("РўРµРі СЃРѕР·РґР°РЅ."))
      .catch(() => showNotesToast("РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ С‚РµРі."));
  }
});

document.addEventListener("submit", (event) => {
  const tagDeleteForm = event.target.closest("[data-note-tag-order-item]");
  if (tagDeleteForm) {
    event.preventDefault();
    submitNotesFormAjax(tagDeleteForm).catch(() => showNotesToast("РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ С‚РµРі."));
    return;
  }

  if (event.target.closest("#notes-delete-form, #notes-delete-all-form")) {
    event.preventDefault();
    submitNotesFormAjax(event.target).catch(() => showNotesToast("РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ СЃРµСЃСЃРёРё."));
  }
});

document.addEventListener("hold-delete:submit", (event) => {
  const singleDeleteButton = event.target.closest("[data-open-note-delete]");
  if (!singleDeleteButton) return;
  event.preventDefault();
  openSingleNoteDeleteConfirm(singleDeleteButton);
});

document.addEventListener("change", (event) => {
  if (event.target.matches('input[name="note_ids"]')) updateNoteDeleteActions();
  const autosaveControl = event.target.closest("[data-note-autosave] input, [data-note-autosave] textarea, [data-note-autosave] select");
  const isTextLikeAutosave = autosaveControl?.matches('textarea, input:not([type]), input[type="text"], input[type="search"]');
  if (autosaveControl && !isTextLikeAutosave) {
    scheduleNoteAutosave(autosaveControl.closest("[data-note-form]"), { refreshStats: shouldRefreshSessionStats(autosaveControl) });
  }
  const filterControl = event.target.closest('.session-filter-row select, .session-filter-row input[type="date"]');
  if (filterControl) {
    const form = filterControl.closest(".session-filter-row");
    if (form) submitNotesFilterAjax(form);
  }
});

window.addEventListener("popstate", () => {
  refreshNotesPage(window.location.href, { pushState: false }).catch(() => window.location.reload());
});

initializeNotesPage();
