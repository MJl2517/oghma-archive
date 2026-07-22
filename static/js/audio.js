let audioPage = document.querySelector("[data-audio-page]");
const audioToast = document.querySelector("[data-audio-toast]");
let audioSearchTimer = null;
let activeAudioDeleteHold = null;
let draggedAudioCategoryItem = null;
let audioRefreshToken = 0;
let audioTaxonomyActiveTab = "tags";
let pendingAudioTagRenameForm = null;

function showAudioToast(message) {
  if (!audioToast) return;
  audioToast.textContent = message;
  audioToast.classList.add("is-visible");
  window.clearTimeout(showAudioToast.timer);
  showAudioToast.timer = window.setTimeout(() => audioToast.classList.remove("is-visible"), 1700);
}

function clearAudioFormErrors(form) {
  form.querySelectorAll(".has-audio-error").forEach((element) => element.classList.remove("has-audio-error"));
  form.querySelectorAll("[data-audio-inline-error]").forEach((element) => element.remove());
}

function appendAudioFormError(form, field, message) {
  const input = field ? form.querySelector(`[name="${CSS.escape(field)}"]`) : null;
  const target = input?.closest("label") || form.querySelector("label");
  if (!target) return;
  target.classList.add("has-audio-error");
  const error = document.createElement("small");
  error.className = "audio-inline-error";
  error.dataset.audioInlineError = "true";
  error.textContent = message;
  target.appendChild(error);
  input?.focus();
}

function showAudioFormError(form, payload = {}) {
  clearAudioFormErrors(form);
  const fallbackMessage = "Не удалось сохранить трек. Проверьте поля.";
  const message = payload.message || (payload.error === "youtube_url_required" ? "Укажите корректную YouTube-ссылку." : fallbackMessage);
  appendAudioFormError(form, payload.field, message);
}

function normalizeAudioTag(tag) {
  return (tag || "").trim().toLocaleLowerCase("ru-RU");
}

function currentAudioUrl() {
  return new URL(window.location.href);
}

function removeBodyAudioTaxonomyModals() {
  document.querySelectorAll("body > [data-audio-taxonomy-modal], body > [data-audio-tag-rename-modal]").forEach((modal) => modal.remove());
}

function getAudioTaxonomyModal() {
  const modal = document.querySelector("[data-audio-taxonomy-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function setAudioTaxonomyTab(tabName = "tags") {
  audioTaxonomyActiveTab = tabName === "categories" ? "categories" : "tags";
  const modal = getAudioTaxonomyModal();
  if (!modal) return;
  modal.querySelectorAll("[data-audio-taxonomy-tab]").forEach((tab) => {
    const isActive = tab.dataset.audioTaxonomyTab === audioTaxonomyActiveTab;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-selected", isActive ? "true" : "false");
    tab.tabIndex = isActive ? 0 : -1;
  });
  modal.querySelectorAll("[data-audio-taxonomy-pane]").forEach((pane) => {
    const isActive = pane.dataset.audioTaxonomyPane === audioTaxonomyActiveTab;
    pane.classList.toggle("is-active", isActive);
    pane.hidden = !isActive;
  });
}

async function refreshAudioPage(url, push = true) {
  const refreshToken = ++audioRefreshToken;
  const activeSearch = document.activeElement?.matches?.("[data-audio-search]")
    ? {
        value: document.activeElement.value,
        start: document.activeElement.selectionStart,
        end: document.activeElement.selectionEnd,
      }
    : null;
  const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
  if (!response.ok) throw new Error("Audio page was not loaded.");
  const html = await response.text();
  if (refreshToken !== audioRefreshToken) return;
  const doc = new DOMParser().parseFromString(html, "text/html");
  const nextPage = doc.querySelector("[data-audio-page]");
  if (!nextPage || !audioPage) {
    window.location.href = url;
    return;
  }
  const latestSearch = activeSearch
    ? (() => {
        const liveInput = document.querySelector("[data-audio-search]");
        return liveInput
          ? {
              value: liveInput.value || "",
              start: liveInput.selectionStart ?? activeSearch.start,
              end: liveInput.selectionEnd ?? activeSearch.end,
            }
          : activeSearch;
      })()
    : null;
  removeBodyAudioTaxonomyModals();
  audioPage.replaceWith(nextPage);
  audioPage = nextPage;
  if (push) window.history.pushState({}, "", url);
  if (latestSearch) {
    const nextSearch = audioPage.querySelector("[data-audio-search]");
    if (nextSearch) {
      nextSearch.value = latestSearch.value;
      nextSearch.focus();
      nextSearch.setSelectionRange(latestSearch.start ?? latestSearch.value.length, latestSearch.end ?? latestSearch.value.length);
    }
  }
  if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
  openInitialAudioTrackModal();
}

async function submitAudioAjaxForm(form, message = "") {
  const response = await fetch(form.action, {
    method: form.method || "POST",
    body: new FormData(form),
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
  });
  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok) {
    if (contentType.includes("application/json")) {
      showAudioFormError(form, await response.json());
      const validationError = new Error("Audio validation failed.");
      validationError.name = "AudioValidationError";
      throw validationError;
    }
    throw new Error("Audio form failed.");
  }
  clearAudioFormErrors(form);
  if (contentType.includes("application/json")) {
    await response.json();
    await refreshAudioPage(window.location.href, false);
    if (message) showAudioToast(message);
    return;
  }
  const html = await response.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  const nextPage = doc.querySelector("[data-audio-page]");
  if (nextPage && audioPage) {
    removeBodyAudioTaxonomyModals();
    audioPage.replaceWith(nextPage);
    audioPage = nextPage;
    document.body.classList.remove("has-modal");
    window.history.replaceState({}, "", response.url || window.location.href);
  } else if (response.url) {
    await refreshAudioPage(response.url, false);
  }
  if (message) showAudioToast(message);
}

async function renameAudioTag(button) {
  const modal = button.closest("[data-audio-tag-rename-modal]");
  const form = button.closest("[data-audio-tag-delete-form]") || pendingAudioTagRenameForm;
  const oldTag = form?.dataset.audioTag || button.dataset.audioRenameTag || "";
  const input = modal?.querySelector("[data-audio-rename-input]") || form?.querySelector("[data-audio-rename-input]");
  const cleanTag = (input?.value || "").trim();
  if (!oldTag || !cleanTag || cleanTag.toLocaleLowerCase("ru-RU") === oldTag.toLocaleLowerCase("ru-RU")) {
    closeAudioTagRenameModal();
    return;
  }
  const panel = form?.closest("[data-audio-tag-editor]") || document.querySelector("[data-audio-tag-editor]");
  const url = panel?.dataset.audioTagRenameUrl || "";
  if (!url) return;
  const formData = new FormData();
  formData.append("tag", oldTag);
  formData.append("new_tag", cleanTag);
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    body: formData,
  });
  if (!response.ok) {
    showAudioToast("Не удалось переименовать тег");
    return;
  }
  audioTaxonomyActiveTab = "tags";
  await refreshAudioPage(window.location.href, false);
  pendingAudioTagRenameForm = null;
  closeAudioTagRenameModal();
  showAudioToast("Тег переименован");
  openAudioTaxonomyModal();
}

function openAudioTagRename(button) {
  const form = button.closest("[data-audio-tag-delete-form]");
  if (!form) return;
  openAudioTagRenameModal(form);
}

function closeAudioTagRename(form) {
  const targetForm = form || pendingAudioTagRenameForm;
  targetForm?.classList.remove("is-renaming");
  const view = targetForm?.querySelector("[data-audio-tag-row-view]");
  const edit = targetForm?.querySelector("[data-audio-tag-row-edit]");
  const input = targetForm?.querySelector("[data-audio-rename-input]");
  if (input) input.value = targetForm.dataset.audioTag || input.value;
  if (edit) edit.hidden = true;
  if (view) view.hidden = false;
  closeAudioTagRenameModal();
}

function getAudioTagRenameModal() {
  const modal = document.querySelector("[data-audio-tag-rename-modal]");
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  return modal;
}

function openAudioTagRenameModal(form) {
  const tag = form?.dataset.audioTag || "";
  const modal = getAudioTagRenameModal();
  if (!modal || !tag) return;
  pendingAudioTagRenameForm = form;
  const title = modal.querySelector("[data-audio-tag-rename-title]");
  if (title) title.textContent = `Переименовать «${tag}»`;
  const input = modal.querySelector("[data-audio-rename-input]");
  if (input) input.value = tag;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeAudioTagRenameModal() {
  const modal = document.querySelector("[data-audio-tag-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const input = modal.querySelector("[data-audio-rename-input]");
  if (input) input.value = "";
  pendingAudioTagRenameForm = null;
  if (!document.querySelector("[data-audio-link-modal].is-open, [data-audio-track-modal].is-open, [data-audio-taxonomy-modal].is-open, [data-audio-category-order-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

async function renameAudioCategory(button) {
  const form = button.closest("[data-audio-category-delete-form]");
  const oldCategory = form?.dataset.audioCategory || "";
  const input = form?.querySelector("[data-audio-category-rename-input]");
  const cleanCategory = (input?.value || "").trim();
  if (!oldCategory || !cleanCategory || cleanCategory.toLocaleLowerCase("ru-RU") === oldCategory.toLocaleLowerCase("ru-RU")) {
    closeAudioCategoryRename(form);
    return;
  }
  const panel = form?.closest("[data-audio-tag-editor]") || document.querySelector("[data-audio-tag-editor]");
  const url = panel?.dataset.audioCategoryRenameUrl || "";
  if (!url) return;
  const formData = new FormData();
  formData.append("category", oldCategory);
  formData.append("new_category", cleanCategory);
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    body: formData,
  });
  if (!response.ok) {
    showAudioToast("Не удалось переименовать категорию");
    return;
  }
  audioTaxonomyActiveTab = "categories";
  await refreshAudioPage(window.location.href, false);
  showAudioToast("Категория переименована");
  openAudioTaxonomyModal();
}

function openAudioCategoryRename(button) {
  const form = button.closest("[data-audio-category-delete-form]");
  if (!form) return;
  document.querySelectorAll("[data-audio-category-delete-form].is-renaming").forEach((item) => {
    if (item !== form) closeAudioCategoryRename(item);
  });
  form.classList.add("is-renaming");
  const view = form.querySelector("[data-audio-category-row-view]");
  const edit = form.querySelector("[data-audio-category-row-edit]");
  const input = form.querySelector("[data-audio-category-rename-input]");
  if (view) view.hidden = true;
  if (edit) edit.hidden = false;
  if (input) {
    input.value = form.dataset.audioCategory || input.value;
    window.setTimeout(() => {
      input.focus();
      input.select();
    }, 30);
  }
}

function closeAudioCategoryRename(form) {
  if (!form) return;
  form.classList.remove("is-renaming");
  const view = form.querySelector("[data-audio-category-row-view]");
  const edit = form.querySelector("[data-audio-category-row-edit]");
  const input = form.querySelector("[data-audio-category-rename-input]");
  if (input) input.value = form.dataset.audioCategory || input.value;
  if (edit) edit.hidden = true;
  if (view) view.hidden = false;
}

function selectedAudioTags(input) {
  return (input?.value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setAudioTags(input, tags) {
  const seen = new Set();
  const normalized = [];
  tags.forEach((tag) => {
    const clean = tag.trim();
    const key = normalizeAudioTag(clean);
    if (clean && !seen.has(key)) {
      seen.add(key);
      normalized.push(clean);
    }
  });
  if (input) input.value = normalized.join(", ");
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

function syncAudioTagPicker(picker) {
  const input = picker.closest("form")?.querySelector("[data-audio-modal-tags-input], [data-audio-track-tags-input]");
  const active = new Set(selectedAudioTags(input).map(normalizeAudioTag));
  picker.querySelectorAll("[data-audio-pick-tag]").forEach((button) => {
    button.classList.toggle("is-active", active.has(normalizeAudioTag(button.dataset.audioPickTag)));
  });
}

function togglePickedAudioTag(button) {
  const form = button.closest("form");
  const input = form?.querySelector("[data-audio-modal-tags-input], [data-audio-track-tags-input]");
  if (!input) return;
  const tag = button.dataset.audioPickTag;
  const current = selectedAudioTags(input);
  const hasTag = current.some((item) => normalizeAudioTag(item) === normalizeAudioTag(tag));
  setAudioTags(input, hasTag ? current.filter((item) => normalizeAudioTag(item) !== normalizeAudioTag(tag)) : [...current, tag]);
  syncAudioTagPicker(button.closest("[data-audio-tag-picker]"));
}

function filterAudioFilterTags(searchInput) {
  const query = normalizeAudioTag(searchInput.value || "");
  document.querySelectorAll("[data-audio-filter-chip]").forEach((chip) => {
    const tag = normalizeAudioTag(chip.dataset.audioFilterChip || chip.textContent || "");
    const visible = !query || tag.includes(query);
    chip.hidden = !visible;
    chip.style.display = visible ? "" : "none";
  });
}

function audioFilterUrlFromState({ tagAction = null, tag = "", page = 1 } = {}) {
  const form = document.querySelector("[data-audio-filter-form]");
  const url = new URL(form?.action || window.location.href, window.location.origin);
  const query = form?.querySelector("[data-audio-search]")?.value.trim() || "";
  const category = form?.querySelector("[data-audio-category-filter]")?.value || "";
  const perPage = form?.querySelector("[data-audio-per-page-filter]")?.value || "";
  const included = new Set([...document.querySelectorAll("[data-audio-filter-chip].is-included")].map((chip) => chip.dataset.audioFilterChip));
  const excluded = new Set([...document.querySelectorAll("[data-audio-filter-chip].is-excluded")].map((chip) => chip.dataset.audioFilterChip));

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
  if (perPage) url.searchParams.set("per_page", perPage);
  if (page > 1) url.searchParams.set("page", String(page));
  [...included].forEach((item) => url.searchParams.append("tag", item));
  [...excluded].forEach((item) => url.searchParams.append("exclude_tag", item));
  return url.toString();
}

function openAudioLinkModal() {
  const modal = document.querySelector("[data-audio-link-modal]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => modal.querySelector('input[name="title"]')?.focus(), 30);
}

function closeAudioLinkModal() {
  const modal = document.querySelector("[data-audio-link-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector("[data-audio-taxonomy-modal].is-open, [data-audio-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function openAudioTaxonomyModal() {
  const modal = getAudioTaxonomyModal();
  if (!modal) return;
  setAudioTaxonomyTab(audioTaxonomyActiveTab);
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const toggle = document.querySelector("[data-toggle-audio-tags]");
  if (toggle) {
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
  }
  window.setTimeout(() => modal.querySelector("[data-audio-taxonomy-pane].is-active input")?.focus(), 30);
}

function closeAudioTaxonomyModal() {
  const modal = document.querySelector("[data-audio-taxonomy-modal]");
  if (!modal) return;
  closeAudioTagRenameModal();
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  const toggle = document.querySelector("[data-toggle-audio-tags]");
  if (toggle) {
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  }
  if (!document.querySelector("[data-audio-link-modal].is-open, [data-audio-track-modal].is-open, [data-audio-category-order-modal].is-open, [data-audio-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

async function openAudioTrackModal(trackId) {
  await closeAudioTrackModals();
  closeAudioLinkModal();
  const modal = document.querySelector(`[data-audio-track-modal="${CSS.escape(trackId)}"]`);
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function clearInitialAudioTrackFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("track")) return;
  url.searchParams.delete("track");
  window.history.replaceState({}, "", url.toString());
}

async function closeAudioTrackModals({ save = true } = {}) {
  const openForms = save
    ? [...document.querySelectorAll("[data-audio-track-modal].is-open [data-audio-track-form]")]
    : [];
  document.querySelectorAll("[data-audio-track-modal]").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  if (!document.querySelector("[data-audio-link-modal].is-open, [data-audio-taxonomy-modal].is-open, [data-audio-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
  clearInitialAudioTrackFromUrl();
  if (openForms.length) {
    await Promise.all(openForms.map((form) => submitAudioAjaxForm(form)));
  }
}

function openInitialAudioTrackModal() {
  const trackId = audioPage?.dataset.openAudioTrackId || "";
  if (!trackId) return;
  audioPage.dataset.openAudioTrackId = "";
  window.setTimeout(() => openAudioTrackModal(trackId), 40);
}

function openAudioCategoryOrderModal() {
  const modal = document.querySelector("[data-audio-category-order-modal]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  updateAudioCategoryOrderNumbers();
}

function closeAudioCategoryOrderModal() {
  const modal = document.querySelector("[data-audio-category-order-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector("[data-audio-link-modal].is-open, [data-audio-track-modal].is-open, [data-audio-taxonomy-modal].is-open, [data-audio-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function getAudioCategoryOrderItems() {
  return [...document.querySelectorAll("[data-audio-category-order-modal-item]")];
}

function updateAudioCategoryOrderNumbers() {
  getAudioCategoryOrderItems().forEach((item, index) => {
    const number = item.querySelector("[data-rule-order-number]");
    if (number) number.textContent = String(index + 1);
  });
}

async function saveAudioCategoryOrder() {
  const categories = getAudioCategoryOrderItems().map((item) => item.dataset.audioCategory);
  const endpoint = document.querySelector("[data-audio-tag-editor]")?.dataset.audioCategoryReorderUrl || "/audio/categories/reorder";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/json" },
    body: JSON.stringify({ categories }),
  });
  if (!response.ok) throw new Error("Audio category order was not saved.");
  await refreshAudioPage(window.location.href, false);
  showAudioToast("Порядок категорий сохранён");
}

function updateAudioSelection() {
  const selected = document.querySelectorAll('input[name="track_ids"]:checked').length;
  const count = document.querySelector("[data-audio-selected-count]");
  const bulkButton = document.querySelector("[data-hold-audio-bulk-delete]");
  if (count) count.textContent = String(selected);
  if (bulkButton) {
    bulkButton.disabled = selected === 0;
    if (selected === 0) resetAudioHoldButton(bulkButton);
  }
}

function resetAudioHoldButton(button) {
  if (!button) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  if (typeof releaseHoldDeleteButtonSize === "function") releaseHoldDeleteButtonSize(button);
  const label = button.querySelector("[data-hold-delete-label]");
  if (!label) return;
  label.textContent = button.matches("[data-hold-audio-bulk-delete]")
    ? "Удерживайте, чтобы удалить выбранные"
    : "Удерживайте, чтобы удалить";
}

function cancelAudioDeleteHold() {
  if (!activeAudioDeleteHold) return;
  window.clearTimeout(activeAudioDeleteHold.timeout);
  window.cancelAnimationFrame(activeAudioDeleteHold.frame);
  resetAudioHoldButton(activeAudioDeleteHold.button);
  activeAudioDeleteHold = null;
}

function startAudioDeleteHold(button) {
  const form = button.matches("[data-hold-audio-bulk-delete]")
    ? document.querySelector("#audio-delete-form")
    : button.closest("form");
  if (!form || button.disabled) return;
  if (button.matches("[data-hold-audio-bulk-delete]") && !document.querySelectorAll('input[name="track_ids"]:checked').length) {
    showAudioToast("Выберите треки для удаления");
    return;
  }
  cancelAudioDeleteHold();
  const duration = 1900;
  const startedAt = performance.now();
  const label = button.querySelector("[data-hold-delete-label]");
  if (typeof lockHoldDeleteButtonSize === "function") lockHoldDeleteButtonSize(button);
  button.classList.add("is-holding");
  if (label) label.textContent = "Держите...";

  const tick = () => {
    if (!activeAudioDeleteHold || activeAudioDeleteHold.button !== button) return;
    const progress = Math.min((performance.now() - startedAt) / duration, 1);
    button.style.setProperty("--hold-progress", String(progress));
    if (progress < 1) activeAudioDeleteHold.frame = window.requestAnimationFrame(tick);
  };

  activeAudioDeleteHold = {
    button,
    frame: window.requestAnimationFrame(tick),
    timeout: window.setTimeout(async () => {
      activeAudioDeleteHold = null;
      button.classList.remove("is-holding");
      button.style.setProperty("--hold-progress", "1");
      if (label) label.textContent = "Удаляю...";
      try {
        await submitAudioAjaxForm(form, button.matches("[data-hold-audio-bulk-delete]") ? "Треки удалены" : "Трек удалён");
        closeAudioTrackModals({ save: false });
      } catch {
        showAudioToast("Не удалось удалить трек");
        resetAudioHoldButton(button);
      }
    }, duration),
  };
}

document.addEventListener("change", (event) => {
  const fileInput = event.target.closest("[data-audio-file-input]");
  if (fileInput) {
    const count = fileInput.files.length;
    const fileCount = fileInput.closest("form")?.querySelector("[data-audio-file-count]");
    if (fileCount) fileCount.textContent = count ? `Выбрано треков: ${count}` : "MP3, WAV, OGG, FLAC, M4A, WEBM";
    return;
  }

  if (event.target.closest('input[name="track_ids"]')) {
    updateAudioSelection();
    return;
  }

  if (event.target.closest("[data-audio-category-filter], [data-audio-per-page-filter]")) {
    refreshAudioPage(audioFilterUrlFromState()).catch(() => showAudioToast("Не удалось применить фильтр"));
  }
});

document.addEventListener("input", (event) => {
  const tagManagerSearch = event.target.closest("[data-audio-tag-manager-search]");
  if (tagManagerSearch) {
    const query = tagManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-audio-tag-delete-form]").forEach((form) => {
      const tag = (form.dataset.audioTag || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !tag.includes(query);
    });
    return;
  }

  const categoryManagerSearch = event.target.closest("[data-audio-category-manager-search]");
  if (categoryManagerSearch) {
    const query = categoryManagerSearch.value.trim().toLocaleLowerCase("ru-RU");
    document.querySelectorAll("[data-audio-category-delete-form]").forEach((form) => {
      const category = (form.dataset.audioCategory || "").toLocaleLowerCase("ru-RU");
      form.hidden = query && !category.includes(query);
    });
    return;
  }

  const filterTagSearch = event.target.closest("[data-audio-filter-tag-search]");
  if (filterTagSearch) {
    filterAudioFilterTags(filterTagSearch);
    return;
  }

  if (!event.target.closest("[data-audio-search]")) return;
  window.clearTimeout(audioSearchTimer);
  audioSearchTimer = window.setTimeout(() => {
    refreshAudioPage(audioFilterUrlFromState()).catch(() => showAudioToast("Не удалось выполнить поиск"));
  }, 320);
});

document.addEventListener("click", async (event) => {
  const includeTag = event.target.closest("[data-audio-include-tag]");
  if (includeTag) {
    refreshAudioPage(audioFilterUrlFromState({ tagAction: "include", tag: includeTag.dataset.audioIncludeTag }))
      .catch(() => showAudioToast("Не удалось применить тег"));
    return;
  }

  const excludeTag = event.target.closest("[data-audio-exclude-tag]");
  if (excludeTag) {
    refreshAudioPage(audioFilterUrlFromState({ tagAction: "exclude", tag: excludeTag.dataset.audioExcludeTag }))
      .catch(() => showAudioToast("Не удалось исключить тег"));
    return;
  }

  if (event.target.closest("[data-audio-clear-filters]")) {
    refreshAudioPage(new URL("/audio", window.location.origin).toString()).catch(() => showAudioToast("Не удалось сбросить фильтры"));
    return;
  }

  const dynamicLink = event.target.closest("[data-audio-dynamic-link]");
  if (dynamicLink) {
    event.preventDefault();
    refreshAudioPage(dynamicLink.href).catch(() => showAudioToast("Не удалось открыть страницу"));
    return;
  }

  const tagToggle = event.target.closest("[data-toggle-audio-tags]");
  if (tagToggle) {
    const isOpen = document.querySelector("[data-audio-taxonomy-modal].is-open");
    if (isOpen) closeAudioTaxonomyModal();
    else openAudioTaxonomyModal();
    return;
  }

  if (event.target.closest("[data-close-audio-taxonomy]")) {
    closeAudioTaxonomyModal();
    return;
  }

  if (event.target.closest("[data-close-audio-tag-rename]")) {
    closeAudioTagRenameModal();
    return;
  }

  const renameTagButton = event.target.closest("[data-audio-rename-tag]");
  if (renameTagButton) {
    openAudioTagRename(renameTagButton);
    return;
  }

  const renameSaveButton = event.target.closest("[data-audio-rename-save]");
  if (renameSaveButton) {
    renameAudioTag(renameSaveButton).catch(() => showAudioToast("Не удалось переименовать тег"));
    return;
  }

  const renameCancelButton = event.target.closest("[data-audio-rename-cancel]");
  if (renameCancelButton) {
    closeAudioTagRename(renameCancelButton.closest("[data-audio-tag-delete-form]"));
    return;
  }

  const renameCategoryButton = event.target.closest("[data-audio-rename-category]");
  if (renameCategoryButton) {
    openAudioCategoryRename(renameCategoryButton);
    return;
  }

  const renameCategorySaveButton = event.target.closest("[data-audio-category-rename-save]");
  if (renameCategorySaveButton) {
    renameAudioCategory(renameCategorySaveButton).catch(() => showAudioToast("Не удалось переименовать категорию"));
    return;
  }

  const renameCategoryCancelButton = event.target.closest("[data-audio-category-rename-cancel]");
  if (renameCategoryCancelButton) {
    closeAudioCategoryRename(renameCategoryCancelButton.closest("[data-audio-category-delete-form]"));
    return;
  }

  const taxonomyTab = event.target.closest("[data-audio-taxonomy-tab]");
  if (taxonomyTab) {
    setAudioTaxonomyTab(taxonomyTab.dataset.audioTaxonomyTab);
    return;
  }

  if (event.target.closest("[data-open-audio-category-order]")) {
    audioTaxonomyActiveTab = "categories";
    openAudioCategoryOrderModal();
    return;
  }

  if (event.target.closest("[data-close-audio-category-order]")) {
    closeAudioCategoryOrderModal();
    return;
  }

  if (event.target.closest("[data-save-audio-category-order]")) {
    saveAudioCategoryOrder().then(closeAudioCategoryOrderModal).catch(() => showAudioToast("Не удалось сохранить порядок"));
    return;
  }

  if (event.target.closest("[data-open-audio-link-modal]")) {
    openAudioLinkModal();
    return;
  }

  const openTrackModal = event.target.closest("[data-open-audio-track-modal]");
  if (openTrackModal) {
    await openAudioTrackModal(openTrackModal.dataset.openAudioTrackModal);
    return;
  }

  if (event.target.closest("[data-close-audio-track-modal]")) {
    await closeAudioTrackModals();
    return;
  }

  const copyUrlButton = event.target.closest("[data-copy-audio-url]");
  if (copyUrlButton) {
    copyTextToClipboard(copyUrlButton.dataset.copyAudioUrl || "")
      .then(() => showAudioToast("Ссылка скопирована"))
      .catch(() => showAudioToast("Не удалось скопировать ссылку"));
    return;
  }

  if (event.target.closest("[data-close-audio-link-modal]")) {
    closeAudioLinkModal();
    return;
  }

  const pickedTag = event.target.closest("[data-audio-pick-tag]");
  if (pickedTag) {
    togglePickedAudioTag(pickedTag);
  }
});

document.addEventListener("submit", async (event) => {
  const filterForm = event.target.closest("[data-audio-filter-form]");
  if (filterForm) {
    event.preventDefault();
    await refreshAudioPage(audioFilterUrlFromState()).catch(() => showAudioToast("Не удалось применить фильтр"));
    return;
  }

  const deleteForm = event.target.closest("[data-audio-delete-form]");
  if (deleteForm) {
    const checked = document.querySelectorAll('input[name="track_ids"]:checked').length;
    if (!checked) {
      event.preventDefault();
      showAudioToast("Выберите треки для удаления");
      return;
    }
  }

  const tagDeleteForm = event.target.closest("[data-audio-tag-delete-form]");
  if (tagDeleteForm) {
    event.preventDefault();
    try {
      audioTaxonomyActiveTab = "tags";
      await submitAudioAjaxForm(tagDeleteForm, "Тег удалён");
      openAudioTaxonomyModal();
    } catch {
      showAudioToast("Не удалось удалить тег");
    }
    return;
  }

  const categoryDeleteForm = event.target.closest("[data-audio-category-delete-form]");
  if (categoryDeleteForm) {
    event.preventDefault();
    try {
      audioTaxonomyActiveTab = "categories";
      await submitAudioAjaxForm(categoryDeleteForm, "Категория удалена");
      openAudioTaxonomyModal();
    } catch {
      showAudioToast("Не удалось удалить категорию");
    }
    return;
  }

  const ajaxForm = event.target.closest("[data-audio-ajax-form], [data-audio-tag-create-form], [data-audio-category-create-form]");
  if (ajaxForm) {
    event.preventDefault();
    if (ajaxForm.matches("[data-audio-upload]") && !ajaxForm.querySelector("[data-audio-file-input]")?.files.length) {
      showAudioToast("Выберите аудиофайлы");
      return;
    }
    const submitButton = ajaxForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    const reopenTaxonomy = ajaxForm.matches("[data-audio-tag-create-form], [data-audio-category-create-form]");
    if (ajaxForm.matches("[data-audio-tag-create-form]")) audioTaxonomyActiveTab = "tags";
    if (ajaxForm.matches("[data-audio-category-create-form]")) audioTaxonomyActiveTab = "categories";
    try {
      const message = ajaxForm.matches("[data-audio-link-form]")
        ? "YouTube-трек создан"
        : ajaxForm.matches("[data-audio-track-form]")
          ? "Трек сохранён"
          : ajaxForm.matches("[data-audio-tag-create-form]")
            ? "Тег создан"
            : ajaxForm.matches("[data-audio-category-create-form]")
              ? "Категория создана"
              : ajaxForm.matches("[data-audio-delete-form]")
                ? "Треки удалены"
                : "Аудио загружено";
      await submitAudioAjaxForm(ajaxForm, message);
      if (reopenTaxonomy) openAudioTaxonomyModal();
      closeAudioLinkModal();
      if (ajaxForm.matches("[data-audio-track-form]")) closeAudioTrackModals({ save: false });
    } catch (error) {
      if (error.name !== "AudioValidationError") {
        showAudioToast("Запрос не выполнен");
      }
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
  }
});

document.addEventListener("pointerdown", (event) => {
  const holdButton = event.target.closest("[data-hold-audio-delete], [data-hold-audio-bulk-delete]");
  if (!holdButton) return;
  event.preventDefault();
  holdButton.setPointerCapture?.(event.pointerId);
  startAudioDeleteHold(holdButton);
});

["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    const holdButton = event.target.closest?.("[data-hold-audio-delete], [data-hold-audio-bulk-delete]");
    if (!holdButton || activeAudioDeleteHold?.button !== holdButton) return;
    cancelAudioDeleteHold();
  });
});

document.addEventListener("dragstart", (event) => {
  const item = event.target.closest("[data-audio-category-order-modal-item]");
  if (!item) return;
  draggedAudioCategoryItem = item;
  item.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", item.dataset.audioCategory || "");
});

document.addEventListener("dragover", (event) => {
  const targetItem = event.target.closest("[data-audio-category-order-modal-item]");
  if (!targetItem || !draggedAudioCategoryItem || targetItem === draggedAudioCategoryItem) return;
  event.preventDefault();
  const rect = targetItem.getBoundingClientRect();
  const after = event.clientY > rect.top + rect.height / 2;
  targetItem.parentElement.insertBefore(draggedAudioCategoryItem, after ? targetItem.nextSibling : targetItem);
  updateAudioCategoryOrderNumbers();
});

document.addEventListener("dragend", () => {
  if (!draggedAudioCategoryItem) return;
  draggedAudioCategoryItem.classList.remove("is-dragging");
  draggedAudioCategoryItem = null;
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-audio-filter-tag-search]")) {
    event.preventDefault();
    return;
  }

  const renameInput = event.target.closest("[data-audio-rename-input]");
  if (renameInput && event.key === "Enter") {
    event.preventDefault();
    await renameAudioTag(renameInput).catch(() => showAudioToast("Не удалось переименовать тег"));
    return;
  }

  if (renameInput && event.key === "Escape") {
    event.preventDefault();
    closeAudioTagRenameModal();
    return;
  }

  const categoryRenameInput = event.target.closest("[data-audio-category-rename-input]");
  if (categoryRenameInput && event.key === "Enter") {
    event.preventDefault();
    await renameAudioCategory(categoryRenameInput).catch(() => showAudioToast("Не удалось переименовать категорию"));
    return;
  }

  if (categoryRenameInput && event.key === "Escape") {
    event.preventDefault();
    closeAudioCategoryRename(categoryRenameInput.closest("[data-audio-category-delete-form]"));
    return;
  }

  if (event.key === "Escape") {
    closeAudioLinkModal();
    closeAudioTaxonomyModal();
    closeAudioTagRenameModal();
    await closeAudioTrackModals();
    closeAudioCategoryOrderModal();
  }
});

window.addEventListener("popstate", () => {
  refreshAudioPage(window.location.href, false).catch(() => window.location.reload());
});

openInitialAudioTrackModal();
