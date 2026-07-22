let resourcesPage = document.querySelector("[data-resources-page]");
const resourceToast = document.querySelector("[data-resource-toast]");
let resourceSearchTimer = null;
let activeResourceDeleteHold = null;
let resourceRefreshToken = 0;
let resourceTaxonomyActiveTab = "tags";
let pendingResourceTaxonomyRename = null;

function showResourceToast(message) {
  if (!resourceToast) return;
  resourceToast.textContent = message;
  resourceToast.classList.add("is-visible");
  window.clearTimeout(showResourceToast.timer);
  showResourceToast.timer = window.setTimeout(() => resourceToast.classList.remove("is-visible"), 1700);
}

function normalizeResourceTag(tag) {
  return (tag || "").trim().toLocaleLowerCase("ru-RU");
}

function removeBodyResourceTaxonomyModals() {
  document.querySelectorAll("body > [data-resource-taxonomy-modal], body > [data-resource-taxonomy-rename-modal]").forEach((modal) => modal.remove());
}

function hasOpenResourceModal() {
  return !!document.querySelector(
    "[data-resource-modal].is-open, [data-resource-edit-modal].is-open, [data-resource-taxonomy-modal].is-open, [data-resource-taxonomy-rename-modal].is-open"
  );
}

function syncResourceBodyModalState() {
  document.body.classList.toggle("has-modal", hasOpenResourceModal());
}

function getResourceTaxonomyModal() {
  const modal = document.querySelector("[data-resource-taxonomy-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function getResourceTaxonomyRenameModal() {
  const modal = document.querySelector("[data-resource-taxonomy-rename-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function setResourceTaxonomyTab(tabName = "tags") {
  resourceTaxonomyActiveTab = tabName === "categories" ? "categories" : "tags";
  const modal = getResourceTaxonomyModal();
  if (!modal) return;
  modal.querySelectorAll("[data-resource-taxonomy-tab]").forEach((tab) => {
    const isActive = tab.dataset.resourceTaxonomyTab === resourceTaxonomyActiveTab;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
    tab.tabIndex = isActive ? 0 : -1;
  });
  modal.querySelectorAll("[data-resource-taxonomy-pane]").forEach((pane) => {
    const isActive = pane.dataset.resourceTaxonomyPane === resourceTaxonomyActiveTab;
    pane.classList.toggle("is-active", isActive);
    pane.hidden = !isActive;
  });
}

async function refreshResourcesPage(url, push = true) {
  const refreshToken = ++resourceRefreshToken;
  const activeSearch = document.activeElement?.matches?.("[data-resource-search]")
    ? {
        value: document.activeElement.value,
        start: document.activeElement.selectionStart,
        end: document.activeElement.selectionEnd,
      }
    : null;
  const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
  if (!response.ok) throw new Error("Resources page was not loaded.");
  const html = await response.text();
  if (refreshToken !== resourceRefreshToken) return;
  const doc = new DOMParser().parseFromString(html, "text/html");
  const nextPage = doc.querySelector("[data-resources-page]");
  if (!nextPage || !resourcesPage) {
    window.location.href = url;
    return;
  }
  const latestSearch = activeSearch
    ? (() => {
        const liveInput = document.querySelector("[data-resource-search]");
        return liveInput
          ? {
              value: liveInput.value || "",
              start: liveInput.selectionStart ?? activeSearch.start,
              end: liveInput.selectionEnd ?? activeSearch.end,
            }
          : activeSearch;
      })()
    : null;
  removeBodyResourceTaxonomyModals();
  resourcesPage.replaceWith(nextPage);
  resourcesPage = nextPage;
  if (push) window.history.pushState({}, "", url);
  if (latestSearch) {
    const nextSearch = resourcesPage.querySelector("[data-resource-search]");
    if (nextSearch) {
      nextSearch.value = latestSearch.value;
      nextSearch.focus();
      nextSearch.setSelectionRange(latestSearch.start ?? latestSearch.value.length, latestSearch.end ?? latestSearch.value.length);
    }
  }
  if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
  openInitialResourceModal();
}

async function submitResourceAjaxForm(form, message = "") {
  const response = await fetch(form.action, {
    method: form.method || "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "fetch" },
  });
  if (!response.ok) throw new Error("Resource form failed.");
  const contentType = response.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    await response.json();
    await refreshResourcesPage(window.location.href, false);
    if (message) showResourceToast(message);
    return;
  }
  const html = await response.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  const nextPage = doc.querySelector("[data-resources-page]");
  if (nextPage && resourcesPage) {
    removeBodyResourceTaxonomyModals();
    resourcesPage.replaceWith(nextPage);
    resourcesPage = nextPage;
    syncResourceBodyModalState();
    window.history.replaceState({}, "", response.url || window.location.href);
  } else if (response.url) {
    await refreshResourcesPage(response.url, false);
  }
  if (message) showResourceToast(message);
}

function selectedResourceTags(input) {
  return (input?.value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function setResourceTags(input, tags) {
  const seen = new Set();
  const normalized = [];
  tags.forEach((tag) => {
    const clean = tag.trim();
    const key = normalizeResourceTag(clean);
    if (clean && !seen.has(key)) {
      seen.add(key);
      normalized.push(clean);
    }
  });
  if (input) input.value = normalized.join(", ");
}

function syncResourceTagPicker(picker) {
  const input = picker.closest("form")?.querySelector("[data-resource-modal-tags-input], [data-resource-track-tags-input]");
  const active = new Set(selectedResourceTags(input).map(normalizeResourceTag));
  picker.querySelectorAll("[data-resource-pick-tag]").forEach((button) => {
    button.classList.toggle("is-active", active.has(normalizeResourceTag(button.dataset.resourcePickTag)));
  });
}

function togglePickedResourceTag(button) {
  const form = button.closest("form");
  const input = form?.querySelector("[data-resource-modal-tags-input], [data-resource-track-tags-input]");
  if (!input) return;
  const tag = button.dataset.resourcePickTag;
  const current = selectedResourceTags(input);
  const hasTag = current.some((item) => normalizeResourceTag(item) === normalizeResourceTag(tag));
  setResourceTags(input, hasTag ? current.filter((item) => normalizeResourceTag(item) !== normalizeResourceTag(tag)) : [...current, tag]);
  syncResourceTagPicker(button.closest("[data-resource-tag-picker]"));
}

function filterResourceTagPicker(searchInput) {
  const picker = searchInput.closest("[data-resource-tag-picker]");
  if (!picker) return;
  const query = normalizeResourceTag(searchInput.value);
  picker.querySelectorAll("[data-resource-pick-tag]").forEach((button) => {
    const tag = normalizeResourceTag(button.dataset.resourcePickTag || button.textContent);
    button.hidden = query && !tag.includes(query);
  });
}

function resourceFilterUrlFromState({ tagAction = null, tag = "", page = 1 } = {}) {
  const form = document.querySelector("[data-resource-filter-form]");
  const url = new URL(form?.action || window.location.href, window.location.origin);
  const query = form?.querySelector("[data-resource-search]")?.value.trim() || "";
  const category = form?.querySelector("[data-resource-category-filter]")?.value || "";
  const type = form?.querySelector("[data-resource-type-filter]")?.value || "";
  const sort = form?.querySelector("[data-resource-sort-filter]")?.value || "";
  const perPage = form?.querySelector("[data-resource-per-page-filter]")?.value || "";
  const included = new Set([...document.querySelectorAll("[data-resource-filter-chip].is-included")].map((chip) => chip.dataset.resourceFilterChip));
  const excluded = new Set([...document.querySelectorAll("[data-resource-filter-chip].is-excluded")].map((chip) => chip.dataset.resourceFilterChip));

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
  if (type) url.searchParams.set("type", type);
  if (sort && sort !== "title") url.searchParams.set("sort", sort);
  if (perPage) url.searchParams.set("per_page", perPage);
  if (page > 1) url.searchParams.set("page", String(page));
  [...included].forEach((item) => url.searchParams.append("tag", item));
  [...excluded].forEach((item) => url.searchParams.append("exclude_tag", item));
  return url.toString();
}

function setResourceModalType(type = "web") {
  const modal = document.querySelector("[data-resource-modal]");
  if (!modal) return;
  const cleanType = type === "local" ? "local" : "web";
  modal.querySelector("[data-resource-modal-source-type]").value = cleanType;
  modal.querySelector("[data-resource-web-field]").hidden = cleanType === "local";
  modal.querySelector("[data-resource-local-field]").hidden = cleanType !== "local";
  modal.querySelector("[data-resource-modal-kicker]").textContent = cleanType === "local" ? "Локальный путь" : "Интернет";
  modal.querySelector("[data-resource-modal-title]").textContent = cleanType === "local" ? "Новый локальный ресурс" : "Новая ссылка";
  const urlInput = modal.querySelector('input[name="url"]');
  const pathInput = modal.querySelector("[data-resource-path-display]");
  const capabilityInput = modal.querySelector('input[name="file_capability"]');
  if (urlInput) urlInput.required = cleanType === "web";
  if (pathInput) pathInput.required = cleanType === "local";
  if (cleanType === "web" && pathInput) {
    pathInput.value = "";
    if (capabilityInput) capabilityInput.value = "";
  }
  if (cleanType === "local" && urlInput) urlInput.value = "";
}

async function pickResourceFile(button) {
  const form = button.closest("form");
  const pathInput = form?.querySelector("[data-resource-path-display]");
  const capabilityInput = form?.querySelector('input[name="file_capability"]');
  if (!pathInput || !capabilityInput) return;
  button.disabled = true;
  try {
    showResourceToast("Открываю выбор файла...");
    const payload = await window.startLocalJob("/resources/pick-file", {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    });
    if (!payload.ok) throw new Error(payload.error || "File picker failed.");
    if (payload.cancelled) {
      showResourceToast("Выбор файла отменён");
      return;
    }
    pathInput.value = payload.display_name || "";
    capabilityInput.value = payload.capability_id || "";
    pathInput.dispatchEvent(new Event("input", { bubbles: true }));
    showResourceToast("Файл выбран");
  } catch {
    showResourceToast("Не удалось открыть выбор файла");
  } finally {
    button.disabled = false;
  }
}

function openResourceModal(type = "web") {
  const modal = document.querySelector("[data-resource-modal]");
  if (!modal) return;
  setResourceModalType(type);
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => modal.querySelector('input[name="title"]')?.focus(), 30);
}

function closeResourceModal() {
  const modal = document.querySelector("[data-resource-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  syncResourceBodyModalState();
}

async function openResourceEditModal(resourceId) {
  await closeResourceEditModals();
  closeResourceModal();
  const modal = document.querySelector(`[data-resource-edit-modal="${CSS.escape(resourceId)}"]`);
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function clearInitialResourceFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("resource")) return;
  url.searchParams.delete("resource");
  window.history.replaceState({}, "", url.toString());
}

async function closeResourceEditModals({ save = true } = {}) {
  const openForms = save
    ? [...document.querySelectorAll("[data-resource-edit-modal].is-open [data-resource-edit-form]")]
    : [];
  document.querySelectorAll("[data-resource-edit-modal]").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  syncResourceBodyModalState();
  clearInitialResourceFromUrl();
  if (openForms.length) {
    await Promise.all(openForms.map((form) => submitResourceAjaxForm(form)));
  }
}

function openInitialResourceModal() {
  const resourceId = resourcesPage?.dataset.openResourceId || "";
  if (!resourceId) return;
  resourcesPage.dataset.openResourceId = "";
  window.setTimeout(() => openResourceEditModal(resourceId), 40);
}

function openResourceTaxonomyModal() {
  const modal = getResourceTaxonomyModal();
  if (!modal) return;
  setResourceTaxonomyTab(resourceTaxonomyActiveTab);
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const toggle = document.querySelector("[data-toggle-resource-tags]");
  if (toggle) {
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
  }
  window.setTimeout(() => modal.querySelector("[data-resource-taxonomy-pane].is-active input")?.focus(), 40);
}

function closeResourceTaxonomyModal() {
  const modal = document.querySelector("[data-resource-taxonomy-modal]");
  if (!modal) return;
  closeResourceTaxonomyRenameModal();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const toggle = document.querySelector("[data-toggle-resource-tags]");
  if (toggle) {
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  }
  syncResourceBodyModalState();
}

function openResourceTaxonomyRename(kind, form) {
  const modal = getResourceTaxonomyRenameModal();
  const oldValue = kind === "category" ? form?.dataset.resourceCategory || "" : form?.dataset.resourceTag || "";
  if (!modal || !oldValue) return;
  pendingResourceTaxonomyRename = { kind, form };
  const label = kind === "category" ? "категорию" : "тег";
  const kicker = modal.querySelector("[data-resource-taxonomy-rename-kicker]");
  const title = modal.querySelector("[data-resource-taxonomy-rename-title]");
  const input = modal.querySelector("[data-resource-taxonomy-rename-input]");
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

function closeResourceTaxonomyRenameModal() {
  const modal = document.querySelector("[data-resource-taxonomy-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const input = modal.querySelector("[data-resource-taxonomy-rename-input]");
  if (input) input.value = "";
  pendingResourceTaxonomyRename = null;
  syncResourceBodyModalState();
}

async function renameResourceTaxonomy() {
  const pending = pendingResourceTaxonomyRename;
  if (!pending?.form) return;
  const modal = document.querySelector("[data-resource-taxonomy-rename-modal]");
  const input = modal?.querySelector("[data-resource-taxonomy-rename-input]");
  const cleanValue = (input?.value || "").trim();
  const editor = document.querySelector("[data-resource-tag-editor]");
  const isCategory = pending.kind === "category";
  const oldValue = isCategory ? pending.form.dataset.resourceCategory || "" : pending.form.dataset.resourceTag || "";
  if (!oldValue || !cleanValue || normalizeResourceTag(oldValue) === normalizeResourceTag(cleanValue)) {
    closeResourceTaxonomyRenameModal();
    return;
  }
  const url = isCategory ? editor?.dataset.resourceCategoryRenameUrl : editor?.dataset.resourceTagRenameUrl;
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
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Resource taxonomy was not renamed.");
  resourceTaxonomyActiveTab = isCategory ? "categories" : "tags";
  await refreshResourcesPage(window.location.href, false);
  closeResourceTaxonomyRenameModal();
  showResourceToast(isCategory ? "Категория переименована" : "Тег переименован");
  openResourceTaxonomyModal();
}

function updateResourceSelection() {
  const selected = document.querySelectorAll('input[name="resource_ids"]:checked').length;
  const count = document.querySelector("[data-resource-selected-count]");
  const bulkButton = document.querySelector("[data-hold-resource-bulk-delete]");
  if (count) count.textContent = String(selected);
  if (bulkButton) {
    bulkButton.disabled = selected === 0;
    if (selected === 0) resetResourceHoldButton(bulkButton);
  }
}

function resetResourceHoldButton(button) {
  if (!button) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  if (typeof releaseHoldDeleteButtonSize === "function") releaseHoldDeleteButtonSize(button);
  const label = button.querySelector("[data-hold-delete-label]");
  if (!label) return;
  label.textContent = button.matches("[data-hold-resource-bulk-delete]")
    ? "Удерживайте, чтобы удалить выбранные"
    : "Удерживайте, чтобы удалить";
}

function cancelResourceDeleteHold() {
  if (!activeResourceDeleteHold) return;
  window.clearTimeout(activeResourceDeleteHold.timeout);
  window.cancelAnimationFrame(activeResourceDeleteHold.frame);
  resetResourceHoldButton(activeResourceDeleteHold.button);
  activeResourceDeleteHold = null;
}

function startResourceDeleteHold(button) {
  const form = button.matches("[data-hold-resource-bulk-delete]")
    ? document.querySelector("#resource-delete-form")
    : button.closest("form");
  if (!form || button.disabled) return;
  if (button.matches("[data-hold-resource-bulk-delete]") && !document.querySelectorAll('input[name="resource_ids"]:checked').length) {
    showResourceToast("Выберите ресурсы для удаления");
    return;
  }
  cancelResourceDeleteHold();
  const duration = 1900;
  const startedAt = performance.now();
  const label = button.querySelector("[data-hold-delete-label]");
  if (typeof lockHoldDeleteButtonSize === "function") lockHoldDeleteButtonSize(button);
  button.classList.add("is-holding");
  if (label) label.textContent = "Держите...";

  const tick = () => {
    if (!activeResourceDeleteHold || activeResourceDeleteHold.button !== button) return;
    const progress = Math.min((performance.now() - startedAt) / duration, 1);
    button.style.setProperty("--hold-progress", String(progress));
    if (progress < 1) activeResourceDeleteHold.frame = window.requestAnimationFrame(tick);
  };

  activeResourceDeleteHold = {
    button,
    frame: window.requestAnimationFrame(tick),
    timeout: window.setTimeout(async () => {
      activeResourceDeleteHold = null;
      button.classList.remove("is-holding");
      button.style.setProperty("--hold-progress", "1");
      if (label) label.textContent = "Удаляю...";
      try {
        await submitResourceAjaxForm(form, button.matches("[data-hold-resource-bulk-delete]") ? "Ресурсы удалены" : "Ресурс удалён");
        closeResourceEditModals({ save: false });
      } catch {
        showResourceToast("Не удалось удалить ресурс");
        resetResourceHoldButton(button);
      }
    }, duration),
  };
}

async function copyResourceText(text) {
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

document.addEventListener("change", (event) => {
  if (event.target.closest('input[name="resource_ids"]')) {
    updateResourceSelection();
    return;
  }
  if (event.target.closest("[data-resource-category-filter], [data-resource-type-filter], [data-resource-sort-filter], [data-resource-per-page-filter]")) {
    refreshResourcesPage(resourceFilterUrlFromState()).catch(() => showResourceToast("Не удалось применить фильтр"));
  }
});

document.addEventListener("input", (event) => {
  const tagPickerSearch = event.target.closest("[data-resource-tag-picker-search]");
  if (tagPickerSearch) {
    filterResourceTagPicker(tagPickerSearch);
    return;
  }

  const tagManagerSearch = event.target.closest("[data-resource-tag-manager-search]");
  if (tagManagerSearch) {
    const query = tagManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-resource-tag-delete-form]").forEach((form) => {
      const tag = (form.dataset.resourceTag || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !tag.includes(query);
    });
    return;
  }

  const categoryManagerSearch = event.target.closest("[data-resource-category-manager-search]");
  if (categoryManagerSearch) {
    const query = categoryManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-resource-category-delete-form]").forEach((form) => {
      const category = (form.dataset.resourceCategory || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !category.includes(query);
    });
    return;
  }

  if (!event.target.closest("[data-resource-search]")) return;
  window.clearTimeout(resourceSearchTimer);
  resourceSearchTimer = window.setTimeout(() => {
    refreshResourcesPage(resourceFilterUrlFromState()).catch(() => showResourceToast("Не удалось выполнить поиск"));
  }, 320);
});

document.addEventListener("click", async (event) => {
  const dynamicLink = event.target.closest("[data-resource-dynamic-link]");
  if (dynamicLink) {
    event.preventDefault();
    refreshResourcesPage(dynamicLink.href).catch(() => showResourceToast("Не удалось открыть страницу"));
    return;
  }

  const includeTag = event.target.closest("[data-resource-include-tag]");
  if (includeTag) {
    refreshResourcesPage(resourceFilterUrlFromState({ tagAction: "include", tag: includeTag.dataset.resourceIncludeTag }))
      .catch(() => showResourceToast("Не удалось применить тег"));
    return;
  }

  const excludeTag = event.target.closest("[data-resource-exclude-tag]");
  if (excludeTag) {
    refreshResourcesPage(resourceFilterUrlFromState({ tagAction: "exclude", tag: excludeTag.dataset.resourceExcludeTag }))
      .catch(() => showResourceToast("Не удалось исключить тег"));
    return;
  }

  if (event.target.closest("[data-resource-clear-filters]")) {
    refreshResourcesPage(new URL("/resources", window.location.origin).toString()).catch(() => showResourceToast("Не удалось сбросить фильтры"));
    return;
  }

  const tagToggle = event.target.closest("[data-toggle-resource-tags]");
  if (tagToggle) {
    if (document.querySelector("[data-resource-taxonomy-modal].is-open")) closeResourceTaxonomyModal();
    else openResourceTaxonomyModal();
    return;
  }

  if (event.target.closest("[data-close-resource-taxonomy]")) {
    closeResourceTaxonomyModal();
    return;
  }

  const taxonomyTab = event.target.closest("[data-resource-taxonomy-tab]");
  if (taxonomyTab) {
    setResourceTaxonomyTab(taxonomyTab.dataset.resourceTaxonomyTab);
    return;
  }

  const renameTag = event.target.closest("[data-resource-rename-tag]");
  if (renameTag) {
    openResourceTaxonomyRename("tag", renameTag.closest("[data-resource-tag-delete-form]"));
    return;
  }

  const renameCategory = event.target.closest("[data-resource-rename-category]");
  if (renameCategory) {
    openResourceTaxonomyRename("category", renameCategory.closest("[data-resource-category-delete-form]"));
    return;
  }

  if (event.target.closest("[data-close-resource-taxonomy-rename]")) {
    closeResourceTaxonomyRenameModal();
    return;
  }

  if (event.target.closest("[data-save-resource-taxonomy-rename]")) {
    renameResourceTaxonomy().catch(() => showResourceToast("Не удалось переименовать"));
    return;
  }

  const openCreate = event.target.closest("[data-open-resource-modal]");
  if (openCreate) {
    openResourceModal(openCreate.dataset.resourceModalType || "web");
    return;
  }

  const pickerButton = event.target.closest("[data-pick-resource-file]");
  if (pickerButton) {
    pickResourceFile(pickerButton);
    return;
  }

  if (event.target.closest("[data-close-resource-modal]")) {
    closeResourceModal();
    return;
  }

  const openEdit = event.target.closest("[data-open-resource-edit-modal]");
  if (openEdit) {
    await openResourceEditModal(openEdit.dataset.openResourceEditModal);
    return;
  }

  if (event.target.closest("[data-close-resource-edit-modal]")) {
    await closeResourceEditModals();
    return;
  }

  const copyButton = event.target.closest("[data-copy-resource-target]");
  if (copyButton) {
    copyResourceText(copyButton.dataset.copyResourceTarget || "")
      .then(() => showResourceToast("Ссылка скопирована"))
      .catch(() => showResourceToast("Не удалось скопировать"));
    return;
  }

  const openLocalButton = event.target.closest("[data-open-local-resource]");
  if (openLocalButton) {
    openLocalButton.disabled = true;
    fetch(openLocalButton.dataset.openLocalResource, {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) throw new Error(payload.error || "open_failed");
        showResourceToast("Файл открыт");
      })
      .catch((error) => {
        showResourceToast(error.message === "file_not_found" ? "Файл не найден" : "Не удалось открыть файл");
      })
      .finally(() => {
        openLocalButton.disabled = false;
      });
    return;
  }

  const pickedTag = event.target.closest("[data-resource-pick-tag]");
  if (pickedTag) {
    togglePickedResourceTag(pickedTag);
  }
});

document.addEventListener("submit", async (event) => {
  const filterForm = event.target.closest("[data-resource-filter-form]");
  if (filterForm) {
    event.preventDefault();
    await refreshResourcesPage(resourceFilterUrlFromState()).catch(() => showResourceToast("Не удалось применить фильтр"));
    return;
  }

  const tagDeleteForm = event.target.closest("[data-resource-tag-delete-form]");
  if (tagDeleteForm) {
    event.preventDefault();
    try {
      resourceTaxonomyActiveTab = "tags";
      await submitResourceAjaxForm(tagDeleteForm, "Тег удалён");
      openResourceTaxonomyModal();
    } catch {
      showResourceToast("Не удалось удалить тег");
    }
    return;
  }

  const categoryDeleteForm = event.target.closest("[data-resource-category-delete-form]");
  if (categoryDeleteForm) {
    event.preventDefault();
    try {
      resourceTaxonomyActiveTab = "categories";
      await submitResourceAjaxForm(categoryDeleteForm, "Категория удалена");
      openResourceTaxonomyModal();
    } catch {
      showResourceToast("Не удалось удалить категорию");
    }
    return;
  }

  const ajaxForm = event.target.closest("[data-resource-ajax-form], [data-resource-tag-create-form], [data-resource-category-create-form]");
  if (ajaxForm) {
    event.preventDefault();
    const submitButton = ajaxForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    const reopenTaxonomy = ajaxForm.matches("[data-resource-tag-create-form], [data-resource-category-create-form]");
    if (ajaxForm.matches("[data-resource-tag-create-form]")) resourceTaxonomyActiveTab = "tags";
    if (ajaxForm.matches("[data-resource-category-create-form]")) resourceTaxonomyActiveTab = "categories";
    try {
      const message = ajaxForm.matches("[data-resource-form]")
        ? "Ресурс создан"
        : ajaxForm.matches("[data-resource-edit-form]")
          ? "Ресурс сохранён"
          : ajaxForm.matches("[data-resource-tag-create-form]")
            ? "Тег создан"
            : ajaxForm.matches("[data-resource-category-create-form]")
              ? "Категория создана"
              : ajaxForm.matches("[data-resource-delete-form]")
                ? "Ресурсы удалены"
                : "Готово";
      await submitResourceAjaxForm(ajaxForm, message);
      if (reopenTaxonomy) openResourceTaxonomyModal();
      closeResourceModal();
      if (ajaxForm.matches("[data-resource-edit-form]")) closeResourceEditModals({ save: false });
    } catch {
      showResourceToast("Запрос не выполнен");
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  }
});

document.addEventListener("pointerdown", (event) => {
  const holdButton = event.target.closest("[data-hold-resource-delete], [data-hold-resource-bulk-delete]");
  if (!holdButton) return;
  event.preventDefault();
  holdButton.setPointerCapture?.(event.pointerId);
  startResourceDeleteHold(holdButton);
});

["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    const holdButton = event.target.closest?.("[data-hold-resource-delete], [data-hold-resource-bulk-delete]");
    if (!holdButton || activeResourceDeleteHold?.button !== holdButton) return;
    cancelResourceDeleteHold();
  });
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-resource-taxonomy-rename-input]")) {
    event.preventDefault();
    await renameResourceTaxonomy().catch(() => showResourceToast("Не удалось переименовать"));
    return;
  }

  if (event.key === "Escape") {
    closeResourceTaxonomyRenameModal();
    closeResourceTaxonomyModal();
    closeResourceModal();
    await closeResourceEditModals();
  }
});

window.addEventListener("popstate", () => {
  refreshResourcesPage(window.location.href, false).catch(() => window.location.reload());
});

openInitialResourceModal();
