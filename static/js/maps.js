const uploadForm = document.querySelector("[data-dropzone]");
const fileInput = document.querySelector("[data-file-input]");
const fileCount = document.querySelector("[data-file-count]");
const batchTagsInput = document.querySelector("[data-batch-tags-input]");
const singleTitleInput = document.querySelector("[data-single-title-input]");
const uploadSingleTitleWrap = document.querySelector("[data-upload-single-title-wrap]");
const uploadSingleTitle = document.querySelector("[data-upload-single-title]");
let uploadModeKicker = document.querySelector("[data-upload-mode-kicker]");
let uploadModeTitle = document.querySelector("[data-upload-mode-title]");
let uploadModeDescription = document.querySelector("[data-upload-mode-description]");
const loadingOverlay = document.querySelector("[data-maps-loading]");
let uploadModal = document.querySelector("[data-upload-modal]");
let uploadTagsText = document.querySelector("[data-upload-tags-text]");
const toast = document.querySelector("[data-copy-toast]");
const serviceTag = document.querySelector("[data-maps-board]")?.dataset.serviceMapTag || "Неотсортированные";

let selectModeEnabled = false;
let includedMapTags = new Set((document.querySelector("[data-maps-board]")?.dataset.activeTags || "").split("||").filter(Boolean).map(normalizeTag));
let excludedMapTags = new Set((document.querySelector("[data-maps-board]")?.dataset.excludedTags || "").split("||").filter(Boolean).map(normalizeTag));
let pendingMapTagDeleteForm = null;
let pendingMapTagRenameForm = null;
let mapSearchTimer = null;
let mapsRefreshToken = 0;

function mapSettingsSnapshot(form) {
  if (!form) return "";
  const tags = tagsFromInput(form.querySelector("input[name='tags']"))
    .map(normalizeTag)
    .sort();
  return JSON.stringify({
    title: String(form.querySelector("input[name='title']")?.value || "").trim(),
    tags,
  });
}

function markMapSettingsClean(form) {
  if (!form) return;
  form.dataset.initialMapSettings = mapSettingsSnapshot(form);
}

function isMapSettingsDirty(form) {
  return Boolean(form) && form.dataset.initialMapSettings !== mapSettingsSnapshot(form);
}

function layoutMasonryBoard() {
  const board = document.querySelector("[data-maps-board]");
  if (!board) return;
  const styles = window.getComputedStyle(board);
  const rowHeight = Number.parseFloat(styles.getPropertyValue("grid-auto-rows")) || 8;
  const rowGap = Number.parseFloat(styles.getPropertyValue("row-gap")) || 0;

  board.querySelectorAll("[data-map-tile]").forEach((tile) => {
    if (tile.style.display === "none" || tile.hidden) return;
    tile.style.setProperty("--tile-rows", "1");
    const span = Math.ceil((tile.getBoundingClientRect().height + rowGap) / (rowHeight + rowGap));
    tile.style.setProperty("--tile-rows", String(Math.max(span, 1)));
  });
}

function normalizeTag(tag) {
  return tag.trim().toLocaleLowerCase("ru-RU");
}

function displayMapTagsFromSet(tagSet) {
  const tags = [];
  document.querySelectorAll("[data-map-filter-chip]").forEach((chip) => {
    if (tagSet.has(normalizeTag(chip.dataset.mapFilterChip))) tags.push(chip.dataset.mapFilterChip);
  });
  return tags;
}

function updateMapFilterChips() {
  const hasFilters = includedMapTags.size > 0 || excludedMapTags.size > 0;
  document.querySelectorAll("[data-map-filter-chip]").forEach((chip) => {
    const tag = normalizeTag(chip.dataset.mapFilterChip);
    chip.classList.toggle("is-included", includedMapTags.has(tag));
    chip.classList.toggle("is-excluded", excludedMapTags.has(tag));
    chip.classList.toggle("is-muted", hasFilters && !includedMapTags.has(tag) && !excludedMapTags.has(tag));
  });
}

function mapFilterUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("tag");
  url.searchParams.delete("exclude_tag");
  url.searchParams.delete("page");
  displayMapTagsFromSet(includedMapTags).forEach((tag) => url.searchParams.append("tag", tag));
  displayMapTagsFromSet(excludedMapTags).forEach((tag) => url.searchParams.append("exclude_tag", tag));
  return url.toString();
}

function mapFilterUrlFromState({ reset = false, page = 1 } = {}) {
  const form = document.querySelector("[data-map-filter-form]");
  const action = form?.action || window.location.href;
  const url = new URL(action, window.location.origin);

  if (!reset) {
    const q = form?.querySelector("[data-map-search]")?.value.trim() || "";
    const perPage = document.querySelector("[data-maps-per-page]")?.value || form?.querySelector('input[name="per_page"]')?.value || "";
    const campaign = form?.querySelector('input[name="campaign"]')?.value || "";
    if (campaign) url.searchParams.set("campaign", campaign);
    if (q) url.searchParams.set("q", q);
    if (perPage) url.searchParams.set("per_page", perPage);
    if (page > 1) url.searchParams.set("page", String(page));
    displayMapTagsFromSet(includedMapTags).forEach((tag) => url.searchParams.append("tag", tag));
    displayMapTagsFromSet(excludedMapTags).forEach((tag) => url.searchParams.append("exclude_tag", tag));
  } else {
    const campaign = form?.querySelector('input[name="campaign"]')?.value || "";
    if (campaign) url.searchParams.set("campaign", campaign);
  }
  return url.toString();
}

function syncMapFilterStateFromBoard() {
  const board = document.querySelector("[data-maps-board]");
  if (board) {
    includedMapTags = new Set((board.dataset.activeTags || "").split("||").filter(Boolean).map(normalizeTag));
    excludedMapTags = new Set((board.dataset.excludedTags || "").split("||").filter(Boolean).map(normalizeTag));
  } else {
    includedMapTags = new Set([...document.querySelectorAll("[data-map-filter-chip].is-included")].map((chip) => normalizeTag(chip.dataset.mapFilterChip)));
    excludedMapTags = new Set([...document.querySelectorAll("[data-map-filter-chip].is-excluded")].map((chip) => normalizeTag(chip.dataset.mapFilterChip)));
  }
  updateMapFilterChips();
}

function tagsFromInput(input) {
  return input.value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function syncTagButtons(input) {
  const container = input.closest("form, [data-upload-modal]");
  if (!container) return;

  const activeTags = new Set(tagsFromInput(input).map(normalizeTag));
  container.querySelectorAll("[data-insert-tag], [data-upload-tag]").forEach((button) => {
    const tag = button.dataset.insertTag || button.dataset.uploadTag || "";
    button.classList.toggle("is-active", activeTags.has(normalizeTag(tag)));
  });
}

function filterMapTagPicker(searchInput) {
  const container = searchInput.closest(".map-modal-form, .upload-modal-dialog")?.querySelector(".map-modal-tags");
  if (!container) return;
  const query = normalizeTag(searchInput.value || "");
  container.querySelectorAll("button").forEach((button) => {
    const tag = normalizeTag(button.dataset.insertTag || button.dataset.uploadTag || button.textContent || "");
    button.hidden = Boolean(query) && !tag.includes(query);
  });
}

function filterMapFilterTags(searchInput) {
  const query = normalizeTag(searchInput.value || "");
  document.querySelectorAll("[data-map-filter-chip]").forEach((chip) => {
    const tag = normalizeTag(chip.dataset.mapFilterChip || chip.textContent || "");
    const visible = !query || tag.includes(query);
    chip.hidden = !visible;
    chip.style.display = visible ? "" : "none";
  });
}

function filterMapTaxonomyTags(searchInput) {
  const query = normalizeTag(searchInput.value || "");
  const manager = searchInput.closest(".map-tag-manager");
  const list = manager?.querySelector("[data-map-tag-order-list]");
  if (!list) return;
  list.querySelectorAll("[data-map-tag-order-item]").forEach((item) => {
    const tag = normalizeTag(item.dataset.mapTag || item.textContent || "");
    item.hidden = Boolean(query) && !tag.includes(query);
  });
}

function setInputTags(input, tags) {
  const seen = new Set();
  const normalizedTags = [];
  tags.forEach((tag) => {
    const cleanTag = tag.trim();
    const key = normalizeTag(cleanTag);
    if (cleanTag && !seen.has(key)) {
      seen.add(key);
      normalizedTags.push(cleanTag);
    }
  });

  const regularTags = normalizedTags.filter((tag) => normalizeTag(tag) !== normalizeTag(serviceTag));
  input.value = (regularTags.length ? regularTags : [serviceTag]).join(", ");
  syncTagButtons(input);
}

function toggleMapTag(input, tag) {
  if (normalizeTag(tag) === normalizeTag(serviceTag)) {
    setInputTags(input, [serviceTag]);
    return;
  }

  const currentRegularTags = tagsFromInput(input).filter((item) => normalizeTag(item) !== normalizeTag(serviceTag));
  const hasTag = currentRegularTags.some((item) => normalizeTag(item) === normalizeTag(tag));
  const nextTags = hasTag
    ? currentRegularTags.filter((item) => normalizeTag(item) !== normalizeTag(tag))
    : [...currentRegularTags, tag];

  setInputTags(input, nextTags);
}

function addTagToInput(input, tag) {
  const tags = tagsFromInput(input);
  const knownTags = new Set(tags.map(normalizeTag));
  if (!knownTags.has(normalizeTag(tag))) {
    tags.push(tag);
  }
  input.value = tags.join(", ");
  syncTagButtons(input);
}

function setSingleTitleVisibility(isVisible) {
  if (!uploadSingleTitleWrap) return;
  uploadSingleTitleWrap.hidden = !isVisible;
  uploadSingleTitleWrap.style.display = isVisible ? "grid" : "none";
}

function updateUploadModalTexts(isSingle) {
  if (uploadModeKicker) uploadModeKicker.textContent = isSingle ? "Одиночная загрузка" : "Пакетная загрузка";
  if (uploadModeTitle) uploadModeTitle.textContent = isSingle ? "Настройте карточку изображения" : "Назначьте теги всем выбранным изображениям";
  if (uploadModeDescription) {
    uploadModeDescription.textContent = isSingle
      ? "Вы можете задать название карточки и выбрать теги для изображения. Если теги не выбрать, оно попадёт в “Неотсортированные”."
      : "Выберите теги, которые будут применены ко всем загружаемым изображениям. Если ничего не выбрать, они попадут в “Неотсортированные”.";
  }
}

function updateFileCount() {
  if (!fileInput?.files.length) {
    fileCount.textContent = "PNG, JPG, WEBP, GIF, AVIF";
    setSingleTitleVisibility(false);
    if (uploadSingleTitle) uploadSingleTitle.value = "";
    if (singleTitleInput) singleTitleInput.value = "";
    return;
  }

  fileCount.textContent = `Выбрано файлов: ${fileInput.files.length}`;
  const isSingle = fileInput.files.length === 1;
  setSingleTitleVisibility(isSingle);
  updateUploadModalTexts(isSingle);
  if (!isSingle) {
    if (uploadSingleTitle) uploadSingleTitle.value = "";
    if (singleTitleInput) singleTitleInput.value = "";
    return;
  }
  const filename = fileInput.files[0]?.name || "";
  const stem = filename.includes(".") ? filename.slice(0, filename.lastIndexOf(".")) : filename;
  if (uploadSingleTitle && !uploadSingleTitle.value.trim()) {
    uploadSingleTitle.value = stem;
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.setTimeout(() => toast.classList.remove("is-visible"), 1600);
}

function syncMapBodyModalState() {
  const hasOpenModal = Boolean(document.querySelector(
    "[data-map-modal].is-open, [data-map-taxonomy-modal].is-open, [data-map-tag-rename-modal].is-open, [data-map-tag-delete-modal].is-open, [data-upload-modal].is-open"
  ));
  document.body.classList.toggle("has-modal", hasOpenModal);
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
  if (blob.type === "image/png") {
    return blob;
  }

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
      else reject(new Error("Не удалось подготовить PNG для буфера обмена."));
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

  if (!copied) {
    throw new Error("Legacy image copy failed.");
  }
}

async function copyPngBlobViaServer(pngBlob) {
  const formData = new FormData();
  formData.append("image", pngBlob, "clipboard.png");
  await window.startLocalJob("/clipboard/copy-image", { method: "POST", body: formData });
}

async function copyImageToClipboard(imageUrl) {
  if (!imageUrl) {
    throw new Error("Image URL is empty.");
  }
  const response = await fetch(imageUrl);
  const sourceBlob = await response.blob();
  const pngBlob = await blobToPng(sourceBlob);

  if (navigator.clipboard?.write && typeof ClipboardItem !== "undefined" && window.isSecureContext) {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ [pngBlob.type]: pngBlob }),
      ]);
      return;
    } catch {
      // Some Chromium builds expose ClipboardItem but reject image writes on local HTTP origins.
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
  const formData = new FormData();
  formData.append("scope", document.querySelector("input[name='scope']")?.value || "shared");
  formData.append("campaign_slug", document.querySelector("input[name='campaign_slug']")?.value || "");
  await window.startLocalJob(copyImageUrl, {
    method: "POST",
    body: formData,
  });
}

function shouldCopyImageInBrowser(imageUrl) {
  const cleanUrl = String(imageUrl || "").split("?", 1)[0].toLocaleLowerCase("ru-RU");
  return cleanUrl.endsWith(".webp") || cleanUrl.endsWith(".avif");
}

async function copyMapImage(copyImageUrl, browserImageUrl) {
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

function setLoading(isLoading) {
  loadingOverlay.hidden = !isLoading;
}

function openMapTagEditor() {
  const modal = document.querySelector("[data-map-taxonomy-modal]");
  const toggle = document.querySelector("[data-toggle-tag-editor]");
  if (!modal) return;
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  if (toggle) {
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
  }
  window.setTimeout(() => modal.querySelector("[data-map-tag-create-input]")?.focus(), 40);
}

function closeMapTagEditor() {
  const modal = document.querySelector("[data-map-taxonomy-modal]");
  const toggle = document.querySelector("[data-toggle-tag-editor]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  document.querySelectorAll("[data-map-tag-order-item].is-renaming").forEach(closeMapTagRename);
  closeMapTagRenameModal();
  if (toggle) {
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  }
  syncMapBodyModalState();
}

function removeBodyMapTagEditorModal() {
  document.querySelectorAll("body > [data-map-taxonomy-modal]").forEach((modal) => modal.remove());
  document.querySelectorAll("body > [data-map-tag-rename-modal]").forEach((modal) => modal.remove());
}

async function loadMapsFragment(url, pushState = true, options = {}) {
  const refreshToken = ++mapsRefreshToken;
  const { showLoading = true, preserveFocus = false } = options;
  const activeInput = preserveFocus
    ? document.activeElement?.closest?.("[data-map-search], [data-map-filter-tag-search]")
    : null;
  const focusState = activeInput
    ? {
        selector: activeInput.matches("[data-map-search]") ? "[data-map-search]" : "[data-map-filter-tag-search]",
        value: activeInput.value || "",
        start: activeInput.selectionStart ?? null,
        end: activeInput.selectionEnd ?? null,
      }
    : null;

  if (showLoading) setLoading(true);
  const current = document.querySelector("[data-maps-dynamic]");
  if (current) current.style.minHeight = `${current.offsetHeight}px`;
  try {
    const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    const html = await response.text();
    if (refreshToken !== mapsRefreshToken) return;
    const documentFragment = new DOMParser().parseFromString(html, "text/html");
    const incoming = documentFragment.querySelector("[data-maps-dynamic]");
    if (incoming && current) {
      const latestFocusState = focusState
        ? (() => {
            const liveInput = document.querySelector(focusState.selector);
            return liveInput
              ? {
                  ...focusState,
                  value: liveInput.value || "",
                  start: liveInput.selectionStart ?? focusState.start,
                  end: liveInput.selectionEnd ?? focusState.end,
                }
              : focusState;
          })()
        : null;
      removeBodyMapTagEditorModal();
      current.replaceWith(incoming);
      const freshUploadModal = documentFragment.querySelector("[data-upload-modal]");
      if (freshUploadModal && uploadModal) {
        uploadModal.replaceWith(freshUploadModal);
        uploadModal = freshUploadModal;
        uploadTagsText = uploadModal.querySelector("[data-upload-tags-text]");
        uploadModeKicker = uploadModal.querySelector("[data-upload-mode-kicker]");
        uploadModeTitle = uploadModal.querySelector("[data-upload-mode-title]");
        uploadModeDescription = uploadModal.querySelector("[data-upload-mode-description]");
      }
      closeMapModals({ save: false, refresh: false });
      setSelectMode(false);
      syncMapFilterStateFromBoard();
      window.requestAnimationFrame(() => {
        layoutMasonryBoard();
        const next = document.querySelector("[data-maps-dynamic]");
        if (next) next.style.minHeight = "";
      });
      if (latestFocusState) {
        const nextInput = document.querySelector(latestFocusState.selector);
        if (nextInput) {
          nextInput.value = latestFocusState.value;
          if (latestFocusState.selector === "[data-map-filter-tag-search]") {
            filterMapFilterTags(nextInput);
          }
          nextInput.focus();
          if (typeof latestFocusState.start === "number" && typeof latestFocusState.end === "number") {
            nextInput.setSelectionRange(latestFocusState.start, latestFocusState.end);
          }
        }
      }
      document.querySelectorAll("[data-map-tile] img").forEach((image) => {
        if (image.complete) return;
        image.addEventListener("load", layoutMasonryBoard, { once: true });
      });
      if (pushState) window.history.pushState({}, "", url);
    } else {
      window.location.href = url;
    }
  } finally {
    if (showLoading && refreshToken === mapsRefreshToken) setLoading(false);
  }
}

async function renameMapTag(button) {
  const form = button.closest("[data-map-tag-order-item]") || pendingMapTagRenameForm;
  const oldTag = form?.dataset.mapTag || "";
  const input = button.closest("[data-map-tag-rename-modal]")?.querySelector("[data-map-rename-input]") || form?.querySelector("[data-map-rename-input]");
  const cleanTag = (input?.value || "").trim();
  if (!oldTag || !cleanTag || cleanTag.toLocaleLowerCase("ru-RU") === oldTag.toLocaleLowerCase("ru-RU")) {
    closeMapTagRename(form);
    return;
  }
  const editorPanel = form?.closest("[data-tag-editor]") || document.querySelector("[data-tag-editor]");
  const url = editorPanel?.dataset.mapTagRenameUrl || "";
  if (!url) return;
  const formData = new FormData();
  formData.append("scope", form.querySelector('input[name="scope"]')?.value || "shared");
  formData.append("campaign_slug", form.querySelector('input[name="campaign_slug"]')?.value || "");
  formData.append("tag", oldTag);
  formData.append("new_tag", cleanTag);
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Requested-With": "fetch", "Accept": "application/json" },
    body: formData,
  });
  if (!response.ok) {
    showToast("Не удалось переименовать тег");
    return;
  }
  await loadMapsFragment(window.location.href, false, { showLoading: false });
  pendingMapTagRenameForm = null;
  closeMapTagRenameModal();
  showToast("Тег переименован");
  openMapTagEditor();
}

function openMapTagRename(button) {
  const form = button.closest("[data-map-tag-order-item]");
  if (!form) return;
  openMapTagRenameModal(form);
}

function closeMapTagRename(form) {
  const targetForm = form || pendingMapTagRenameForm;
  targetForm?.classList.remove("is-renaming");
  pendingMapTagRenameForm = null;
  closeMapTagRenameModal();
}

async function saveMapSettingsForm(form) {
  if (!form) return null;
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  if (!response.ok) throw new Error("Map was not saved.");
  const payload = await response.json();
  if (payload?.map) syncMapView(form, payload.map);
  markMapSettingsClean(form);
  return payload;
}

function mapItemMatchesCurrentView(map) {
  const tags = new Set((map.tags || []).map(normalizeTag));
  const hasRequiredTags = [...includedMapTags].every((tag) => tags.has(tag));
  const hasExcludedTags = [...excludedMapTags].some((tag) => tags.has(tag));
  const query = String(document.querySelector("[data-map-search]")?.value || "").trim().toLocaleLowerCase("ru-RU");
  const haystack = [
    map.title || "",
    map.filename || "",
    ...(map.tags || []),
  ].join(" ").toLocaleLowerCase("ru-RU");
  const matchesSearch = query.length < 3 || haystack.includes(query);
  return hasRequiredTags && !hasExcludedTags && matchesSearch;
}

function syncMapView(form, map) {
  if (!form || !map?.id) return;
  const modal = form.closest("[data-map-modal]");
  const tags = map.tags || [serviceTag];
  const tagsText = tags.join(" · ");
  const foundryPath = map.foundry_path || "";

  modal?.querySelector(".map-modal-heading h2")?.replaceChildren(document.createTextNode(map.title || ""));
  modal?.setAttribute("aria-label", `Настройки: ${map.title || ""}`);
  const modalTitleInput = modal?.querySelector("input[name='title']");
  const modalTagsInput = modal?.querySelector("input[name='tags']");
  if (modalTitleInput) modalTitleInput.value = map.title || "";
  if (modalTagsInput) {
    modalTagsInput.value = tags.join(", ");
    syncTagButtons(modalTagsInput);
  }
  const modalImage = modal?.querySelector(".map-modal-preview img");
  if (modalImage) modalImage.alt = map.title || "";

  const openButton = document.querySelector(`[data-open-map-modal="${CSS.escape(map.id)}"]`);
  const tile = openButton?.closest("[data-map-tile]");
  if (tile) {
    tile.dataset.tags = tags.join("||");
    tile.hidden = false;
    tile.style.display = mapItemMatchesCurrentView(map) ? "" : "none";
    tile.querySelector(".map-caption strong")?.replaceChildren(document.createTextNode(map.title || ""));
    tile.querySelector(".map-caption span")?.replaceChildren(document.createTextNode(tagsText));
    const image = tile.querySelector(".map-image-wrap img");
    if (image) image.alt = map.title || "";
  }

  if (openButton) openButton.setAttribute("aria-label", `Открыть настройки ${map.title || ""}`);
  document.querySelectorAll(`[data-copy-path], [data-copy-map-image], [data-demo-show]`).forEach((button) => {
    const ownerTile = button.closest("[data-map-tile]");
    if (ownerTile !== tile) return;
    if (foundryPath) button.dataset.copyFoundryPath = foundryPath;
    if (button.matches("[data-copy-path]")) {
      button.setAttribute("aria-label", `Скопировать Foundry-путь ${map.title || ""}.`);
    }
    if (button.matches("[data-copy-map-image]")) {
      button.setAttribute("aria-label", `Скопировать изображение ${map.title || ""}`);
    }
    if (button.matches("[data-demo-show]")) {
      button.setAttribute("aria-label", `Показать ${map.title || ""} на экране демонстрации`);
    }
  });

  if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
  window.requestAnimationFrame(layoutMasonryBoard);
}

async function closeMapModals({ save = true, refresh = true } = {}) {
  const openForms = save
    ? [...document.querySelectorAll("[data-map-modal].is-open [data-map-settings-form]")].filter(isMapSettingsDirty)
    : [];
  document.querySelectorAll("[data-map-modal]").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  syncMapBodyModalState();
  if (openForms.length) {
    await Promise.all(openForms.map((form) => saveMapSettingsForm(form)));
    if (refresh) window.requestAnimationFrame(layoutMasonryBoard);
  }
}

async function openMapModal(mapId) {
  await closeMapModals();
  const modal = document.querySelector(`[data-map-modal="${mapId}"]`);
  if (!modal) return;

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  const tagsInput = modal.querySelector("input[name='tags']");
  if (tagsInput) {
    setInputTags(tagsInput, tagsFromInput(tagsInput));
  }
  markMapSettingsClean(modal.querySelector("[data-map-settings-form]"));
  window.setTimeout(() => modal.querySelector("input[name='title']")?.focus(), 40);
}

function openUploadModal() {
  if (!fileInput?.files.length) {
    fileInput?.click();
    return;
  }
  const isSingle = fileInput.files.length === 1;
  setSingleTitleVisibility(isSingle);
  updateUploadModalTexts(isSingle);
  if (!isSingle && uploadSingleTitle) uploadSingleTitle.value = "";

  uploadModal.classList.add("is-open");
  uploadModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  syncTagButtons(uploadTagsText);
  if (!uploadSingleTitleWrap?.hidden) {
    uploadSingleTitle?.focus();
    uploadSingleTitle?.select();
  } else {
    uploadTagsText.focus();
  }
}

function closeUploadModal({ resetFiles = true } = {}) {
  uploadModal.classList.remove("is-open");
  uploadModal.setAttribute("aria-hidden", "true");
  syncMapBodyModalState();
  if (resetFiles && fileInput) {
    fileInput.value = "";
    updateFileCount();
  }
}

function selectedMapIds() {
  return [...document.querySelectorAll("[data-map-select]")]
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function setSelectMode(isEnabled) {
  selectModeEnabled = isEnabled;
  document.body.classList.toggle("is-selecting-maps", isEnabled);
  document.querySelector("[data-toggle-select-mode]")?.classList.toggle("is-active", isEnabled);
  document.querySelector("[data-toggle-select-mode]")?.setAttribute("aria-expanded", String(isEnabled));
  const bulkDeleteForm = document.querySelector("[data-bulk-delete-form]");
  if (bulkDeleteForm) bulkDeleteForm.hidden = !isEnabled;

  if (!isEnabled) {
    document.querySelectorAll("[data-map-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-map-tile]")?.classList.remove("is-selected");
    });
  }
  updateBulkDeleteState();
}

function updateBulkDeleteState() {
  const ids = selectedMapIds();
  const selectedCount = document.querySelector("[data-selected-count]");
  const bulkDeleteButton = document.querySelector("[data-bulk-delete-button]");
  const bulkDeleteBar = document.querySelector("[data-bulk-delete-bar]");
  const bulkDeleteInputs = document.querySelector("[data-bulk-delete-inputs]");

  if (selectedCount) selectedCount.textContent = String(ids.length);
  if (bulkDeleteButton) bulkDeleteButton.disabled = ids.length === 0;
  if (bulkDeleteBar) bulkDeleteBar.hidden = !selectModeEnabled;
  if (bulkDeleteInputs) {
    bulkDeleteInputs.innerHTML = "";
    ids.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "map_ids";
      input.value = id;
      bulkDeleteInputs.appendChild(input);
    });
  }
}

function getMapTagOrderItems() {
  return [...document.querySelectorAll("[data-map-tag-order-item]")];
}

function openMapTagDeleteModal(form) {
  const tag = form?.dataset.mapTag || "";
  const modal = document.querySelector("[data-map-tag-delete-modal]");
  if (!modal || !tag || normalizeTag(tag) === normalizeTag(serviceTag)) return;
  const mediaTitle = document.querySelector("[data-maps-board]")?.dataset.mediaTitleAccusative || "карты";
  pendingMapTagDeleteForm = form;
  modal.querySelector("[data-map-tag-delete-title]").textContent = `Удалить «${tag}»?`;
  modal.querySelector("[data-map-tag-delete-message]").textContent = `Тег «${tag}» будет снят со всех записей. Если у записи не останется других тегов, она попадёт в «${serviceTag}». Раздел: ${mediaTitle}.`;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeMapTagDeleteModal() {
  const modal = document.querySelector("[data-map-tag-delete-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  pendingMapTagDeleteForm = null;
  syncMapBodyModalState();
}

function openMapTagRenameModal(form) {
  const tag = form?.dataset.mapTag || "";
  const modal = document.querySelector("[data-map-tag-rename-modal]");
  if (!modal || !tag || normalizeTag(tag) === normalizeTag(serviceTag)) return;
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  pendingMapTagRenameForm = form;
  modal.querySelector("[data-map-tag-rename-title]").textContent = `Переименовать «${tag}»`;
  const input = modal.querySelector("[data-map-rename-input]");
  if (input) input.value = tag;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeMapTagRenameModal() {
  const modal = document.querySelector("[data-map-tag-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  pendingMapTagRenameForm?.classList.remove("is-renaming");
  pendingMapTagRenameForm = null;
  const input = modal.querySelector("[data-map-rename-input]");
  if (input) input.value = "";
  syncMapBodyModalState();
}

async function confirmMapTagDelete() {
  if (!pendingMapTagDeleteForm) return;
  const form = pendingMapTagDeleteForm;
  const tag = form.dataset.mapTag || "";
  const button = document.querySelector("[data-confirm-map-tag-delete-action]");
  if (button) button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Map tag was not deleted.");
    includedMapTags.delete(normalizeTag(tag));
    excludedMapTags.delete(normalizeTag(tag));
    closeMapTagDeleteModal();
    await loadMapsFragment(mapFilterUrl(), false);
  } catch {
    window.alert("Не удалось удалить тег. Попробуйте ещё раз.");
  } finally {
    if (button) button.disabled = false;
  }
}

fileInput?.addEventListener("change", () => {
  updateFileCount();
  if (fileInput.files.length) {
    openUploadModal();
  }
});

uploadForm?.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadForm.classList.add("is-dragging");
});

uploadForm?.addEventListener("dragleave", () => {
  uploadForm.classList.remove("is-dragging");
});

uploadForm?.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadForm.classList.remove("is-dragging");
  fileInput.files = event.dataTransfer.files;
  updateFileCount();
  openUploadModal();
});

document.addEventListener("click", async (event) => {
  const includeTagButton = event.target.closest("[data-map-include-tag]");
  if (includeTagButton) {
    const tag = normalizeTag(includeTagButton.dataset.mapIncludeTag);
    includedMapTags.has(tag) ? includedMapTags.delete(tag) : (includedMapTags.add(tag), excludedMapTags.delete(tag));
    updateMapFilterChips();
    await loadMapsFragment(mapFilterUrlFromState());
    return;
  }

  const excludeTagButton = event.target.closest("[data-map-exclude-tag]");
  if (excludeTagButton) {
    const tag = normalizeTag(excludeTagButton.dataset.mapExcludeTag);
    excludedMapTags.has(tag) ? excludedMapTags.delete(tag) : (excludedMapTags.add(tag), includedMapTags.delete(tag));
    updateMapFilterChips();
    await loadMapsFragment(mapFilterUrlFromState());
    return;
  }

  if (event.target.closest("[data-map-clear-filters]")) {
    includedMapTags.clear();
    excludedMapTags.clear();
    const searchInput = document.querySelector("[data-map-search]");
    if (searchInput) searchInput.value = "";
    const filterTagSearchInput = document.querySelector("[data-map-filter-tag-search]");
    if (filterTagSearchInput) filterTagSearchInput.value = "";
    updateMapFilterChips();
    await loadMapsFragment(mapFilterUrlFromState({ reset: true }));
    return;
  }

  if (event.target.closest("[data-close-map-tag-delete]")) {
    closeMapTagDeleteModal();
    return;
  }

  if (event.target.closest("[data-close-map-tag-rename]")) {
    closeMapTagRenameModal();
    return;
  }

  if (event.target.closest("[data-close-map-taxonomy]")) {
    closeMapTagEditor();
    return;
  }

  if (event.target.closest("[data-confirm-map-tag-delete-action]")) {
    confirmMapTagDelete();
    return;
  }


  const dynamicLink = event.target.closest("[data-dynamic-link]");
  if (dynamicLink) {
    event.preventDefault();
    await loadMapsFragment(dynamicLink.href);
    return;
  }

  const tagEditorToggle = event.target.closest("[data-toggle-tag-editor]");
  if (tagEditorToggle) {
    const modal = document.querySelector("[data-map-taxonomy-modal]");
    if (modal?.classList.contains("is-open")) {
      closeMapTagEditor();
    } else {
      openMapTagEditor();
    }
    return;
  }

  const renameMapTagButton = event.target.closest("[data-map-rename-tag]");
  if (renameMapTagButton) {
    openMapTagRename(renameMapTagButton);
    return;
  }

  const renameMapTagSaveButton = event.target.closest("[data-map-rename-save]");
  if (renameMapTagSaveButton) {
    renameMapTag(renameMapTagSaveButton).catch(() => showToast("Не удалось переименовать тег"));
    return;
  }

  const renameMapTagCancelButton = event.target.closest("[data-map-rename-cancel]");
  if (renameMapTagCancelButton) {
    closeMapTagRename(renameMapTagCancelButton.closest("[data-map-tag-order-item]"));
    return;
  }

  if (event.target.closest("[data-toggle-select-mode]")) {
    setSelectMode(!selectModeEnabled);
    return;
  }

  if (event.target.closest("[data-clear-selection]")) {
    document.querySelectorAll("[data-map-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-map-tile]")?.classList.remove("is-selected");
    });
    updateBulkDeleteState();
    return;
  }

  const copyButton = event.target.closest("[data-copy-path]");
  if (copyButton) {
    const foundryPath = copyButton.dataset.copyFoundryPath;
    if (foundryPath) {
      await copyTextToClipboard(foundryPath);
      showToast("Foundry-путь скопирован");
      return;
    }
    showToast("Foundry-путь не настроен");
    return;
  }

  const imageCopyButton = event.target.closest("[data-copy-map-image]");
  if (imageCopyButton) {
    try {
      showToast("Готовлю изображение...");
      await copyMapImage(imageCopyButton.dataset.copyImageUrl, imageCopyButton.dataset.browserImageUrl);
      showToast("Изображение скопировано");
    } catch {
      showToast("Не удалось скопировать изображение");
    }
    return;
  }

  const modalButton = event.target.closest("[data-open-map-modal]");
  if (modalButton) {
    await openMapModal(modalButton.dataset.openMapModal);
    return;
  }

  if (event.target.closest("[data-close-map-modal]")) {
    await closeMapModals();
    return;
  }

  const insertTagButton = event.target.closest("[data-insert-tag]");
  if (insertTagButton) {
    const form = insertTagButton.closest("form");
    const input = form?.querySelector("input[name='tags']");
    if (input) {
      toggleMapTag(input, insertTagButton.dataset.insertTag);
      input.focus();
    }
    return;
  }

  if (event.target.closest("[data-open-upload-modal]")) {
    openUploadModal();
    return;
  }

  if (event.target.closest("[data-close-upload-modal]")) {
    closeUploadModal();
    return;
  }

  const uploadTagButton = event.target.closest("[data-upload-tag]");
  if (uploadTagButton) {
    addTagToInput(uploadTagsText, uploadTagButton.dataset.uploadTag);
    uploadTagsText.focus();
    return;
  }

  if (event.target.closest("[data-confirm-upload]")) {
    batchTagsInput.value = uploadTagsText.value;
    if (singleTitleInput) {
      singleTitleInput.value = uploadSingleTitleWrap?.hidden ? "" : (uploadSingleTitle?.value || "").trim();
    }
    closeUploadModal({ resetFiles: false });
    uploadForm.submit();
  }
});

document.addEventListener("change", (event) => {
  const perPageSelect = event.target.closest("[data-maps-per-page]");
  if (perPageSelect) {
    loadMapsFragment(mapFilterUrlFromState());
    return;
  }

  const selectInput = event.target.closest("[data-map-select]");
  if (selectInput) {
    selectInput.closest("[data-map-tile]")?.classList.toggle("is-selected", selectInput.checked);
    updateBulkDeleteState();
    return;
  }

  const tagsInput = event.target.closest("input[name='tags']");
  if (tagsInput) {
    setInputTags(tagsInput, tagsFromInput(tagsInput));
  }
});

document.addEventListener("input", (event) => {
  const searchInput = event.target.closest("[data-map-search]");
  if (searchInput) {
    window.clearTimeout(mapSearchTimer);
    mapSearchTimer = window.setTimeout(() => {
      loadMapsFragment(mapFilterUrlFromState(), true, { showLoading: false, preserveFocus: true }).catch(() => showToast("Не удалось выполнить поиск"));
    }, 320);
    return;
  }

  const tagSearchInput = event.target.closest("[data-map-tag-search]");
  if (tagSearchInput) {
    filterMapTagPicker(tagSearchInput);
    return;
  }

  const filterTagSearchInput = event.target.closest("[data-map-filter-tag-search]");
  if (filterTagSearchInput) {
    filterMapFilterTags(filterTagSearchInput);
    return;
  }

  const taxonomyTagSearchInput = event.target.closest("[data-map-taxonomy-tag-search]");
  if (taxonomyTagSearchInput) {
    filterMapTaxonomyTags(taxonomyTagSearchInput);
    return;
  }

  const tagsInput = event.target.closest("input[name='tags']");
  if (tagsInput) {
    syncTagButtons(tagsInput);
    return;
  }

  const uploadTagsInput = event.target.closest("[data-upload-tags-text]");
  if (uploadTagsInput) {
    syncTagButtons(uploadTagsInput);
  }
});

document.addEventListener("submit", (event) => {
  const mapFilterForm = event.target.closest("[data-map-filter-form]");
  if (mapFilterForm) {
    event.preventDefault();
    loadMapsFragment(mapFilterUrlFromState(), true, { showLoading: false, preserveFocus: true }).catch(() => showToast("Не удалось применить фильтр"));
    return;
  }

  const mapSettingsForm = event.target.closest("[data-map-settings-form]");
  if (mapSettingsForm) {
    event.preventDefault();
    if (!isMapSettingsDirty(mapSettingsForm)) {
      closeMapModals({ save: false, refresh: false });
      return;
    }
    const submitButton = mapSettingsForm.querySelector("button[type='submit']");
    if (submitButton) submitButton.disabled = true;
    saveMapSettingsForm(mapSettingsForm)
      .then(() => {
        closeMapModals({ save: false, refresh: false });
      })
      .catch(() => window.alert("Не удалось сохранить запись. Попробуйте ещё раз."))
      .finally(() => {
        if (submitButton) submitButton.disabled = false;
      });
    return;
  }

  const tagCreateForm = event.target.closest("[data-map-tag-create-form]");
  if (tagCreateForm) {
    event.preventDefault();
    const input = tagCreateForm.querySelector("[data-map-tag-create-input]");
    const submitButton = tagCreateForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    fetch(tagCreateForm.action, {
      method: "POST",
      body: new FormData(tagCreateForm),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Map tag was not created.");
        return response.json();
      })
      .then((payload) => {
        if (input) input.value = "";
        if (payload.created) {
          return loadMapsFragment(window.location.href, false, { showLoading: false }).then(openMapTagEditor);
        }
        return null;
      })
      .catch(() => window.alert("Не удалось создать тег. Попробуйте ещё раз."))
      .finally(() => {
        if (submitButton) submitButton.disabled = false;
      });
    return;
  }

});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-map-tag-search], [data-map-filter-tag-search]")) {
    event.preventDefault();
    return;
  }

  const renameInput = event.target.closest("[data-map-rename-input]");
  if (renameInput && event.key === "Enter") {
    event.preventDefault();
    await renameMapTag(renameInput).catch(() => showToast("Не удалось переименовать тег"));
    return;
  }

  if (renameInput && event.key === "Escape") {
    event.preventDefault();
    closeMapTagRename(renameInput.closest("[data-map-tag-order-item]") || pendingMapTagRenameForm);
    return;
  }

  if (event.key === "Escape") {
    await closeMapModals();
    closeUploadModal();
    closeMapTagEditor();
    closeMapTagRenameModal();
    closeMapTagDeleteModal();
  }
});

window.addEventListener("DOMContentLoaded", () => {
  syncMapFilterStateFromBoard();
  layoutMasonryBoard();
  document.querySelectorAll("[data-map-tile] img").forEach((image) => {
    if (image.complete) return;
    image.addEventListener("load", layoutMasonryBoard, { once: true });
  });
});
window.addEventListener("resize", layoutMasonryBoard);

window.addEventListener("popstate", () => {
  loadMapsFragment(window.location.href, false);
});
