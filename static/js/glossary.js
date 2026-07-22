function setRuleEditMode(modal, isEditing) {
  const editPanel = modal?.querySelector("[data-rule-edit-panel]");
  if (!editPanel) return;
  editPanel.hidden = !isEditing;
  if (!isEditing) editPanel.open = false;
  if (isEditing) editPanel.open = true;
}

async function closeRuleModals({ save = true } = {}) {
  const openForms = save
    ? [...document.querySelectorAll("[data-rule-modal].is-open [data-rule-edit-panel]:not([hidden]) .rule-edit-form")]
    : [];
  document.querySelectorAll("[data-rule-modal]").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
    setRuleEditMode(modal, false);
  });
  syncRuleBodyModalState();
  clearInitialRuleFromUrl();
  if (openForms.length) {
    await Promise.all(openForms.map((form) => saveRuleEditForm(form)));
  }
}

function clearInitialRuleFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("rule")) return;
  url.searchParams.delete("rule");
  window.history.replaceState({}, "", url.toString());
}

function ensureRuleSelectOption(select, value) {
  if (!select || !value) return;
  const exists = [...select.options].some((option) => normalizeRuleTag(option.value) === normalizeRuleTag(value));
  if (exists) return;
  const option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  select.appendChild(option);
}

function normalizeRuleModalContent(content) {
  if (!content) return;
  content.querySelector(":scope > h1:first-child, :scope > h2:first-child")?.remove();
}

function fillRuleModal(rule) {
  const modal = document.querySelector("[data-rule-modal]");
  if (!modal || !rule?.id) return modal;
  modal.dataset.ruleModal = rule.id;
  modal.dataset.loadedRuleId = rule.id;
  modal.querySelector(".rules-reader-dialog")?.setAttribute("aria-label", rule.title || "Правило");
  const title = modal.querySelector("[data-rule-modal-title]");
  const tag = modal.querySelector("[data-rule-modal-tag]");
  const source = modal.querySelector("[data-rule-modal-source]");
  const page = modal.querySelector("[data-rule-modal-page]");
  const book = modal.querySelector("[data-rule-modal-book]");
  const content = modal.querySelector("[data-rule-content]");
  const form = modal.querySelector(".rule-edit-form");
  const deleteForm = modal.querySelector("[data-rule-delete-form]");
  const favoriteButton = modal.querySelector("[data-favorite-toggle][data-favorite-type='rule']");

  if (title) title.textContent = rule.title || "Правило";
  if (tag) tag.textContent = rule.tag || "";
  if (source) source.textContent = rule.source || "";
  if (page) {
    page.textContent = rule.page ? `стр. ${rule.page}` : "";
    page.hidden = !rule.page;
  }
  if (book) {
    book.href = rule.book_url || "#";
    book.hidden = !rule.book_url;
  }
  if (content) {
    content.innerHTML = rule.content_html || "<p>Текста пока нет.</p>";
    normalizeRuleModalContent(content);
  }
  if (favoriteButton) {
    favoriteButton.dataset.favoriteId = rule.id || "";
    favoriteButton.dataset.favoriteTitle = rule.title || "";
    favoriteButton.setAttribute("aria-label", `Добавить правило ${rule.title || ""} в избранное`);
    if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
  }

  if (form) {
    form.action = `/rules/${encodeURIComponent(rule.id)}/update`;
    const titleInput = form.querySelector('input[name="title"]');
    const pageInput = form.querySelector('input[name="page"]');
    const bookInput = form.querySelector('input[name="book_url"]');
    const contentInput = form.querySelector('textarea[name="content"]');
    if (titleInput) titleInput.value = rule.title || "";
    if (pageInput) pageInput.value = rule.page || "";
    if (bookInput) bookInput.value = rule.book_url || "";
    if (contentInput) contentInput.value = rule.content || "";
    const tagSelect = form.querySelector('select[name="tag"]');
    const sourceSelect = form.querySelector('select[name="source"]');
    ensureRuleSelectOption(tagSelect, rule.tag || "");
    ensureRuleSelectOption(sourceSelect, rule.source || "");
    if (tagSelect) tagSelect.value = rule.tag || "";
    if (sourceSelect) sourceSelect.value = rule.source || "";
  }

  if (deleteForm) {
    deleteForm.action = `/rules/${encodeURIComponent(rule.id)}/delete`;
    deleteForm.dataset.ruleTitle = rule.title || "";
  }
  return modal;
}

async function loadRuleIntoModal(ruleId) {
  const modal = document.querySelector("[data-rule-modal]");
  if (!modal || modal.dataset.loadedRuleId === ruleId) return modal;
  fillRuleModal({
    id: ruleId,
    title: "Загружаю правило...",
    tag: "Правило",
    source: "",
    page: "",
    book_url: "",
    content: "",
    content_html: "<p>Загружаю правило...</p>",
  });
  delete modal.dataset.loadedRuleId;
  const response = await fetch(`/rules/${encodeURIComponent(ruleId)}/preview`, {
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule was not loaded.");
  return fillRuleModal(payload.rule);
}

async function openRuleModal(ruleId, isEditing = false) {
  await closeRuleModals();
  closeRuleSearch();
  const modal = await loadRuleIntoModal(ruleId).catch(() => null);
  if (!modal) return;
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  setRuleEditMode(modal, isEditing);
  document.body.classList.add("has-modal");
}

const ruleSearchModal = document.querySelector("[data-rule-search-modal]");
const ruleSearchInput = document.querySelector("[data-rule-search-input]");
const rulesGroups = document.querySelector("[data-rules-groups]");
const ruleTaxonomyModal = document.querySelector("[data-rule-taxonomy-modal]");
const ruleTagOrderModal = document.querySelector("[data-rule-tag-order-modal]");
const ruleTagOrderModalList = document.querySelector("[data-rule-order-modal-list]");
const ruleSourceOrderModal = document.querySelector("[data-rule-source-order-modal]");
const ruleSourceOrderModalList = document.querySelector("[data-rule-source-order-modal-list]");
const ruleTagRenameModal = document.querySelector("[data-rule-tag-rename-modal]");
const ruleSourceRenameModal = document.querySelector("[data-rule-source-rename-modal]");
const ruleTagDeleteModal = document.querySelector("[data-rule-tag-delete-modal]");
const ruleSourceDeleteModal = document.querySelector("[data-rule-source-delete-modal]");
const ruleDeleteModal = document.querySelector("[data-rule-delete-modal]");
const scrollTopZone = document.querySelector("[data-scroll-top-zone]");
const ruleToast = document.querySelector("[data-rule-toast]");
const serviceRuleTag = rulesGroups?.dataset.serviceRuleTag || "Без категории";
const includedRuleTags = new Set();
const excludedRuleTags = new Set();
let draggedRuleTagItem = null;
let draggedRuleSourceItem = null;
let ruleTagOrderDirty = false;
let ruleSourceOrderDirty = false;
let pendingRuleTagDeleteForm = null;
let pendingRuleSourceDeleteForm = null;
let pendingRuleDeleteForm = null;
let pendingRuleTagRenameForm = null;
let pendingRuleSourceRenameForm = null;
let activeRuleDeleteHold = null;
let ruleTaxonomyActiveTab = "categories";

function showRuleToast(message) {
  if (!ruleToast) return;
  ruleToast.textContent = message;
  ruleToast.classList.add("is-visible");
  window.clearTimeout(showRuleToast.timer);
  showRuleToast.timer = window.setTimeout(() => ruleToast.classList.remove("is-visible"), 1700);
}

function normalizeRuleTag(tag) {
  return (tag || "").trim().toLocaleLowerCase("ru-RU");
}

function hasActiveRuleCategoryFilters() {
  return includedRuleTags.size > 0 || excludedRuleTags.size > 0;
}

function isRuleGroupVisibleByTag(tag) {
  if (!hasActiveRuleCategoryFilters()) return true;
  const normalized = normalizeRuleTag(tag);
  return (includedRuleTags.size === 0 || includedRuleTags.has(normalized)) && !excludedRuleTags.has(normalized);
}

function syncRuleGroupFilterState(group) {
  if (!group) return;
  group.hidden = !isRuleGroupVisibleByTag(group.dataset.ruleTag || "");
}

function hasOpenRuleOverlay() {
  return !!(
    document.querySelector(".rule-modal.is-open")
    || ruleSearchModal?.classList.contains("is-open")
    || ruleTaxonomyModal?.classList.contains("is-open")
    || ruleTagOrderModal?.classList.contains("is-open")
    || ruleSourceOrderModal?.classList.contains("is-open")
    || ruleTagRenameModal?.classList.contains("is-open")
    || ruleSourceRenameModal?.classList.contains("is-open")
    || ruleTagDeleteModal?.classList.contains("is-open")
    || ruleSourceDeleteModal?.classList.contains("is-open")
    || ruleDeleteModal?.classList.contains("is-open")
  );
}

function syncRuleBodyModalState() {
  document.body.classList.toggle("has-modal", hasOpenRuleOverlay());
}

function updateRuleCategoryFilters() {
  const hasFilters = hasActiveRuleCategoryFilters();
  const currentHeight = rulesGroups?.offsetHeight || 0;
  if (rulesGroups && currentHeight) {
    rulesGroups.style.minHeight = hasFilters ? `${currentHeight}px` : "";
    rulesGroups.classList.toggle("is-filtered", hasFilters);
  }
  let visibleGroups = 0;

  document.querySelectorAll("[data-rule-group]").forEach((group) => {
    const tag = normalizeRuleTag(group.dataset.ruleTag);
    const isIncluded = includedRuleTags.size === 0 || includedRuleTags.has(tag);
    const isExcluded = excludedRuleTags.has(tag);
    const isVisible = !hasFilters || (isIncluded && !isExcluded);
    group.hidden = !isVisible;
    if (isVisible) visibleGroups += 1;
  });

  document.querySelectorAll("[data-rule-filter-chip]").forEach((chip) => {
    const tag = normalizeRuleTag(chip.dataset.ruleFilterChip);
    chip.classList.toggle("is-included", includedRuleTags.has(tag));
    chip.classList.toggle("is-excluded", excludedRuleTags.has(tag));
    chip.classList.toggle("is-muted", hasFilters && !includedRuleTags.has(tag) && !excludedRuleTags.has(tag));
  });

  const hint = document.querySelector("[data-rule-filter-hint]");
  if (hint) {
    if (!hasFilters) {
      hint.textContent = "Клик по категории показывает только её. Кнопка − исключает категорию из списка.";
    } else if (visibleGroups === 0) {
      hint.textContent = "Нет категорий под текущие фильтры. Сбросьте фильтры или измените исключения.";
    } else {
      hint.textContent = `Показано категорий: ${visibleGroups}.`;
    }
  }

  if (rulesGroups && !hasFilters) {
    window.setTimeout(() => {
      rulesGroups.style.minHeight = "";
      rulesGroups.classList.remove("is-filtered");
    }, 180);
  }
}

function filterRuleFilterTags(searchInput) {
  const query = normalizeRuleTag(searchInput.value || "");
  document.querySelectorAll("[data-rule-filter-chip]").forEach((chip) => {
    const tag = normalizeRuleTag(chip.dataset.ruleFilterChip || chip.textContent || "");
    const visible = !query || tag.includes(query);
    chip.hidden = !visible;
    chip.style.display = visible ? "" : "none";
  });
}

function setRuleTaxonomyTab(tabName = "categories") {
  ruleTaxonomyActiveTab = tabName === "sources" ? "sources" : "categories";
  const modal = ruleTaxonomyModal || document.querySelector("[data-rule-taxonomy-modal]");
  if (!modal) return;
  modal.querySelectorAll("[data-rule-taxonomy-tab]").forEach((tab) => {
    const isActive = tab.dataset.ruleTaxonomyTab === ruleTaxonomyActiveTab;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
    tab.tabIndex = isActive ? 0 : -1;
  });
  modal.querySelectorAll("[data-rule-taxonomy-pane]").forEach((pane) => {
    const isActive = pane.dataset.ruleTaxonomyPane === ruleTaxonomyActiveTab;
    pane.classList.toggle("is-active", isActive);
    pane.hidden = !isActive;
  });
}

function filterRuleTaxonomyList(input) {
  const kind = input?.dataset.ruleTaxonomySearch || "categories";
  const query = normalizeRuleTag(input?.value || "");
  const selector = kind === "sources" ? "[data-rule-source-order-item]" : "[data-rule-tag-order-item]";
  document.querySelectorAll(selector).forEach((item) => {
    const label = kind === "sources" ? item.dataset.ruleSource : item.dataset.ruleTag;
    const visible = !query || normalizeRuleTag(label).includes(query);
    item.hidden = !visible;
    item.style.display = visible ? "" : "none";
  });
}

function getRuleTagOrderItems() {
  return [...document.querySelectorAll("[data-rule-tag-order-item]")];
}

function currentRuleTagOrder() {
  return getRuleTagOrderItems().map((item) => item.dataset.ruleTag).join("||");
}

function moveRuleGroupInPage(tag, beforeTag = "") {
  const group = document.querySelector(`[data-rule-group][data-rule-tag="${CSS.escape(tag)}"]`);
  if (!group || !rulesGroups) return;

  const beforeGroup = beforeTag
    ? document.querySelector(`[data-rule-group][data-rule-tag="${CSS.escape(beforeTag)}"]`)
    : null;

  if (beforeGroup && beforeGroup !== group) {
    rulesGroups.insertBefore(group, beforeGroup);
  } else if (!beforeGroup) {
    rulesGroups.appendChild(group);
  }
}

function syncRuleTagDependentOrder() {
  const orderedItems = getRuleTagOrderItems();
  const filterList = document.querySelector("[data-rule-filters]");

  orderedItems.forEach((item, index) => {
    const tag = item.dataset.ruleTag;
    const nextItem = orderedItems[index + 1];
    moveRuleGroupInPage(tag, nextItem?.dataset.ruleTag || "");

    const chip = document.querySelector(`[data-rule-filter-chip="${CSS.escape(tag)}"]`);
    const nextChip = nextItem
      ? document.querySelector(`[data-rule-filter-chip="${CSS.escape(nextItem.dataset.ruleTag)}"]`)
      : null;
    if (chip && filterList) {
      if (nextChip && nextChip !== chip) {
        filterList.insertBefore(chip, nextChip);
      } else if (!nextChip) {
        filterList.appendChild(chip);
      }
    }
  });
}

function getRuleOrderModalItems() {
  return [...document.querySelectorAll("[data-rule-order-modal-item]")];
}

function getRuleSourceOrderModalItems() {
  return [...document.querySelectorAll("[data-rule-source-order-modal-item]")];
}

function updateRuleOrderNumbers() {
  getRuleOrderModalItems().forEach((item, index) => {
    const number = item.querySelector("[data-rule-order-number]");
    if (number) number.textContent = String(index + 1);
  });
  getRuleSourceOrderModalItems().forEach((item, index) => {
    const number = item.querySelector("[data-rule-order-number]");
    if (number) number.textContent = String(index + 1);
  });
}

async function saveRuleTagOrder(tags = getRuleOrderModalItems().map((item) => item.dataset.ruleTag)) {
  if (!tags.length) return;
  const response = await fetch("/rules/tags/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
  });
  if (!response.ok) {
    throw new Error("Rule tag order was not saved.");
  }
}

async function saveRuleSourceOrder(sources = getRuleSourceOrderModalItems().map((item) => item.dataset.ruleSource)) {
  if (!sources.length) return;
  const response = await fetch("/rules/sources/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources }),
  });
  if (!response.ok) {
    throw new Error("Rule source order was not saved.");
  }
}

function ruleTagAlreadyExists(tag) {
  const key = normalizeRuleTag(tag);
  return getRuleTagOrderItems().some((item) => normalizeRuleTag(item.dataset.ruleTag) === key);
}

function ruleSourceAlreadyExists(source) {
  const key = normalizeRuleTag(source);
  return getRuleSourceOrderModalItems().some((item) => normalizeRuleTag(item.dataset.ruleSource) === key);
}

function createRuleTaxonomyIconButton(kind, value) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "audio-taxonomy-icon-button map-tag-icon-button";
  if (kind === "source") {
    button.dataset.openRuleSourceRename = value;
    button.setAttribute("aria-label", `Переименовать источник ${value}`);
  } else {
    button.dataset.openRuleTagRename = value;
    button.setAttribute("aria-label", `Переименовать категорию ${value}`);
  }
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z"/></svg>';
  return button;
}

function createRuleTaxonomyDeleteButton(kind, value, disabled = false) {
  const button = document.createElement("button");
  button.type = "button";
  if (disabled) {
    button.disabled = true;
    button.textContent = "Сервисная";
    return button;
  }
  button.className = "hold-delete-button";
  button.dataset.holdSubmit = "";
  button.dataset.holdStaticIcon = "";
  button.style.setProperty("--hold-progress", "0");
  button.setAttribute("aria-label", `Удалить ${kind === "source" ? "источник" : "категорию"} ${value}`);
  button.innerHTML = '<span data-hold-delete-label><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span>';
  return button;
}

function createRuleTagDeleteForm(tag) {
  const form = document.createElement("form");
  form.action = "/rules/tags/delete";
  form.method = "post";
  form.dataset.ruleTagOrderItem = "";
  form.dataset.ruleTag = tag;

  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "tag";
  input.value = tag;

  const view = document.createElement("div");
  view.className = "audio-tag-row-view map-tag-row-view";
  const label = document.createElement("span");
  label.textContent = tag;
  view.appendChild(label);

  if (normalizeRuleTag(tag) === normalizeRuleTag(serviceRuleTag)) {
    const editButton = createRuleTaxonomyIconButton("tag", tag);
    editButton.disabled = true;
    view.append(editButton, createRuleTaxonomyDeleteButton("tag", tag, true));
  } else {
    view.append(createRuleTaxonomyIconButton("tag", tag), createRuleTaxonomyDeleteButton("tag", tag));
  }

  form.append(input, view);
  return form;
}

function createRuleSourceDeleteForm(source) {
  const form = document.createElement("form");
  form.action = "/rules/sources/delete";
  form.method = "post";
  form.dataset.ruleSourceOrderItem = "";
  form.dataset.ruleSource = source;

  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "source";
  input.value = source;

  const view = document.createElement("div");
  view.className = "audio-tag-row-view map-tag-row-view";
  const label = document.createElement("span");
  label.textContent = source;
  view.append(label, createRuleTaxonomyIconButton("source", source), createRuleTaxonomyDeleteButton("source", source));

  form.append(input, view);
  return form;
}

function createRuleFilterChip(tag) {
  const chip = document.createElement("span");
  chip.className = "rule-filter-chip";
  chip.dataset.ruleFilterChip = tag;

  const includeButton = document.createElement("button");
  includeButton.type = "button";
  includeButton.dataset.ruleIncludeTag = tag;
  includeButton.setAttribute("aria-label", `Показать категорию ${tag}`);
  includeButton.textContent = tag;

  const excludeButton = document.createElement("button");
  excludeButton.type = "button";
  excludeButton.dataset.ruleExcludeTag = tag;
  excludeButton.setAttribute("aria-label", `Исключить категорию ${tag}`);
  excludeButton.textContent = "−";

  chip.append(includeButton, excludeButton);
  return chip;
}

function createRuleOrderModalItem(tag) {
  const item = document.createElement("div");
  item.className = "rule-order-item";
  item.draggable = true;
  item.dataset.ruleOrderModalItem = "";
  item.dataset.ruleTag = tag;

  const number = document.createElement("span");
  number.className = "rule-order-number";
  number.dataset.ruleOrderNumber = "";

  const handle = document.createElement("span");
  handle.className = "tag-drag-handle";
  handle.setAttribute("aria-hidden", "true");
  handle.textContent = "↕";

  const title = document.createElement("strong");
  title.textContent = tag;

  item.append(number, handle, title);
  return item;
}

function createRuleSourceOrderModalItem(source) {
  const item = document.createElement("div");
  item.className = "rule-order-item";
  item.draggable = true;
  item.dataset.ruleSourceOrderModalItem = "";
  item.dataset.ruleSource = source;

  const number = document.createElement("span");
  number.className = "rule-order-number";
  number.dataset.ruleOrderNumber = "";

  const handle = document.createElement("span");
  handle.className = "tag-drag-handle";
  handle.setAttribute("aria-hidden", "true");
  handle.textContent = "↕";

  const title = document.createElement("strong");
  title.textContent = source;

  item.append(number, handle, title);
  return item;
}

function createEmptyRuleGroup(tag) {
  const group = document.createElement("details");
  group.className = "rules-group";
  group.dataset.ruleGroup = "";
  group.dataset.ruleTag = tag;
  group.open = true;

  const summary = document.createElement("summary");
  const title = document.createElement("span");
  title.textContent = tag;
  const counter = document.createElement("em");
  counter.textContent = "0";
  summary.append(title, counter);

  const empty = document.createElement("div");
  empty.className = "empty-state rules-empty";
  const strong = document.createElement("strong");
  strong.textContent = "В этой категории пока нет правил.";
  const hint = document.createElement("span");
  hint.textContent = `Добавьте новое правило и выберите тег «${tag}».`;
  empty.append(strong, hint);

  group.append(summary, empty);
  return group;
}

function getRuleGroup(tag) {
  return document.querySelector(`[data-rule-group][data-rule-tag="${CSS.escape(tag)}"]`);
}

function getOrCreateRuleGroup(tag) {
  let group = getRuleGroup(tag);
  if (!group) {
    group = createEmptyRuleGroup(tag);
    rulesGroups?.appendChild(group);
  }
  return group;
}

function getRuleGroupGrid(group) {
  group.querySelector(".rules-empty")?.remove();
  let grid = group.querySelector(".rules-card-grid");
  if (!grid) {
    grid = document.createElement("div");
    grid.className = "rules-card-grid";
    group.appendChild(grid);
  }
  return grid;
}

function createRuleCardShell(rule) {
  const shell = document.createElement("article");
  shell.className = "rule-card-shell";
  shell.dataset.searchCard = "";
  shell.dataset.title = rule.title || "";
  shell.dataset.description = rule.content || "";
  shell.dataset.terms = `${rule.tag || ""} ${rule.source || ""}`;

  const card = document.createElement("button");
  card.className = "rule-card";
  card.type = "button";
  card.dataset.openRuleModal = rule.id || "";
  card.dataset.ruleCard = rule.id || "";
  card.title = "Клик: открыть правило. Ctrl + клик: открыть с редактированием.";

  const main = document.createElement("span");
  main.className = "rule-card-main";
  const title = document.createElement("strong");
  title.dataset.ruleCardTitle = "";
  title.textContent = rule.title || "";
  const tag = document.createElement("small");
  tag.dataset.ruleCardTag = "";
  tag.textContent = rule.tag || "";
  main.append(title, tag);

  const source = document.createElement("span");
  source.className = "rule-source-badge";
  source.dataset.ruleCardSource = "";
  source.textContent = rule.source || "";

  card.append(main, source);
  shell.appendChild(card);

  if (document.querySelector("[data-demo-open]")) {
    const demoButton = document.createElement("button");
    demoButton.className = "rule-demo-button";
    demoButton.type = "button";
    demoButton.dataset.demoShow = "";
    demoButton.dataset.demoKind = "rule";
    demoButton.dataset.demoId = rule.id || "";
    demoButton.setAttribute("aria-label", `Показать правило ${rule.title || ""} на экране демонстрации`);
    demoButton.title = "Показать игрокам";
    const icon = document.createElement("span");
    icon.className = "demo-monitor-icon";
    icon.setAttribute("aria-hidden", "true");
    demoButton.appendChild(icon);
    shell.appendChild(demoButton);
  }

  return shell;
}

function createRuleSearchRow(rule) {
  const row = document.createElement("button");
  row.className = "result-row result-row-button";
  row.type = "button";
  row.dataset.ruleSearchRow = "";
  row.dataset.openRuleModal = rule.id || "";
  row.dataset.title = rule.title || "";
  row.hidden = true;
  row.style.display = "none";

  const icon = document.createElement("span");
  icon.className = "card-icon icon-book";
  icon.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = rule.title || "";
  const meta = document.createElement("small");
  meta.textContent = `${rule.tag || ""} · ${rule.source || ""}`;
  copy.append(title, meta);
  row.append(icon, copy);
  return row;
}

function getRuleCardButton(ruleId) {
  if (!ruleId) return null;
  return document.querySelector(`[data-rule-card="${CSS.escape(ruleId)}"]`);
}

function getRuleCardShellFromButton(card) {
  return card?.closest("[data-search-card], .rule-card-shell") || null;
}

function getRuleCardShell(ruleId) {
  return getRuleCardShellFromButton(getRuleCardButton(ruleId));
}

function updateRuleSearchRow(rule) {
  if (!rule?.id) return;
  const row = document.querySelector(`[data-rule-search-row][data-open-rule-modal="${CSS.escape(rule.id)}"]`);
  if (!row) return;
  row.dataset.title = rule.title || "";
  const title = row.querySelector("strong");
  const meta = row.querySelector("small");
  if (title) title.textContent = rule.title || "";
  if (meta) meta.textContent = `${rule.tag || ""} · ${rule.source || ""}`;
  if (ruleSearchModal?.classList.contains("is-open") && ruleSearchInput) {
    filterRuleSearch(ruleSearchInput.value || "");
  }
}

function updateRuleGroupCounter(group) {
  const counter = group?.querySelector("summary em");
  if (!counter) return;
  counter.textContent = String(group.querySelectorAll(".rule-card").length);
}

function removeRuleGroupIfEmpty(group) {
  if (!group || group.querySelector(".rule-card")) return;
  group.remove();
}

function setRuleCardTag(ruleId, tag) {
  const card = getRuleCardButton(ruleId);
  const shell = getRuleCardShellFromButton(card);
  const tagLabel = card?.querySelector(".rule-card-main small");
  if (tagLabel) tagLabel.textContent = tag;
  if (shell) {
    shell.dataset.terms = `${tag} ${card?.querySelector(".rule-source-badge")?.textContent || ""}`;
  }

  const modal = document.querySelector(`[data-rule-modal][data-loaded-rule-id="${CSS.escape(ruleId)}"]`);
  const kicker = modal?.querySelector("[data-rule-modal-tag]");
  const select = modal?.querySelector('select[name="tag"]');
  if (kicker) kicker.textContent = tag;
  if (select) select.value = tag;

  const row = document.querySelector(`[data-rule-search-row][data-open-rule-modal="${CSS.escape(ruleId)}"]`);
  const meta = row?.querySelector("small");
  if (meta) meta.textContent = `${tag} · ${card?.querySelector(".rule-source-badge")?.textContent || ""}`;
}

function setRuleCardSource(ruleId, source) {
  const card = getRuleCardButton(ruleId);
  const shell = getRuleCardShellFromButton(card);
  const sourceBadge = card?.querySelector("[data-rule-card-source], .rule-source-badge");
  if (sourceBadge) sourceBadge.textContent = source;
  if (shell) {
    shell.dataset.terms = `${card?.querySelector(".rule-card-main small")?.textContent || ""} ${source}`;
  }

  const modal = document.querySelector(`[data-rule-modal][data-loaded-rule-id="${CSS.escape(ruleId)}"]`);
  const modalBadge = modal?.querySelector("[data-rule-modal-source], .rule-meta-line .rule-source-badge");
  const select = modal?.querySelector('select[name="source"]');
  if (modalBadge) modalBadge.textContent = source;
  if (select) select.value = source;

  const row = document.querySelector(`[data-rule-search-row][data-open-rule-modal="${CSS.escape(ruleId)}"]`);
  const meta = row?.querySelector("small");
  if (meta) meta.textContent = `${card?.querySelector(".rule-card-main small")?.textContent || ""} · ${source}`;
}

function updateRuleAfterSave(rule) {
  if (!rule?.id) return;
  const card = getRuleCardButton(rule.id);
  const shell = getRuleCardShellFromButton(card);
  if (card) {
    const oldGroup = card.closest("[data-rule-group]");
    const oldTag = oldGroup?.dataset.ruleTag || "";
    if (rule.tag && normalizeRuleTag(rule.tag) !== normalizeRuleTag(oldTag)) {
      const targetGroup = getOrCreateRuleGroup(rule.tag);
      const movable = shell || card;
      getRuleGroupGrid(targetGroup)?.appendChild(movable);
      updateRuleGroupCounter(targetGroup);
      syncRuleGroupFilterState(targetGroup);
      if (oldGroup) {
        updateRuleGroupCounter(oldGroup);
        syncRuleGroupFilterState(oldGroup);
        removeRuleGroupIfEmpty(oldGroup);
      }
    }
    const dataNode = shell || card;
    dataNode.dataset.title = rule.title || "";
    dataNode.dataset.description = rule.content || "";
    dataNode.dataset.terms = `${rule.tag || ""} ${rule.source || ""}`;
    const title = card.querySelector("[data-rule-card-title], strong");
    const tag = card.querySelector("[data-rule-card-tag], .rule-card-main small");
    const source = card.querySelector("[data-rule-card-source], .rule-source-badge");
    if (title) title.textContent = rule.title || "";
    if (tag) tag.textContent = rule.tag || "";
    if (source) source.textContent = rule.source || "";
  }
  updateRuleSearchRow(rule);

  const modal = document.querySelector(`[data-rule-modal][data-loaded-rule-id="${CSS.escape(rule.id)}"]`);
  if (!modal) return;
  const title = modal.querySelector("[data-rule-modal-title]");
  const tag = modal.querySelector("[data-rule-modal-tag]");
  const source = modal.querySelector("[data-rule-modal-source]");
  const page = modal.querySelector("[data-rule-modal-page]");
  const book = modal.querySelector("[data-rule-modal-book]");
  const content = modal.querySelector("[data-rule-content]");
  const deleteForm = modal.querySelector("[data-rule-delete-form]");
  const favoriteButton = modal.querySelector("[data-favorite-toggle][data-favorite-type='rule']");
  if (title) title.textContent = rule.title || "";
  if (tag) tag.textContent = rule.tag || "";
  if (source) source.textContent = rule.source || "";
  if (page) {
    page.textContent = rule.page ? `стр. ${rule.page}` : "";
    page.hidden = !rule.page;
  }
  if (book) {
    book.href = rule.book_url || "#";
    book.hidden = !rule.book_url;
  }
  if (content && rule.content_html !== undefined) {
    content.innerHTML = rule.content_html;
    normalizeRuleModalContent(content);
  }
  if (favoriteButton) {
    favoriteButton.dataset.favoriteId = rule.id || "";
    favoriteButton.dataset.favoriteTitle = rule.title || "";
    favoriteButton.setAttribute("aria-label", `Добавить правило ${rule.title || ""} в избранное`);
    if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
  }
  if (deleteForm) deleteForm.dataset.ruleTitle = rule.title || "";
}

function removeRuleFromPage(ruleId) {
  const card = getRuleCardButton(ruleId);
  const shell = getRuleCardShellFromButton(card);
  const group = card?.closest("[data-rule-group]");
  const modal = document.querySelector(`[data-rule-modal][data-loaded-rule-id="${CSS.escape(ruleId)}"]`);
  (shell || card)?.remove();
  modal?.remove();
  if (group) {
    updateRuleGroupCounter(group);
    removeRuleGroupIfEmpty(group);
  }
  updateRuleCategoryFilters();
}

function moveDeletedTagRulesToService(deletedTag, movedRuleIds = []) {
  const sourceGroup = getRuleGroup(deletedTag);
  const serviceGroup = getOrCreateRuleGroup(serviceRuleTag);
  const serviceGrid = getRuleGroupGrid(serviceGroup);
  const cards = movedRuleIds.length
    ? movedRuleIds.map((ruleId) => getRuleCardButton(ruleId)).filter(Boolean)
    : [...(sourceGroup?.querySelectorAll(".rule-card") || [])];

  cards.forEach((card) => {
    const ruleId = card.dataset.openRuleModal;
    const modal = ruleId ? document.querySelector(`[data-rule-modal][data-loaded-rule-id="${CSS.escape(ruleId)}"]`) : null;
    serviceGrid.appendChild(getRuleCardShellFromButton(card) || card);
    if (ruleId) setRuleCardTag(ruleId, serviceRuleTag);
  });

  updateRuleGroupCounter(serviceGroup);
  removeRuleGroupIfEmpty(sourceGroup);
  updateRuleCategoryFilters();
}

function addRuleTagToPage(tag) {
  if (!tag || ruleTagAlreadyExists(tag)) return;

  document.querySelector("[data-rule-tag-order-list]")?.appendChild(createRuleTagDeleteForm(tag));
  document.querySelector("[data-rule-filters]")?.appendChild(createRuleFilterChip(tag));
  ruleTagOrderModalList?.appendChild(createRuleOrderModalItem(tag));
  rulesGroups?.appendChild(createEmptyRuleGroup(tag));

  document.querySelectorAll('select[name="tag"]').forEach((select) => {
    const option = document.createElement("option");
    option.value = tag;
    option.textContent = tag;
    select.appendChild(option);
  });

  updateRuleOrderNumbers();
  updateRuleCategoryFilters();
}

function addRuleSourceToPage(source) {
  if (!source || ruleSourceAlreadyExists(source)) return;

  document.querySelector("[data-rule-source-order-list]")?.appendChild(createRuleSourceDeleteForm(source));
  ruleSourceOrderModalList?.appendChild(createRuleSourceOrderModalItem(source));

  document.querySelectorAll('select[name="source"]').forEach((select) => {
    const option = document.createElement("option");
    option.value = source;
    option.textContent = source;
    select.appendChild(option);
  });

  updateRuleOrderNumbers();
}

function addRuleToPage(rule) {
  if (!rule?.id) return;
  const group = getOrCreateRuleGroup(rule.tag || serviceRuleTag);
  const grid = getRuleGroupGrid(group);
  const shell = createRuleCardShell(rule);
  grid.appendChild(shell);
  updateRuleGroupCounter(group);

  document.querySelector("[data-rule-search-results]")?.prepend(createRuleSearchRow(rule));
  fillRuleModal(rule);
  updateRuleCategoryFilters();

  if (typeof shell.animate === "function") {
    shell.animate(
      [
        { opacity: 0, transform: "translateY(-8px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 220, easing: "ease-out" },
    );
  }
}

function openRuleTagOrderModal() {
  if (!ruleTagOrderModal) return;
  if (ruleTagOrderModal.parentElement !== document.body) {
    document.body.appendChild(ruleTagOrderModal);
  }
  ruleTagOrderModal.classList.add("is-open");
  ruleTagOrderModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  ruleTagOrderDirty = false;
  updateRuleOrderNumbers();
}

function openRuleSourceOrderModal() {
  if (!ruleSourceOrderModal) return;
  if (ruleSourceOrderModal.parentElement !== document.body) {
    document.body.appendChild(ruleSourceOrderModal);
  }
  ruleSourceOrderModal.classList.add("is-open");
  ruleSourceOrderModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  ruleSourceOrderDirty = false;
  updateRuleOrderNumbers();
}

function openRuleTaxonomyModal() {
  if (!ruleTaxonomyModal) return;
  if (ruleTaxonomyModal.parentElement !== document.body) {
    document.body.appendChild(ruleTaxonomyModal);
  }
  setRuleTaxonomyTab(ruleTaxonomyActiveTab);
  ruleTaxonomyModal.classList.add("is-open");
  ruleTaxonomyModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const toggle = document.querySelector("[data-toggle-rule-tags]");
  if (toggle) {
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
  }
  window.setTimeout(() => ruleTaxonomyModal.querySelector("input")?.focus(), 40);
}

function closeRuleTaxonomyModal() {
  if (!ruleTaxonomyModal) return;
  ruleTaxonomyModal.classList.remove("is-open");
  ruleTaxonomyModal.setAttribute("aria-hidden", "true");
  const toggle = document.querySelector("[data-toggle-rule-tags]");
  if (toggle) {
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  }
  syncRuleBodyModalState();
}

function openRuleTagRenameModal(form) {
  const tag = form?.dataset.ruleTag || "";
  if (!ruleTagRenameModal || !tag || normalizeRuleTag(tag) === normalizeRuleTag(serviceRuleTag)) return;
  if (ruleTagRenameModal.parentElement !== document.body) {
    document.body.appendChild(ruleTagRenameModal);
  }
  pendingRuleTagRenameForm = form;
  const title = ruleTagRenameModal.querySelector("[data-rule-tag-rename-title]");
  const input = ruleTagRenameModal.querySelector("[data-rule-tag-rename-input]");
  if (title) title.textContent = `Переименовать «${tag}»`;
  if (input) input.value = tag;
  ruleTagRenameModal.classList.add("is-open");
  ruleTagRenameModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeRuleTagRenameModal() {
  if (!ruleTagRenameModal) return;
  ruleTagRenameModal.classList.remove("is-open");
  ruleTagRenameModal.setAttribute("aria-hidden", "true");
  const input = ruleTagRenameModal.querySelector("[data-rule-tag-rename-input]");
  if (input) input.value = "";
  pendingRuleTagRenameForm = null;
  syncRuleBodyModalState();
}

function openRuleSourceRenameModal(form) {
  const source = form?.dataset.ruleSource || "";
  if (!ruleSourceRenameModal || !source) return;
  if (ruleSourceRenameModal.parentElement !== document.body) {
    document.body.appendChild(ruleSourceRenameModal);
  }
  pendingRuleSourceRenameForm = form;
  const title = ruleSourceRenameModal.querySelector("[data-rule-source-rename-title]");
  const input = ruleSourceRenameModal.querySelector("[data-rule-source-rename-input]");
  if (title) title.textContent = `Переименовать «${source}»`;
  if (input) input.value = source;
  ruleSourceRenameModal.classList.add("is-open");
  ruleSourceRenameModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeRuleSourceRenameModal() {
  if (!ruleSourceRenameModal) return;
  ruleSourceRenameModal.classList.remove("is-open");
  ruleSourceRenameModal.setAttribute("aria-hidden", "true");
  const input = ruleSourceRenameModal.querySelector("[data-rule-source-rename-input]");
  if (input) input.value = "";
  pendingRuleSourceRenameForm = null;
  syncRuleBodyModalState();
}

async function renameRuleTag() {
  const form = pendingRuleTagRenameForm;
  const oldTag = form?.dataset.ruleTag || "";
  const input = ruleTagRenameModal?.querySelector("[data-rule-tag-rename-input]");
  const newTag = (input?.value || "").trim();
  if (!oldTag || !newTag || normalizeRuleTag(oldTag) === normalizeRuleTag(newTag)) {
    closeRuleTagRenameModal();
    return;
  }
  const url = document.querySelector("[data-rule-tag-editor]")?.dataset.ruleTagRenameUrl || "/rules/tags/rename";
  const formData = new FormData();
  formData.append("tag", oldTag);
  formData.append("new_tag", newTag);
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      "X-Requested-With": "fetch",
    },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule tag was not renamed.");
  window.location.reload();
}

async function renameRuleSource() {
  const form = pendingRuleSourceRenameForm;
  const oldSource = form?.dataset.ruleSource || "";
  const input = ruleSourceRenameModal?.querySelector("[data-rule-source-rename-input]");
  const newSource = (input?.value || "").trim();
  if (!oldSource || !newSource || normalizeRuleTag(oldSource) === normalizeRuleTag(newSource)) {
    closeRuleSourceRenameModal();
    return;
  }
  const url = document.querySelector("[data-rule-tag-editor]")?.dataset.ruleSourceRenameUrl || "/rules/sources/rename";
  const formData = new FormData();
  formData.append("source", oldSource);
  formData.append("new_source", newSource);
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      "X-Requested-With": "fetch",
    },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule source was not renamed.");
  window.location.reload();
}

async function closeRuleTagOrderModal({ save = true, reload = false } = {}) {
  if (!ruleTagOrderModal) return;
  if (save && ruleTagOrderDirty) {
    try {
      await saveRuleTagOrder();
      ruleTagOrderDirty = false;
      if (reload) {
        window.location.reload();
        return;
      }
    } catch {
      window.alert("Не удалось сохранить порядок категорий. Попробуйте ещё раз.");
    }
  }
  ruleTagOrderModal.classList.remove("is-open");
  ruleTagOrderModal.setAttribute("aria-hidden", "true");
  syncRuleBodyModalState();
}

async function closeRuleSourceOrderModal({ save = true, reload = false } = {}) {
  if (!ruleSourceOrderModal) return;
  if (save && ruleSourceOrderDirty) {
    try {
      await saveRuleSourceOrder();
      ruleSourceOrderDirty = false;
      if (reload) {
        window.location.reload();
        return;
      }
    } catch {
      window.alert("Не удалось сохранить порядок источников. Попробуйте ещё раз.");
    }
  }
  ruleSourceOrderModal.classList.remove("is-open");
  ruleSourceOrderModal.setAttribute("aria-hidden", "true");
  syncRuleBodyModalState();
}

function openRuleTagDeleteModal(form) {
  const tag = form?.dataset.ruleTag || "";
  if (!ruleTagDeleteModal || !tag || normalizeRuleTag(tag) === normalizeRuleTag(serviceRuleTag)) return;
  pendingRuleTagDeleteForm = form;
  const title = ruleTagDeleteModal.querySelector("[data-rule-tag-delete-title]");
  const message = ruleTagDeleteModal.querySelector("[data-rule-tag-delete-message]");
  if (title) title.textContent = `Удалить «${tag}»?`;
  if (message) {
    message.textContent = `Правила из категории «${tag}» будут перенесены в сервисную категорию «${serviceRuleTag}». Это действие можно будет исправить вручную через карточки правил.`;
  }
  ruleTagDeleteModal.classList.add("is-open");
  ruleTagDeleteModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeRuleTagDeleteModal() {
  if (!ruleTagDeleteModal) return;
  ruleTagDeleteModal.classList.remove("is-open");
  ruleTagDeleteModal.setAttribute("aria-hidden", "true");
  pendingRuleTagDeleteForm = null;
  syncRuleBodyModalState();
}

function openRuleSourceDeleteModal(form) {
  const source = form?.dataset.ruleSource || "";
  if (!ruleSourceDeleteModal || !source) return;
  pendingRuleSourceDeleteForm = form;
  const title = ruleSourceDeleteModal.querySelector("[data-rule-source-delete-title]");
  const message = ruleSourceDeleteModal.querySelector("[data-rule-source-delete-message]");
  if (title) title.textContent = `Удалить «${source}»?`;
  if (message) {
    message.textContent = `Правила с источником «${source}» будут перенесены в первый доступный источник. Это действие можно будет исправить вручную через карточки правил.`;
  }
  ruleSourceDeleteModal.classList.add("is-open");
  ruleSourceDeleteModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeRuleSourceDeleteModal() {
  if (!ruleSourceDeleteModal) return;
  ruleSourceDeleteModal.classList.remove("is-open");
  ruleSourceDeleteModal.setAttribute("aria-hidden", "true");
  pendingRuleSourceDeleteForm = null;
  syncRuleBodyModalState();
}

function openRuleDeleteModal(form) {
  if (!ruleDeleteModal || !form) return;
  pendingRuleDeleteForm = form;
  const title = form.dataset.ruleTitle || "правило";
  const heading = ruleDeleteModal.querySelector("[data-rule-delete-title]");
  const message = ruleDeleteModal.querySelector("[data-rule-delete-message]");
  if (heading) heading.textContent = `Удалить «${title}»?`;
  if (message) message.textContent = "Правило будет удалено из глоссария. Это действие нельзя отменить.";
  ruleDeleteModal.classList.add("is-open");
  ruleDeleteModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeRuleDeleteModal() {
  if (!ruleDeleteModal) return;
  ruleDeleteModal.classList.remove("is-open");
  ruleDeleteModal.setAttribute("aria-hidden", "true");
  pendingRuleDeleteForm = null;
  syncRuleBodyModalState();
}

async function confirmRuleTagDelete() {
  if (!pendingRuleTagDeleteForm) return;
  const form = pendingRuleTagDeleteForm;
  const tag = form.dataset.ruleTag || "";
  const button = ruleTagDeleteModal?.querySelector("[data-confirm-rule-tag-delete-action]");
  if (button) button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule tag was not deleted.");

    form.remove();
    document.querySelector(`[data-rule-filter-chip="${CSS.escape(tag)}"]`)?.remove();
    document.querySelector(`[data-rule-order-modal-item][data-rule-tag="${CSS.escape(tag)}"]`)?.remove();
    document.querySelectorAll('select[name="tag"]').forEach((select) => {
      const option = [...select.options].find((item) => normalizeRuleTag(item.value) === normalizeRuleTag(tag));
      option?.remove();
      if (normalizeRuleTag(select.value) === normalizeRuleTag(tag)) select.value = payload.fallback || serviceRuleTag;
    });

    includedRuleTags.delete(normalizeRuleTag(tag));
    excludedRuleTags.delete(normalizeRuleTag(tag));
    moveDeletedTagRulesToService(tag, payload.moved_rule_ids || []);
    updateRuleOrderNumbers();
    closeRuleTagDeleteModal();
  } catch {
    window.alert("Не удалось удалить категорию. Попробуйте ещё раз.");
  } finally {
    if (button) button.disabled = false;
  }
}

async function deleteRuleForm(form, button) {
  if (!form) return;
  if (button) button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule was not deleted.");
    const ruleId = payload.rule_id || form.action.split("/").filter(Boolean).at(-2);
    closeRuleModals({ save: false });
    removeRuleFromPage(ruleId);
    showRuleToast("Правило удалено");
  } catch {
    showRuleToast("Не удалось удалить правило");
    if (button) button.disabled = false;
  }
}

function confirmRuleDelete() {
  if (!pendingRuleDeleteForm) return;
  deleteRuleForm(pendingRuleDeleteForm, ruleDeleteModal?.querySelector("[data-confirm-rule-delete-action]"));
}

async function saveRuleEditForm(form) {
  const submitButton = form?.querySelector('button[type="submit"]');
  if (!form) return;
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule was not saved.");
    updateRuleAfterSave(payload.rule);
    showRuleToast("Правило сохранено");
  } catch {
    showRuleToast("Не удалось сохранить правило");
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function resetHoldDeleteButton(button) {
  if (!button) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  const label = button.querySelector("[data-hold-delete-label]");
  if (label) label.textContent = "Удерживайте, чтобы удалить";
  if (typeof releaseHoldDeleteButtonSize === "function") releaseHoldDeleteButtonSize(button);
}

function cancelActiveRuleDeleteHold() {
  if (!activeRuleDeleteHold) return;
  window.clearTimeout(activeRuleDeleteHold.timeout);
  window.cancelAnimationFrame(activeRuleDeleteHold.frame);
  resetHoldDeleteButton(activeRuleDeleteHold.button);
  activeRuleDeleteHold = null;
}

function startRuleDeleteHold(button) {
  const form = button?.closest("[data-rule-delete-form]");
  if (!form || button.disabled) return;
  cancelActiveRuleDeleteHold();
  const duration = 1900;
  const startedAt = performance.now();
  const label = button.querySelector("[data-hold-delete-label]");
  if (typeof lockHoldDeleteButtonSize === "function") lockHoldDeleteButtonSize(button);
  button.classList.add("is-holding");
  if (label) label.textContent = "Держите...";

  const tick = () => {
    if (!activeRuleDeleteHold || activeRuleDeleteHold.button !== button) return;
    const progress = Math.min((performance.now() - startedAt) / duration, 1);
    button.style.setProperty("--hold-progress", String(progress));
    if (progress < 1) {
      activeRuleDeleteHold.frame = window.requestAnimationFrame(tick);
    }
  };

  activeRuleDeleteHold = {
    button,
    frame: window.requestAnimationFrame(tick),
    timeout: window.setTimeout(() => {
      activeRuleDeleteHold = null;
      button.classList.remove("is-holding");
      button.style.setProperty("--hold-progress", "1");
      if (label) label.textContent = "Удаляю...";
      deleteRuleForm(form, button);
    }, duration),
  };
}

async function confirmRuleSourceDelete() {
  if (!pendingRuleSourceDeleteForm) return;
  const form = pendingRuleSourceDeleteForm;
  const source = form.dataset.ruleSource || "";
  const button = ruleSourceDeleteModal?.querySelector("[data-confirm-rule-source-delete-action]");
  if (button) button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule source was not deleted.");

    form.remove();
    document.querySelector(`[data-rule-source-order-modal-item][data-rule-source="${CSS.escape(source)}"]`)?.remove();
    document.querySelectorAll('select[name="source"]').forEach((select) => {
      const option = [...select.options].find((item) => normalizeRuleTag(item.value) === normalizeRuleTag(source));
      option?.remove();
      if (payload.fallback && ![...select.options].some((item) => normalizeRuleTag(item.value) === normalizeRuleTag(payload.fallback))) {
        const fallbackOption = document.createElement("option");
        fallbackOption.value = payload.fallback;
        fallbackOption.textContent = payload.fallback;
        select.appendChild(fallbackOption);
      }
      if (normalizeRuleTag(select.value) === normalizeRuleTag(source)) select.value = payload.fallback || "";
    });

    (payload.moved_rule_ids || []).forEach((ruleId) => setRuleCardSource(ruleId, payload.fallback || ""));
    updateRuleOrderNumbers();
    closeRuleSourceDeleteModal();
  } catch {
    window.alert("Не удалось удалить источник. Попробуйте ещё раз.");
  } finally {
    if (button) button.disabled = false;
  }
}

function filterRuleSearch(query) {
  const normalizedQuery = query.trim().toLowerCase();
  let visibleCount = 0;
  document.querySelectorAll("[data-rule-search-row]").forEach((row) => {
    const title = (row.dataset.title || "").toLowerCase();
    const isVisible = normalizedQuery.length >= 3 && title.includes(normalizedQuery);
    row.hidden = !isVisible;
    row.style.display = isVisible ? "" : "none";
    if (isVisible) visibleCount += 1;
  });
  const emptyMessage = document.querySelector("[data-rule-search-empty]");
  if (emptyMessage) {
    emptyMessage.hidden = visibleCount > 0;
    emptyMessage.textContent = normalizedQuery.length < 3 ? "Введите минимум 3 символа." : "Нет данных.";
  }
}

function openRuleSearch() {
  if (!ruleSearchModal || !ruleSearchInput) return;
  ruleSearchModal.classList.add("is-open");
  ruleSearchModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  ruleSearchInput.value = "";
  filterRuleSearch("");
  window.setTimeout(() => ruleSearchInput.focus(), 30);
}

function closeRuleSearch() {
  if (!ruleSearchModal) return;
  ruleSearchModal.classList.remove("is-open");
  ruleSearchModal.setAttribute("aria-hidden", "true");
  syncRuleBodyModalState();
}

document.addEventListener("click", async (event) => {
  if (event.target.closest("[data-open-rule-search]")) {
    openRuleSearch();
    return;
  }

  if (event.target.closest("[data-close-rule-search]")) {
    closeRuleSearch();
    return;
  }

  const ruleButton = event.target.closest("[data-open-rule-modal]");
  if (ruleButton) {
    event.preventDefault();
    openRuleModal(ruleButton.dataset.openRuleModal, event.ctrlKey || event.metaKey);
    return;
  }

  if (event.target.closest("[data-close-rule-modal]")) {
    await closeRuleModals();
    return;
  }

  const tagToggle = event.target.closest("[data-toggle-rule-tags]");
  if (tagToggle) {
    if (ruleTaxonomyModal?.classList.contains("is-open")) closeRuleTaxonomyModal();
    else openRuleTaxonomyModal();
    return;
  }

  if (event.target.closest("[data-close-rule-taxonomy]")) {
    closeRuleTaxonomyModal();
    return;
  }

  const ruleTaxonomyTab = event.target.closest("[data-rule-taxonomy-tab]");
  if (ruleTaxonomyTab) {
    setRuleTaxonomyTab(ruleTaxonomyTab.dataset.ruleTaxonomyTab);
    return;
  }

  if (event.target.closest("[data-open-rule-tag-order]")) {
    openRuleTagOrderModal();
    return;
  }

  if (event.target.closest("[data-open-rule-source-order]")) {
    openRuleSourceOrderModal();
    return;
  }

  if (event.target.closest("[data-close-rule-tag-order]")) {
    closeRuleTagOrderModal();
    return;
  }

  if (event.target.closest("[data-close-rule-source-order]")) {
    closeRuleSourceOrderModal();
    return;
  }

  const renameRuleTagButton = event.target.closest("[data-open-rule-tag-rename]");
  if (renameRuleTagButton) {
    openRuleTagRenameModal(renameRuleTagButton.closest("[data-rule-tag-order-item]"));
    return;
  }

  const renameRuleSourceButton = event.target.closest("[data-open-rule-source-rename]");
  if (renameRuleSourceButton) {
    openRuleSourceRenameModal(renameRuleSourceButton.closest("[data-rule-source-order-item]"));
    return;
  }

  if (event.target.closest("[data-close-rule-tag-rename]")) {
    closeRuleTagRenameModal();
    return;
  }

  if (event.target.closest("[data-close-rule-source-rename]")) {
    closeRuleSourceRenameModal();
    return;
  }

  if (event.target.closest("[data-save-rule-tag-rename]")) {
    renameRuleTag().catch(() => showRuleToast("Не удалось переименовать категорию"));
    return;
  }

  if (event.target.closest("[data-save-rule-source-rename]")) {
    renameRuleSource().catch(() => showRuleToast("Не удалось переименовать источник"));
    return;
  }

  if (event.target.closest("[data-close-rule-tag-delete]")) {
    closeRuleTagDeleteModal();
    return;
  }

  if (event.target.closest("[data-close-rule-source-delete]")) {
    closeRuleSourceDeleteModal();
    return;
  }

  if (event.target.closest("[data-close-rule-delete]")) {
    closeRuleDeleteModal();
    return;
  }

  if (event.target.closest("[data-confirm-rule-tag-delete-action]")) {
    confirmRuleTagDelete();
    return;
  }

  if (event.target.closest("[data-confirm-rule-source-delete-action]")) {
    confirmRuleSourceDelete();
    return;
  }

  if (event.target.closest("[data-confirm-rule-delete-action]")) {
    confirmRuleDelete();
    return;
  }

  if (event.target.closest("[data-scroll-top-zone]")) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  if (event.target.closest("[data-save-rule-tag-order]")) {
    saveRuleTagOrder()
      .then(() => window.location.reload())
      .catch(() => window.alert("Не удалось сохранить порядок категорий. Попробуйте ещё раз."));
    return;
  }

  if (event.target.closest("[data-save-rule-source-order]")) {
    saveRuleSourceOrder()
      .then(() => window.location.reload())
      .catch(() => window.alert("Не удалось сохранить порядок источников. Попробуйте ещё раз."));
    return;
  }

  const includeTagButton = event.target.closest("[data-rule-include-tag]");
  if (includeTagButton) {
    const tag = normalizeRuleTag(includeTagButton.dataset.ruleIncludeTag);
    if (includedRuleTags.has(tag)) {
      includedRuleTags.delete(tag);
    } else {
      includedRuleTags.add(tag);
      excludedRuleTags.delete(tag);
    }
    updateRuleCategoryFilters();
    return;
  }

  const excludeTagButton = event.target.closest("[data-rule-exclude-tag]");
  if (excludeTagButton) {
    const tag = normalizeRuleTag(excludeTagButton.dataset.ruleExcludeTag);
    if (excludedRuleTags.has(tag)) {
      excludedRuleTags.delete(tag);
    } else {
      excludedRuleTags.add(tag);
      includedRuleTags.delete(tag);
    }
    updateRuleCategoryFilters();
    return;
  }

  if (event.target.closest("[data-rule-clear-filters]")) {
    includedRuleTags.clear();
    excludedRuleTags.clear();
    updateRuleCategoryFilters();
    return;
  }

  const deleteTagButton = event.target.closest("[data-confirm-rule-tag-delete]");
  if (deleteTagButton) {
    event.preventDefault();
    openRuleTagDeleteModal(deleteTagButton.closest("form"));
    return;
  }

  const deleteSourceButton = event.target.closest("[data-confirm-rule-source-delete]");
  if (deleteSourceButton) {
    event.preventDefault();
    openRuleSourceDeleteModal(deleteSourceButton.closest("form"));
    return;
  }

  const deleteRuleButton = event.target.closest("[data-open-rule-delete]");
  if (deleteRuleButton) {
    event.preventDefault();
    openRuleDeleteModal(deleteRuleButton.closest("form"));
    return;
  }
});

document.addEventListener("submit", (event) => {
  const createForm = event.target.closest(".rule-create-form");
  if (createForm) {
    event.preventDefault();
    createRuleFromForm(createForm);
    return;
  }

  const editForm = event.target.closest(".rule-edit-form");
  if (editForm) {
    event.preventDefault();
    saveRuleEditForm(editForm);
    return;
  }

  const deleteForm = event.target.closest("[data-rule-delete-form]");
  if (deleteForm) {
    event.preventDefault();
  }
});

async function createRuleFromForm(form) {
  const submitButton = form?.querySelector('button[type="submit"]');
  if (!form || !submitButton) return;
  const selectedTag = form.querySelector('select[name="tag"]')?.value || "";
  const selectedSource = form.querySelector('select[name="source"]')?.value || "";
  submitButton.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Rule was not created.");
    addRuleToPage(payload.rule);
    form.reset();
    const tagSelect = form.querySelector('select[name="tag"]');
    const sourceSelect = form.querySelector('select[name="source"]');
    if (tagSelect && selectedTag) tagSelect.value = selectedTag;
    if (sourceSelect && selectedSource) sourceSelect.value = selectedSource;
    showRuleToast("Правило добавлено");
  } catch {
    showRuleToast("Не удалось добавить правило");
  } finally {
    submitButton.disabled = false;
  }
}

document.addEventListener("pointerdown", (event) => {
  const button = event.target.closest("[data-hold-rule-delete]");
  if (!button) return;
  event.preventDefault();
  button.setPointerCapture?.(event.pointerId);
  startRuleDeleteHold(button);
});

["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    const button = event.target.closest?.("[data-hold-rule-delete]");
    if (!button || activeRuleDeleteHold?.button !== button) return;
    cancelActiveRuleDeleteHold();
  });
});

document.addEventListener("dragstart", (event) => {
  const tagItem = event.target.closest("[data-rule-order-modal-item]");
  const sourceItem = event.target.closest("[data-rule-source-order-modal-item]");
  if (!tagItem && !sourceItem) return;
  draggedRuleTagItem = tagItem;
  draggedRuleSourceItem = sourceItem;
  const item = tagItem || sourceItem;
  item?.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", item?.dataset.ruleTag || item?.dataset.ruleSource || "");
});

document.addEventListener("dragover", (event) => {
  const targetTagItem = event.target.closest("[data-rule-order-modal-item]");
  const targetSourceItem = event.target.closest("[data-rule-source-order-modal-item]");
  const targetItem = targetTagItem || targetSourceItem;
  const draggedItem = targetTagItem ? draggedRuleTagItem : draggedRuleSourceItem;
  if (!targetItem || !draggedItem || targetItem === draggedItem) return;
  event.preventDefault();

  const list = targetItem.closest("[data-rule-order-modal-list], [data-rule-source-order-modal-list]");
  if (!list) return;

  const targetRect = targetItem.getBoundingClientRect();
  const shouldPlaceAfter = event.clientY > targetRect.top + targetRect.height / 2;
  list.insertBefore(draggedItem, shouldPlaceAfter ? targetItem.nextSibling : targetItem);
  if (targetTagItem) ruleTagOrderDirty = true;
  if (targetSourceItem) ruleSourceOrderDirty = true;
  updateRuleOrderNumbers();
});

document.addEventListener("drop", (event) => {
  if (!draggedRuleTagItem && !draggedRuleSourceItem) return;
  event.preventDefault();
});

document.addEventListener("dragend", () => {
  draggedRuleTagItem?.classList.remove("is-dragging");
  draggedRuleSourceItem?.classList.remove("is-dragging");
  draggedRuleTagItem = null;
  draggedRuleSourceItem = null;
});

document.querySelector("[data-rule-tag-create-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const input = form.querySelector("[data-rule-tag-create-input]");
  const formData = new FormData(form);
  const tag = String(formData.get("tag") || "").trim();
  if (!tag) return;

  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    if (!response.ok) throw new Error("Rule tag was not created.");
    const payload = await response.json();
    if (payload.created) addRuleTagToPage(payload.tag || tag);
    if (input) input.value = "";
  } catch {
    window.alert("Не удалось создать категорию. Попробуйте ещё раз.");
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector("[data-rule-source-create-form]")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const input = form.querySelector("[data-rule-source-create-input]");
  const formData = new FormData(form);
  const source = String(formData.get("source") || "").trim();
  if (!source) return;

  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "fetch",
      },
    });
    if (!response.ok) throw new Error("Rule source was not created.");
    const payload = await response.json();
    if (payload.created) addRuleSourceToPage(payload.source || source);
    if (input) input.value = "";
  } catch {
    window.alert("Не удалось создать источник. Попробуйте ещё раз.");
  } finally {
    submitButton.disabled = false;
  }
});

ruleSearchInput?.addEventListener("input", (event) => {
  filterRuleSearch(event.target.value);
});

document.addEventListener("input", (event) => {
  const filterTagSearchInput = event.target.closest("[data-rule-filter-tag-search]");
  if (filterTagSearchInput) {
    filterRuleFilterTags(filterTagSearchInput);
  }

  const taxonomySearchInput = event.target.closest("[data-rule-taxonomy-search]");
  if (taxonomySearchInput) {
    filterRuleTaxonomyList(taxonomySearchInput);
  }
});

document.addEventListener("change", (event) => {
  const importInput = event.target.closest("[data-rule-import-input]");
  if (importInput) {
    const form = importInput.closest("[data-rule-import-form]");
    if (form && importInput.files?.length) form.submit();
  }
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-rule-filter-tag-search]")) {
    event.preventDefault();
    return;
  }

  if (event.key === "Enter" && event.target.closest("[data-rule-tag-rename-input]")) {
    event.preventDefault();
    await renameRuleTag().catch(() => showRuleToast("Не удалось переименовать категорию"));
    return;
  }

  if (event.key === "Enter" && event.target.closest("[data-rule-source-rename-input]")) {
    event.preventDefault();
    await renameRuleSource().catch(() => showRuleToast("Не удалось переименовать источник"));
    return;
  }

  if (event.key === "Escape" && ruleSearchModal?.classList.contains("is-open")) {
    closeRuleSearch();
    return;
  }

  if (event.key === "Escape") {
    closeRuleTagRenameModal();
    closeRuleSourceRenameModal();
    closeRuleTaxonomyModal();
    closeRuleTagOrderModal();
    closeRuleSourceOrderModal();
    closeRuleTagDeleteModal();
    closeRuleSourceDeleteModal();
    closeRuleDeleteModal();
    await closeRuleModals();
  }
});

window.addEventListener("scroll", () => {
  if (!scrollTopZone) return;
  const shouldShow = window.scrollY > 720;
  scrollTopZone.hidden = !shouldShow;
  scrollTopZone.classList.toggle("is-visible", shouldShow);
}, { passive: true });

const initialRuleId = new URLSearchParams(window.location.search).get("rule");
if (initialRuleId) {
  window.setTimeout(() => openRuleModal(initialRuleId, false), 40);
}

updateRuleCategoryFilters();
