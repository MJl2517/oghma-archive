let generatorsPage = document.querySelector("[data-generators-page]");
const generatorToast = document.querySelector("[data-generator-toast]");
let generatorSearchTimer = null;
let generatorRefreshToken = 0;
let activeGeneratorDeleteHold = null;
let activeGeneratorImportForm = null;
let generatorTaxonomyActiveTab = "tags";
let pendingGeneratorTaxonomyRename = null;

function showGeneratorToast(message) {
  if (!generatorToast) return;
  generatorToast.textContent = message;
  generatorToast.classList.add("is-visible");
  window.clearTimeout(showGeneratorToast.timer);
  showGeneratorToast.timer = window.setTimeout(() => generatorToast.classList.remove("is-visible"), 1800);
}

function normalizeGeneratorTag(tag) {
  return (tag || "").trim().toLocaleLowerCase("ru-RU");
}

function removeBodyGeneratorTaxonomyModals() {
  document.querySelectorAll("body > [data-generator-taxonomy-modal], body > [data-generator-taxonomy-rename-modal]").forEach((modal) => modal.remove());
}

function hasOpenGeneratorModal() {
  return !!document.querySelector(
    "[data-generator-modal].is-open, [data-generator-edit-modal].is-open, [data-generator-import-modal].is-open, [data-generator-taxonomy-modal].is-open, [data-generator-taxonomy-rename-modal].is-open"
  );
}

function syncGeneratorBodyModalState() {
  document.body.classList.toggle("has-modal", hasOpenGeneratorModal());
}

function getGeneratorTaxonomyModal() {
  const modal = document.querySelector("[data-generator-taxonomy-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function getGeneratorTaxonomyRenameModal() {
  const modal = document.querySelector("[data-generator-taxonomy-rename-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function setGeneratorTaxonomyTab(tabName = "tags") {
  generatorTaxonomyActiveTab = tabName === "categories" ? "categories" : "tags";
  const modal = getGeneratorTaxonomyModal();
  if (!modal) return;
  modal.querySelectorAll("[data-generator-taxonomy-tab]").forEach((tab) => {
    const isActive = tab.dataset.generatorTaxonomyTab === generatorTaxonomyActiveTab;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
    tab.tabIndex = isActive ? 0 : -1;
  });
  modal.querySelectorAll("[data-generator-taxonomy-pane]").forEach((pane) => {
    const isActive = pane.dataset.generatorTaxonomyPane === generatorTaxonomyActiveTab;
    pane.classList.toggle("is-active", isActive);
    pane.hidden = !isActive;
  });
}

function selectedGeneratorTags(input) {
  return (input?.value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function setGeneratorTags(input, tags) {
  const seen = new Set();
  const normalized = [];
  tags.forEach((tag) => {
    const clean = tag.trim();
    const key = normalizeGeneratorTag(clean);
    if (clean && !seen.has(key)) {
      seen.add(key);
      normalized.push(clean);
    }
  });
  if (input) input.value = normalized.join(", ");
}

function syncGeneratorTagPicker(picker) {
  const input = picker.closest("form")?.querySelector("[data-generator-tags-input]");
  const active = new Set(selectedGeneratorTags(input).map(normalizeGeneratorTag));
  picker.querySelectorAll("[data-generator-pick-tag]").forEach((button) => {
    button.classList.toggle("is-active", active.has(normalizeGeneratorTag(button.dataset.generatorPickTag)));
  });
}

function filterGeneratorFilterTags(searchInput) {
  const query = normalizeGeneratorTag(searchInput.value || "");
  document.querySelectorAll("[data-generator-filter-chip]").forEach((chip) => {
    const tag = normalizeGeneratorTag(chip.dataset.generatorFilterChip || chip.textContent || "");
    const visible = !query || tag.includes(query);
    chip.hidden = !visible;
    chip.style.display = visible ? "" : "none";
  });
}

function refreshGeneratorRangeHints(root = document) {
  root.querySelectorAll("[data-generator-form], [data-generator-edit-form]").forEach(updateGeneratorRangeHint);
}

function generatorDescriptionCollapsedHeight(description) {
  const styles = getComputedStyle(description);
  const variable = styles.getPropertyValue("--generator-description-collapsed-height").trim();
  if (variable.endsWith("rem")) {
    return Number.parseFloat(variable) * Number.parseFloat(getComputedStyle(document.documentElement).fontSize || "16");
  }
  if (variable.endsWith("px")) return Number.parseFloat(variable);
  const value = Number.parseFloat(variable);
  return Number.isFinite(value) && value > 20 ? value : 115;
}

function updateGeneratorDescriptionToggles(root = document) {
  root.querySelectorAll("[data-generator-description-wrap]").forEach((wrap) => {
    const description = wrap.querySelector("[data-generator-description]");
    const toggle = wrap.querySelector("[data-toggle-generator-description]");
    if (!description || !toggle) return;
    const collapsedHeight = generatorDescriptionCollapsedHeight(description);
    const isOverflowing = description.scrollHeight > collapsedHeight + 2;
    wrap.classList.toggle("is-toggleable", isOverflowing || wrap.classList.contains("is-expanded"));
    toggle.hidden = !isOverflowing && !wrap.classList.contains("is-expanded");
    description.style.maxHeight = wrap.classList.contains("is-expanded")
      ? `${description.scrollHeight}px`
      : `${collapsedHeight}px`;
  });
}

function setGeneratorDescriptionExpanded(wrap, isExpanded) {
  const description = wrap?.querySelector("[data-generator-description]");
  if (!wrap || !description) return;
  const collapsedHeight = generatorDescriptionCollapsedHeight(description);
  description.style.maxHeight = `${description.offsetHeight}px`;
  wrap.classList.toggle("is-expanded", isExpanded);
  window.requestAnimationFrame(() => {
    description.style.maxHeight = isExpanded ? `${description.scrollHeight}px` : `${collapsedHeight}px`;
  });
}

function parseGeneratorExpression(expression) {
  const compact = (expression || "").replace(/\s+/g, "").toLowerCase();
  if (!compact) throw new Error("empty");
  const parts = compact.match(/[+-]?[^+-]+/g) || [];
  if (parts.join("") !== compact) throw new Error("bad");
  let minimum = 0;
  let maximum = 0;
  let hasDice = false;

  parts.forEach((part) => {
    const sign = part.startsWith("-") ? -1 : 1;
    const clean = part.replace(/^[+-]/, "");
    const diceMatch = clean.match(/^(\d*)d(\d+)$/);
    if (diceMatch) {
      hasDice = true;
      const count = Math.max(1, Math.min(100, Number(diceMatch[1] || 1)));
      const sides = Math.max(2, Math.min(1000, Number(diceMatch[2])));
      const low = count;
      const high = count * sides;
      if (sign > 0) {
        minimum += low;
        maximum += high;
      } else {
        minimum -= high;
        maximum -= low;
      }
      return;
    }
    if (/^\d+$/.test(clean)) {
      const value = sign * Number(clean);
      minimum += value;
      maximum += value;
      return;
    }
    throw new Error("bad");
  });

  if (!hasDice) throw new Error("no-dice");
  return { minimum, maximum };
}

function updateGeneratorRangeHint(form) {
  const hint = form?.querySelector("[data-generator-range-hint]");
  const input = form?.querySelector('input[name="dice_expression"]');
  if (!hint || !input) return null;
  try {
    const bounds = parseGeneratorExpression(input.value);
    hint.textContent = `Рабочий диапазон: ${bounds.minimum}-${bounds.maximum}`;
    hint.classList.remove("is-invalid");
    return bounds;
  } catch {
    hint.textContent = "Рабочий диапазон: проверьте формулу";
    hint.classList.add("is-invalid");
    return null;
  }
}

function togglePickedGeneratorTag(button) {
  const form = button.closest("form");
  const input = form?.querySelector("[data-generator-tags-input]");
  if (!input) return;
  const tag = button.dataset.generatorPickTag;
  const current = selectedGeneratorTags(input);
  const hasTag = current.some((item) => normalizeGeneratorTag(item) === normalizeGeneratorTag(tag));
  setGeneratorTags(input, hasTag ? current.filter((item) => normalizeGeneratorTag(item) !== normalizeGeneratorTag(tag)) : [...current, tag]);
  syncGeneratorTagPicker(button.closest("[data-generator-tag-picker]"));
}

async function refreshGeneratorsPage(url, push = true) {
  const refreshToken = ++generatorRefreshToken;
  const activeInput = document.activeElement?.closest?.("[data-generator-search], [data-generator-filter-tag-search]");
  const activeSearch = activeInput
    ? {
        selector: activeInput.matches("[data-generator-search]") ? "[data-generator-search]" : "[data-generator-filter-tag-search]",
        value: activeInput.value,
        start: activeInput.selectionStart,
        end: activeInput.selectionEnd,
      }
    : null;
  const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
  if (!response.ok) throw new Error("Generators page was not loaded.");
  const html = await response.text();
  if (refreshToken !== generatorRefreshToken) return;
  const doc = new DOMParser().parseFromString(html, "text/html");
  const nextPage = doc.querySelector("[data-generators-page]");
  if (!nextPage || !generatorsPage) {
    window.location.href = url;
    return;
  }
  const latestSearch = activeSearch
    ? (() => {
        const liveInput = document.querySelector(activeSearch.selector);
        return liveInput
          ? {
              selector: activeSearch.selector,
              value: liveInput.value || "",
              start: liveInput.selectionStart ?? activeSearch.start,
              end: liveInput.selectionEnd ?? activeSearch.end,
            }
          : activeSearch;
      })()
    : null;
  removeBodyGeneratorTaxonomyModals();
  generatorsPage.replaceWith(nextPage);
  generatorsPage = nextPage;
  refreshGeneratorRangeHints(generatorsPage);
  updateGeneratorDescriptionToggles(generatorsPage);
  if (push) window.history.pushState({}, "", url);
  if (latestSearch) {
    const nextSearch = generatorsPage.querySelector(latestSearch.selector);
    if (nextSearch) {
      nextSearch.value = latestSearch.value;
      if (latestSearch.selector === "[data-generator-filter-tag-search]") {
        filterGeneratorFilterTags(nextSearch);
      }
      nextSearch.focus();
      nextSearch.setSelectionRange(latestSearch.start ?? latestSearch.value.length, latestSearch.end ?? latestSearch.value.length);
    }
  }
}

function generatorFilterUrlFromState({ tagAction = null, tag = "", page = 1 } = {}) {
  const form = document.querySelector("[data-generator-filter-form]");
  const url = new URL(form?.action || window.location.href, window.location.origin);
  const query = form?.querySelector("[data-generator-search]")?.value.trim() || "";
  const category = document.querySelector("[data-generator-category-filter]")?.value || "";
  const sort = document.querySelector("[data-generator-sort-filter]")?.value || "";
  const perPage = document.querySelector("[data-generator-per-page-filter]")?.value || form?.querySelector('input[name="per_page"]')?.value || "";
  const included = new Set([...document.querySelectorAll("[data-generator-filter-chip].is-included")].map((chip) => chip.dataset.generatorFilterChip));
  const excluded = new Set([...document.querySelectorAll("[data-generator-filter-chip].is-excluded")].map((chip) => chip.dataset.generatorFilterChip));

  if (tagAction === "include") {
    if (included.has(tag)) included.delete(tag);
    else {
      included.add(tag);
      excluded.delete(tag);
    }
  }
  if (tagAction === "exclude") {
    if (excluded.has(tag)) excluded.delete(tag);
    else {
      excluded.add(tag);
      included.delete(tag);
    }
  }

  if (query) url.searchParams.set("q", query);
  if (category) url.searchParams.set("category", category);
  if (sort && sort !== "title") url.searchParams.set("sort", sort);
  if (perPage) url.searchParams.set("per_page", perPage);
  if (page > 1) url.searchParams.set("page", String(page));
  [...included].forEach((item) => url.searchParams.append("tag", item));
  [...excluded].forEach((item) => url.searchParams.append("exclude_tag", item));
  return url.toString();
}

function openGeneratorModal() {
  const modal = document.querySelector("[data-generator-modal]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  updateGeneratorRangeHint(modal.querySelector("[data-generator-form]"));
  window.setTimeout(() => modal.querySelector('input[name="title"]')?.focus(), 30);
}

function closeGeneratorModal() {
  const modal = document.querySelector("[data-generator-modal]");
  if (!modal) return;
  closeGeneratorImportModal();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  syncGeneratorBodyModalState();
}

async function openGeneratorEditModal(generatorId) {
  closeGeneratorModal();
  closeGeneratorEditModals(false);
  let modal = null;
  const opener = document.querySelector(`[data-open-generator-edit-modal="${CSS.escape(generatorId)}"]`);
  const url = opener?.dataset.generatorEditUrl;
  const root = document.querySelector("[data-generator-edit-modal-root]");
  if (!url || !root) return;
  try {
    const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    if (!response.ok) throw new Error("Edit modal was not loaded.");
    root.innerHTML = await response.text();
    modal = root.querySelector(`[data-generator-edit-modal="${CSS.escape(generatorId)}"]`);
    refreshGeneratorRangeHints(root);
  } catch {
    showGeneratorToast("Не удалось открыть редактирование");
    return;
  }
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  updateGeneratorRangeHint(modal.querySelector("[data-generator-edit-form]"));
}

function closeGeneratorEditModals() {
  closeGeneratorImportModal();
  document.querySelectorAll("[data-generator-edit-modal]").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  syncGeneratorBodyModalState();
}

function openGeneratorTaxonomyModal() {
  const modal = getGeneratorTaxonomyModal();
  if (!modal) return;
  setGeneratorTaxonomyTab(generatorTaxonomyActiveTab);
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const toggle = document.querySelector("[data-toggle-generator-taxonomy]");
  if (toggle) {
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
  }
  window.setTimeout(() => modal.querySelector("[data-generator-taxonomy-pane].is-active input")?.focus(), 40);
}

function closeGeneratorTaxonomyModal() {
  const modal = document.querySelector("[data-generator-taxonomy-modal]");
  if (!modal) return;
  closeGeneratorTaxonomyRenameModal();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const toggle = document.querySelector("[data-toggle-generator-taxonomy]");
  if (toggle) {
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  }
  syncGeneratorBodyModalState();
}

function openGeneratorTaxonomyRename(kind, form) {
  const modal = getGeneratorTaxonomyRenameModal();
  const oldValue = kind === "category" ? form?.dataset.generatorCategory || "" : form?.dataset.generatorTag || "";
  if (!modal || !oldValue) return;
  pendingGeneratorTaxonomyRename = { kind, form };
  const label = kind === "category" ? "категорию" : "тег";
  const kicker = modal.querySelector("[data-generator-taxonomy-rename-kicker]");
  const title = modal.querySelector("[data-generator-taxonomy-rename-title]");
  const input = modal.querySelector("[data-generator-taxonomy-rename-input]");
  if (kicker) kicker.textContent = kind === "category" ? "Переименование категории" : "Переименование тега";
  if (title) title.textContent = `Переименовать ${label} «${oldValue}»`;
  if (input) input.value = oldValue;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeGeneratorTaxonomyRenameModal() {
  const modal = document.querySelector("[data-generator-taxonomy-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const input = modal.querySelector("[data-generator-taxonomy-rename-input]");
  if (input) input.value = "";
  pendingGeneratorTaxonomyRename = null;
  syncGeneratorBodyModalState();
}

async function renameGeneratorTaxonomy() {
  const pending = pendingGeneratorTaxonomyRename;
  if (!pending?.form) return;
  const modal = document.querySelector("[data-generator-taxonomy-rename-modal]");
  const input = modal?.querySelector("[data-generator-taxonomy-rename-input]");
  const cleanValue = (input?.value || "").trim();
  const editor = document.querySelector("[data-generator-taxonomy]");
  const isCategory = pending.kind === "category";
  const oldValue = isCategory ? pending.form.dataset.generatorCategory || "" : pending.form.dataset.generatorTag || "";
  if (!oldValue || !cleanValue || normalizeGeneratorTag(oldValue) === normalizeGeneratorTag(cleanValue)) {
    closeGeneratorTaxonomyRenameModal();
    return;
  }
  const url = isCategory ? editor?.dataset.generatorCategoryRenameUrl : editor?.dataset.generatorTagRenameUrl;
  if (!url) return;
  const formData = new FormData();
  formData.append(isCategory ? "category" : "tag", oldValue);
  formData.append(isCategory ? "new_category" : "new_tag", cleanValue);
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Generator taxonomy was not renamed.");
  generatorTaxonomyActiveTab = isCategory ? "categories" : "tags";
  await refreshGeneratorsPage(window.location.href, false);
  closeGeneratorTaxonomyRenameModal();
  showGeneratorToast(isCategory ? "Категория переименована" : "Тег переименован");
  openGeneratorTaxonomyModal();
}

function clearGeneratorErrors(form) {
  form.querySelectorAll(".has-generator-error").forEach((element) => element.classList.remove("has-generator-error"));
  form.querySelectorAll("[data-generator-inline-error]").forEach((element) => element.remove());
}

function appendGeneratorError(target, message) {
  if (!target) return;
  target.classList.add("has-generator-error");
  const error = document.createElement("small");
  error.className = "generator-inline-error";
  error.dataset.generatorInlineError = "true";
  error.textContent = message;
  target.appendChild(error);
}

function generatorRowByNumber(form, number) {
  const rows = [...form.querySelectorAll("[data-generator-edit-row]")];
  return rows[Math.max(0, Number(number) - 1)] || null;
}

function showFormErrors(form, errors) {
  clearGeneratorErrors(form);
  (errors || []).forEach((message) => {
    const rowMatch = String(message).match(/Строка\s+(\d+):\s*(.+)/i);
    if (rowMatch) {
      const row = generatorRowByNumber(form, rowMatch[1]);
      const text = rowMatch[2];
      const target = /результат/i.test(text)
        ? row?.querySelector(".generator-result-field")
        : row?.querySelector(".generator-range-field");
      appendGeneratorError(target || row, text);
      return;
    }

    if (/формул|куб|гран/i.test(message)) {
      appendGeneratorError(form.querySelector('input[name="dice_expression"]')?.closest("label"), message);
      return;
    }

    appendGeneratorError(form.querySelector(".generator-table-shell") || form.querySelector("[data-generator-rows]"), message);
  });
}

async function submitGeneratorAjaxForm(form, message = "") {
  const response = await fetch(form.action, {
    method: form.method || "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
  });
  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok) {
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      showFormErrors(form, payload.errors || [payload.error || "Не удалось сохранить генератор."]);
    }
    throw new Error("Generator form failed.");
  }
  clearGeneratorErrors(form);
  await refreshGeneratorsPage(window.location.href, false);
  if (message) showGeneratorToast(message);
}

async function importGeneratorFile(input) {
  const form = input.closest("[data-generator-import-file-form]");
  if (!form || !input.files?.length) return;
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
  });
  const payload = await response.json().catch(() => ({}));
  input.value = "";
  if (!response.ok || !payload.ok) {
    const detail = Array.isArray(payload.errors) && payload.errors.length ? ` ${payload.errors[0]}` : "";
    showGeneratorToast(`Не удалось импортировать генераторы.${detail}`);
    return;
  }
  await refreshGeneratorsPage(window.location.href, false);
  showGeneratorToast(`Импорт: ${payload.created} новых, ${payload.updated} обновлено`);
}

function addGeneratorRow(button, values = {}, options = {}) {
  const form = button.dataset.generatorActionForm
    ? document.getElementById(button.dataset.generatorActionForm)
    : button.closest("form");
  const list = form?.querySelector("[data-generator-rows]");
  const template = document.querySelector("[data-generator-row-template]");
  if (!list || !template) return;
  const row = template.content.firstElementChild.cloneNode(true);
  const min = values.min ?? "";
  const max = values.max ?? "";
  row.querySelector('input[name="row_range"]').value = min && max && min !== max ? `${min}-${max}` : (min || max || "");
  row.querySelector('textarea[name="row_result"]').value = values.result ?? "";
  list.appendChild(row);
  if (options.focus !== false) row.querySelector('input[name="row_range"]')?.focus();
}

function resetCreateGeneratorForm(form) {
  if (!form) return;
  form.reset();
  clearGeneratorErrors(form);
  const tagsInput = form.querySelector("[data-generator-tags-input]");
  if (tagsInput) tagsInput.value = "";
  form.querySelectorAll("[data-generator-pick-tag]").forEach((button) => button.classList.remove("is-active"));
  const rows = [...form.querySelectorAll("[data-generator-edit-row]")];
  rows.forEach((row, index) => {
    if (index === 0) {
      row.querySelector('input[name="row_id"]').value = "";
      row.querySelector('input[name="row_range"]').value = "";
      row.querySelector('textarea[name="row_result"]').value = "";
    } else {
      row.remove();
    }
  });
  updateGeneratorRangeHint(form);
}

function splitMarkdownTableRow(line) {
  const trimmed = (line || "").trim();
  if (!trimmed.includes("|")) return [];
  const source = trimmed.startsWith("|") ? trimmed.slice(1) : trimmed;
  const withoutTail = source.endsWith("|") ? source.slice(0, -1) : source;
  const cells = [];
  let cell = "";
  let escaped = false;
  for (const char of withoutTail) {
    if (escaped) {
      cell += char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      cell += char;
      escaped = true;
      continue;
    }
    if (char === "|") {
      cells.push(cell.trim());
      cell = "";
      continue;
    }
    cell += char;
  }
  cells.push(cell.trim());
  return cells;
}

function isMarkdownSeparatorRow(cells) {
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test((cell || "").trim()));
}

function parseGeneratorMarkdownRange(value) {
  const normalized = String(value || "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/[`*_]/g, "")
    .replace(/[–—−]/g, "-")
    .trim();
  const rangeMatch = normalized.match(/^\s*(\d+)\s*(?:-|\.{2,}|…|до)\s*(\d+)\s*$/i);
  if (rangeMatch) {
    const min = Number(rangeMatch[1]);
    const max = rangeMatch[2] === "00" && min > 0 ? 100 : Number(rangeMatch[2]);
    if (Number.isInteger(min) && Number.isInteger(max) && min <= max) return { min, max };
  }
  const singleMatch = normalized.match(/^\s*(\d+)\s*$/);
  if (singleMatch) {
    const valueNumber = singleMatch[1] === "00" ? 100 : Number(singleMatch[1]);
    if (Number.isInteger(valueNumber)) return { min: valueNumber, max: valueNumber };
  }
  return null;
}

function diceExpressionFromMarkdownHeader(header, rows) {
  const headerText = String(header || "").replace(/\s+/g, "").toLowerCase();
  const diceMatch = headerText.match(/^(\d*)[dдк](\d+)$/i);
  if (diceMatch) return `${diceMatch[1] || 1}d${diceMatch[2]}`;
  const maximum = rows.reduce((value, row) => Math.max(value, row.max), 0);
  const minimum = rows.reduce((value, row) => Math.min(value, row.min), Number.POSITIVE_INFINITY);
  return minimum === 1 && maximum > 1 ? `1d${maximum}` : "";
}

function parseGeneratorMarkdownTable(markdown) {
  const tableRows = String(markdown || "")
    .split(/\r?\n/)
    .map((line) => splitMarkdownTableRow(line))
    .filter((cells) => cells.length >= 2);
  if (tableRows.length < 2) throw new Error("table");
  const header = tableRows[0];
  const bodyRows = tableRows.slice(1).filter((cells) => !isMarkdownSeparatorRow(cells));
  const rows = bodyRows.map((cells) => {
    const range = parseGeneratorMarkdownRange(cells[0]);
    const result = cells.slice(1).join(" | ").trim();
    if (!range || !result) return null;
    return { ...range, result };
  });
  if (rows.some((row) => row === null) || rows.length === 0) throw new Error("rows");
  return {
    diceExpression: diceExpressionFromMarkdownHeader(header[0], rows),
    rows,
  };
}

function openGeneratorImportModal(button) {
  const form = button.dataset.generatorActionForm
    ? document.getElementById(button.dataset.generatorActionForm)
    : button.closest("form");
  const modal = document.querySelector("[data-generator-import-modal]");
  if (!form || !modal) return;
  activeGeneratorImportForm = form;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const textarea = modal.querySelector("[data-generator-markdown-table]");
  if (textarea) {
    textarea.value = "";
    window.setTimeout(() => textarea.focus(), 30);
  }
}

function closeGeneratorImportModal() {
  const modal = document.querySelector("[data-generator-import-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  modal.querySelector("[data-generator-markdown-table]")?.closest("label")?.classList.remove("has-generator-error");
  modal.querySelectorAll("[data-generator-inline-error]").forEach((element) => element.remove());
  activeGeneratorImportForm = null;
  syncGeneratorBodyModalState();
}

function importGeneratorMarkdownTable() {
  const form = activeGeneratorImportForm;
  const modal = document.querySelector("[data-generator-import-modal]");
  const textarea = modal?.querySelector("[data-generator-markdown-table]");
  if (!form || !modal || !textarea) return;
  clearGeneratorErrors(form);
  modal.querySelector("[data-generator-markdown-table]")?.closest("label")?.classList.remove("has-generator-error");
  modal.querySelectorAll("[data-generator-inline-error]").forEach((element) => element.remove());
  try {
    const parsed = parseGeneratorMarkdownTable(textarea?.value || "");
    clearGeneratorRows(form);
    const actionButton = form.querySelector("[data-add-generator-row]") || { dataset: {}, closest: () => form };
    parsed.rows.forEach((row) => addGeneratorRow(actionButton, row, { focus: false }));
    if (parsed.diceExpression) {
      const diceInput = form.querySelector('input[name="dice_expression"]');
      if (diceInput) diceInput.value = parsed.diceExpression;
    }
    updateGeneratorRangeHint(form);
    showGeneratorToast(`Импортировано строк: ${parsed.rows.length}`);
    closeGeneratorImportModal();
  } catch {
    appendGeneratorError(textarea.closest("label"), "Не удалось распознать markdown-таблицу. Нужны минимум две колонки: диапазон и результат.");
  }
}

function clearGeneratorRows(form) {
  form?.querySelectorAll("[data-generator-edit-row]").forEach((row) => row.remove());
}

function fillUnitGeneratorRanges(button) {
  const form = button.closest("form");
  const bounds = updateGeneratorRangeHint(form);
  if (!form || !bounds) {
    showGeneratorToast("Сначала укажите корректную формулу");
    return;
  }
  const count = bounds.maximum - bounds.minimum + 1;
  if (count > 120) {
    showGeneratorToast("Слишком много строк для автозаполнения");
    return;
  }
  clearGeneratorRows(form);
  for (let value = bounds.minimum; value <= bounds.maximum; value += 1) {
    addGeneratorRow(button, { min: value, max: value, result: "" });
  }
}

function openGeneratorPreset(expression) {
  const form = document.querySelector("[data-generator-form]");
  openGeneratorModal();
  resetCreateGeneratorForm(form);
  if (!form || !expression) return;
  const diceInput = form.querySelector('input[name="dice_expression"]');
  if (diceInput) diceInput.value = expression;
  updateGeneratorRangeHint(form);
  const fillButton = form.querySelector("[data-generator-fill-unit-ranges]");
  if (fillButton) fillUnitGeneratorRanges(fillButton);
}

function fillGeneratorSample() {
  openGeneratorModal();
  const form = document.querySelector("[data-generator-form]");
  if (!form) return;
  form.querySelector('input[name="title"]').value = "Погода 1d8";
  form.querySelector('input[name="dice_expression"]').value = "1d8";
  updateGeneratorRangeHint(form);
  const values = [
    [1, 1, "Холодный дождь"],
    [2, 4, "Обычная температура"],
    [5, 5, "Туман"],
    [6, 7, "Ливень"],
    [8, 8, "Ураганный ветер"],
  ];
  form.querySelectorAll("[data-generator-edit-row]").forEach((row, index) => {
    const value = values[index] || ["", "", ""];
    row.querySelector('input[name="row_range"]').value = value[0] === value[1] ? value[0] : `${value[0]}-${value[1]}`;
    row.querySelector('textarea[name="row_result"]').value = value[2];
  });
}

async function rollGenerator(button) {
  const generatorId = button.dataset.rollGenerator;
  const resultBox = document.querySelector(`[data-generator-roll-result="${CSS.escape(generatorId)}"]`);
  button.disabled = true;
  try {
    const response = await fetch(button.dataset.rollUrl, {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "roll_failed");
    if (resultBox) {
      window.clearTimeout(resultBox.generatorHideTimer);
      const card = resultBox.closest("[data-generator-card]");
      if (card) card.classList.add("is-showing-result");
      resultBox.hidden = false;
      resultBox.classList.remove("is-timing");
      resultBox.innerHTML = `
        <div class="generator-roll-result-head">
          <div>
            <span>${payload.formula} · ${payload.details}</span>
            <strong>Выпало: ${payload.total}</strong>
          </div>
          <div class="generator-roll-result-actions">
            <button class="audio-secondary-button generator-copy-result" type="button" data-copy-generator-result>Скопировать</button>
            <button class="audio-secondary-button generator-close-result" type="button" data-close-generator-result aria-label="Закрыть результат" title="Закрыть">×</button>
          </div>
        </div>
        <article>${payload.result_html}</article>
      `;
      const copyButton = resultBox.querySelector("[data-copy-generator-result]");
      if (copyButton) copyButton.dataset.copyGeneratorResult = payload.result_markdown || "";
      resultBox.offsetWidth;
      resultBox.classList.add("is-timing");
      resultBox.generatorHideTimer = window.setTimeout(() => {
        resultBox.hidden = true;
        resultBox.classList.remove("is-timing");
        if (card) card.classList.remove("is-showing-result");
      }, 5000);
    }
  } catch {
    showGeneratorToast("Не удалось выполнить бросок");
  } finally {
    button.disabled = false;
  }
}

async function copyGeneratorText(text) {
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

function updateGeneratorSelection() {
  const selected = document.querySelectorAll('input[name="generator_ids"]:checked').length;
  const count = document.querySelector("[data-generator-selected-count]");
  const bulkButton = document.querySelector("[data-hold-generator-bulk-delete]");
  if (count) count.textContent = String(selected);
  if (bulkButton) bulkButton.disabled = selected === 0;
}

function resetGeneratorHoldButton(button) {
  if (!button) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  const label = button.querySelector("[data-hold-delete-label]");
  if (label) label.textContent = button.matches("[data-hold-generator-bulk-delete]") ? "Удерживайте, чтобы удалить выбранные" : "Удерживайте, чтобы удалить";
}

function cancelGeneratorDeleteHold() {
  if (!activeGeneratorDeleteHold) return;
  window.clearTimeout(activeGeneratorDeleteHold.timeout);
  window.cancelAnimationFrame(activeGeneratorDeleteHold.frame);
  resetGeneratorHoldButton(activeGeneratorDeleteHold.button);
  activeGeneratorDeleteHold = null;
}

function startGeneratorDeleteHold(button) {
  const form = button.matches("[data-hold-generator-bulk-delete]")
    ? document.querySelector("#generator-delete-form")
    : (button.getAttribute("form") ? document.getElementById(button.getAttribute("form")) : button.closest("form"));
  if (!form || button.disabled) return;
  cancelGeneratorDeleteHold();
  const duration = 1900;
  const startedAt = performance.now();
  const label = button.querySelector("[data-hold-delete-label]");
  button.classList.add("is-holding");
  if (label) label.textContent = "Держите...";
  const tick = () => {
    if (!activeGeneratorDeleteHold || activeGeneratorDeleteHold.button !== button) return;
    const progress = Math.min((performance.now() - startedAt) / duration, 1);
    button.style.setProperty("--hold-progress", String(progress));
    if (progress < 1) activeGeneratorDeleteHold.frame = window.requestAnimationFrame(tick);
  };
  activeGeneratorDeleteHold = {
    button,
    frame: window.requestAnimationFrame(tick),
    timeout: window.setTimeout(async () => {
      activeGeneratorDeleteHold = null;
      try {
        await submitGeneratorAjaxForm(form, "Генератор удален");
        closeGeneratorEditModals();
      } catch {
        showGeneratorToast("Не удалось удалить генератор");
      }
    }, duration),
  };
}

document.addEventListener("change", (event) => {
  const importInput = event.target.closest("[data-generator-import-file-input]");
  if (importInput) {
    importGeneratorFile(importInput).catch(() => showGeneratorToast("Не удалось импортировать генераторы"));
    return;
  }

  if (event.target.closest('input[name="generator_ids"]')) {
    updateGeneratorSelection();
    return;
  }
  if (event.target.closest("[data-generator-category-filter], [data-generator-sort-filter], [data-generator-per-page-filter]")) {
    refreshGeneratorsPage(generatorFilterUrlFromState()).catch(() => showGeneratorToast("Не удалось применить фильтр"));
  }
});

document.addEventListener("input", (event) => {
  const diceExpression = event.target.closest('input[name="dice_expression"]');
  if (diceExpression) {
    updateGeneratorRangeHint(diceExpression.closest("form"));
    return;
  }

  const filterTagSearch = event.target.closest("[data-generator-filter-tag-search]");
  if (filterTagSearch) {
    filterGeneratorFilterTags(filterTagSearch);
    return;
  }

  const tagManagerSearch = event.target.closest("[data-generator-tag-manager-search]");
  if (tagManagerSearch) {
    const query = tagManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-generator-tag-delete-form]").forEach((form) => {
      const tag = (form.dataset.generatorTag || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !tag.includes(query);
    });
    return;
  }

  const categoryManagerSearch = event.target.closest("[data-generator-category-manager-search]");
  if (categoryManagerSearch) {
    const query = categoryManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-generator-category-delete-form]").forEach((form) => {
      const category = (form.dataset.generatorCategory || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !category.includes(query);
    });
    return;
  }

  if (!event.target.closest("[data-generator-search]")) return;
  window.clearTimeout(generatorSearchTimer);
  generatorSearchTimer = window.setTimeout(() => {
    refreshGeneratorsPage(generatorFilterUrlFromState()).catch(() => showGeneratorToast("Не удалось выполнить поиск"));
  }, 320);
});

document.addEventListener("click", async (event) => {
  const includeTag = event.target.closest("[data-generator-include-tag]");
  if (includeTag) {
    refreshGeneratorsPage(generatorFilterUrlFromState({ tagAction: "include", tag: includeTag.dataset.generatorIncludeTag }))
      .catch(() => showGeneratorToast("Не удалось применить тег"));
    return;
  }

  const excludeTag = event.target.closest("[data-generator-exclude-tag]");
  if (excludeTag) {
    refreshGeneratorsPage(generatorFilterUrlFromState({ tagAction: "exclude", tag: excludeTag.dataset.generatorExcludeTag }))
      .catch(() => showGeneratorToast("Не удалось исключить тег"));
    return;
  }

  if (event.target.closest("[data-generator-clear-filters]")) {
    const searchInput = document.querySelector("[data-generator-search]");
    if (searchInput) searchInput.value = "";
    const filterTagSearchInput = document.querySelector("[data-generator-filter-tag-search]");
    if (filterTagSearchInput) filterTagSearchInput.value = "";
    refreshGeneratorsPage(new URL("/generators", window.location.origin).toString()).catch(() => showGeneratorToast("Не удалось сбросить фильтры"));
    return;
  }

  const dynamicLink = event.target.closest("[data-generator-dynamic-link]");
  if (dynamicLink) {
    event.preventDefault();
    refreshGeneratorsPage(dynamicLink.href).catch(() => showGeneratorToast("Не удалось открыть страницу"));
    return;
  }

  if (event.target.closest("[data-open-generator-modal]")) {
    openGeneratorModal();
    resetCreateGeneratorForm(document.querySelector("[data-generator-form]"));
    return;
  }

  const generatorPreset = event.target.closest("[data-open-generator-preset]");
  if (generatorPreset) {
    openGeneratorPreset(generatorPreset.dataset.openGeneratorPreset);
    return;
  }

  if (event.target.closest("[data-close-generator-modal]")) {
    closeGeneratorModal();
    return;
  }

  const openEdit = event.target.closest("[data-open-generator-edit-modal]");
  if (openEdit) {
    await openGeneratorEditModal(openEdit.dataset.openGeneratorEditModal);
    return;
  }

  if (event.target.closest("[data-close-generator-edit-modal]")) {
    closeGeneratorEditModals();
    return;
  }

  const openImport = event.target.closest("[data-open-generator-markdown-import]");
  if (openImport) {
    openGeneratorImportModal(openImport);
    return;
  }

  if (event.target.closest("[data-close-generator-import-modal]")) {
    closeGeneratorImportModal();
    return;
  }

  if (event.target.closest("[data-apply-generator-markdown-import]")) {
    importGeneratorMarkdownTable();
    return;
  }

  const pickedTag = event.target.closest("[data-generator-pick-tag]");
  if (pickedTag) {
    togglePickedGeneratorTag(pickedTag);
    return;
  }

  const addRow = event.target.closest("[data-add-generator-row]");
  if (addRow) {
    addGeneratorRow(addRow);
    return;
  }

  const fillUnitRanges = event.target.closest("[data-generator-fill-unit-ranges]");
  if (fillUnitRanges) {
    fillUnitGeneratorRanges(fillUnitRanges);
    return;
  }

  const removeRow = event.target.closest("[data-remove-generator-row]");
  if (removeRow) {
    const rows = removeRow.closest("[data-generator-rows]");
    if (rows?.querySelectorAll("[data-generator-edit-row]").length > 1) {
      removeRow.closest("[data-generator-edit-row]")?.remove();
    }
    return;
  }

  const rollButton = event.target.closest("[data-roll-generator]");
  if (rollButton) {
    rollGenerator(rollButton);
    return;
  }

  const copyResult = event.target.closest("[data-copy-generator-result]");
  if (copyResult) {
    copyGeneratorText(copyResult.dataset.copyGeneratorResult || "")
      .then(() => showGeneratorToast("Результат скопирован"))
      .catch(() => showGeneratorToast("Не удалось скопировать"));
    return;
  }

  const closeResult = event.target.closest("[data-close-generator-result]");
  if (closeResult) {
    const resultBox = closeResult.closest("[data-generator-roll-result]");
    if (resultBox) {
      window.clearTimeout(resultBox.generatorHideTimer);
      resultBox.hidden = true;
      resultBox.classList.remove("is-timing");
      resultBox.closest("[data-generator-card]")?.classList.remove("is-showing-result");
    }
    return;
  }

  const descriptionToggle = event.target.closest("[data-toggle-generator-description]");
  if (descriptionToggle) {
    const wrap = descriptionToggle.closest("[data-generator-description-wrap]");
    const isExpanded = !wrap?.classList.contains("is-expanded");
    setGeneratorDescriptionExpanded(wrap, isExpanded);
    descriptionToggle.setAttribute("aria-expanded", String(isExpanded));
    descriptionToggle.setAttribute("aria-label", isExpanded ? "Свернуть описание" : "Показать описание полностью");
    descriptionToggle.title = isExpanded ? "Свернуть описание" : "Показать описание полностью";
    return;
  }

  const taxonomyToggle = event.target.closest("[data-toggle-generator-taxonomy]");
  if (taxonomyToggle) {
    if (document.querySelector("[data-generator-taxonomy-modal].is-open")) closeGeneratorTaxonomyModal();
    else openGeneratorTaxonomyModal();
    return;
  }

  if (event.target.closest("[data-close-generator-taxonomy]")) {
    closeGeneratorTaxonomyModal();
    return;
  }

  const taxonomyTab = event.target.closest("[data-generator-taxonomy-tab]");
  if (taxonomyTab) {
    setGeneratorTaxonomyTab(taxonomyTab.dataset.generatorTaxonomyTab);
    return;
  }

  const renameTag = event.target.closest("[data-generator-rename-tag]");
  if (renameTag) {
    openGeneratorTaxonomyRename("tag", renameTag.closest("[data-generator-tag-delete-form]"));
    return;
  }

  const renameCategory = event.target.closest("[data-generator-rename-category]");
  if (renameCategory) {
    openGeneratorTaxonomyRename("category", renameCategory.closest("[data-generator-category-delete-form]"));
    return;
  }

  if (event.target.closest("[data-close-generator-taxonomy-rename]")) {
    closeGeneratorTaxonomyRenameModal();
    return;
  }

  if (event.target.closest("[data-save-generator-taxonomy-rename]")) {
    renameGeneratorTaxonomy().catch(() => showGeneratorToast("Не удалось переименовать"));
  }
});

document.addEventListener("submit", async (event) => {
  const filterForm = event.target.closest("[data-generator-filter-form]");
  if (filterForm) {
    event.preventDefault();
    await refreshGeneratorsPage(generatorFilterUrlFromState()).catch(() => showGeneratorToast("Не удалось применить фильтр"));
    return;
  }

  const tagDeleteForm = event.target.closest("[data-generator-tag-delete-form]");
  if (tagDeleteForm) {
    event.preventDefault();
    try {
      generatorTaxonomyActiveTab = "tags";
      await submitGeneratorAjaxForm(tagDeleteForm, "Тег удален");
      openGeneratorTaxonomyModal();
    } catch {
      showGeneratorToast("Не удалось удалить тег");
    }
    return;
  }

  const categoryDeleteForm = event.target.closest("[data-generator-category-delete-form]");
  if (categoryDeleteForm) {
    event.preventDefault();
    try {
      generatorTaxonomyActiveTab = "categories";
      await submitGeneratorAjaxForm(categoryDeleteForm, "Категория удалена");
      openGeneratorTaxonomyModal();
    } catch {
      showGeneratorToast("Не удалось удалить категорию");
    }
    return;
  }

  const ajaxForm = event.target.closest("[data-generator-ajax-form], [data-generator-tag-create-form], [data-generator-category-create-form]");
  if (!ajaxForm) return;
  event.preventDefault();
  const submitButton = ajaxForm.querySelector('button[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  const reopenTaxonomy = ajaxForm.matches("[data-generator-tag-create-form], [data-generator-category-create-form]");
  if (ajaxForm.matches("[data-generator-tag-create-form]")) generatorTaxonomyActiveTab = "tags";
  if (ajaxForm.matches("[data-generator-category-create-form]")) generatorTaxonomyActiveTab = "categories";
  try {
    const message = ajaxForm.matches("[data-generator-form]")
      ? "Генератор создан"
      : ajaxForm.matches("[data-generator-edit-form]")
        ? "Генератор сохранен"
        : ajaxForm.matches("[data-generator-tag-create-form]")
          ? "Тег создан"
          : ajaxForm.matches("[data-generator-category-create-form]")
            ? "Категория создана"
            : "Готово";
    await submitGeneratorAjaxForm(ajaxForm, message);
    if (reopenTaxonomy) openGeneratorTaxonomyModal();
    closeGeneratorModal();
    closeGeneratorEditModals();
  } catch {
    showGeneratorToast("Запрос не выполнен");
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
});

document.addEventListener("pointerdown", (event) => {
  const holdButton = event.target.closest("[data-hold-generator-delete], [data-hold-generator-bulk-delete]");
  if (!holdButton) return;
  event.preventDefault();
  holdButton.setPointerCapture?.(event.pointerId);
  startGeneratorDeleteHold(holdButton);
});

["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    const holdButton = event.target.closest?.("[data-hold-generator-delete], [data-hold-generator-bulk-delete]");
    if (!holdButton || activeGeneratorDeleteHold?.button !== holdButton) return;
    cancelGeneratorDeleteHold();
  });
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-generator-taxonomy-rename-input]")) {
    event.preventDefault();
    await renameGeneratorTaxonomy().catch(() => showGeneratorToast("Не удалось переименовать"));
    return;
  }

  if (event.key === "Escape") {
    if (document.querySelector("[data-generator-taxonomy-rename-modal].is-open")) {
      closeGeneratorTaxonomyRenameModal();
      return;
    }
    if (document.querySelector("[data-generator-taxonomy-modal].is-open")) {
      closeGeneratorTaxonomyModal();
      return;
    }
    if (document.querySelector("[data-generator-import-modal].is-open")) {
      closeGeneratorImportModal();
      return;
    }
    closeGeneratorModal();
    closeGeneratorEditModals();
  }
});

window.addEventListener("popstate", () => {
  refreshGeneratorsPage(window.location.href, false).catch(() => window.location.reload());
});

refreshGeneratorRangeHints();
updateGeneratorDescriptionToggles();
window.addEventListener("resize", () => updateGeneratorDescriptionToggles());
