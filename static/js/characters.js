const characterUploadForm = document.querySelector("[data-character-dropzone]");
const characterFileInput = document.querySelector("[data-character-file-input]");
const characterFileCount = document.querySelector("[data-character-file-count]");
const characterUploadModal = document.querySelector("[data-character-upload-modal]");
const uploadCharacterTagsText = document.querySelector("[data-upload-character-tags-text]");
const batchTagsInput = document.querySelector("[data-batch-tags-input]");
const characterSingleTitleInput = document.querySelector("[data-character-single-title-input]");
const characterSingleTitleWrap = document.querySelector("[data-character-single-title-wrap]");
const characterSingleTitle = document.querySelector("[data-character-single-title]");
const characterUploadModeKicker = document.querySelector("[data-character-upload-mode-kicker]");
const characterUploadModeTitle = document.querySelector("[data-character-upload-mode-title]");
const characterUploadModeDescription = document.querySelector("[data-character-upload-mode-description]");
const copyToast = document.querySelector("[data-character-copy-toast]");
let characterSearchInput = document.querySelector("[data-character-search]");
let charactersBoard = document.querySelector("[data-characters-board]");
let characterTagOrderModal = document.querySelector("[data-character-tag-order-modal]");
let characterTagOrderModalList = document.querySelector("[data-character-order-modal-list]");
let characterTagDeleteModal = document.querySelector("[data-character-tag-delete-modal]");
const initialCharacterDynamic = document.querySelector("[data-characters-dynamic]");
let serviceTag = charactersBoard?.dataset.serviceCharacterTag || initialCharacterDynamic?.dataset.serviceCharacterTag || "Неотсортированные";
let campaignSlug = charactersBoard?.dataset.campaignSlug || initialCharacterDynamic?.dataset.campaignSlug || document.querySelector("input[name='campaign_slug']")?.value || "";

let characterSelectModeEnabled = false;
let includedCharacterTags = new Set((charactersBoard?.dataset.activeTags || initialCharacterDynamic?.dataset.activeTags || "").split("||").filter(Boolean).map(normalizeTag));
let excludedCharacterTags = new Set((charactersBoard?.dataset.excludedTags || initialCharacterDynamic?.dataset.excludedTags || "").split("||").filter(Boolean).map(normalizeTag));
let draggedCharacterTagItem = null;
let characterTagOrderDirty = false;
let pendingCharacterTagDeleteForm = null;
let pendingCharacterTagRenameForm = null;
let characterSearchTimer = null;
let characterRefreshToken = 0;

function syncCharacterDynamicRefs() {
  characterSearchInput = document.querySelector("[data-character-search]");
  charactersBoard = document.querySelector("[data-characters-board]");
  characterTagOrderModal = document.querySelector("[data-character-tag-order-modal]");
  characterTagOrderModalList = document.querySelector("[data-character-order-modal-list]");
  characterTagDeleteModal = document.querySelector("[data-character-tag-delete-modal]");
  const dynamic = document.querySelector("[data-characters-dynamic]");
  serviceTag = charactersBoard?.dataset.serviceCharacterTag || dynamic?.dataset.serviceCharacterTag || serviceTag || "Неотсортированные";
  campaignSlug = charactersBoard?.dataset.campaignSlug || dynamic?.dataset.campaignSlug || document.querySelector("input[name='campaign_slug']")?.value || campaignSlug || "";
  includedCharacterTags = new Set(((charactersBoard?.dataset.activeTags || dynamic?.dataset.activeTags || "")).split("||").filter(Boolean).map(normalizeTag));
  excludedCharacterTags = new Set(((charactersBoard?.dataset.excludedTags || dynamic?.dataset.excludedTags || "")).split("||").filter(Boolean).map(normalizeTag));
  characterSelectModeEnabled = false;
}

function layoutMasonryBoard() {
  const board = document.querySelector("[data-characters-board]");
  if (!board) return;
  const styles = window.getComputedStyle(board);
  const rowHeight = Number.parseFloat(styles.getPropertyValue("grid-auto-rows")) || 8;
  const rowGap = Number.parseFloat(styles.getPropertyValue("row-gap")) || 0;

  board.querySelectorAll("[data-character-tile]").forEach((tile) => {
    if (tile.style.display === "none" || tile.hidden) return;
    tile.style.setProperty("--tile-rows", "1");
    const span = Math.ceil((tile.getBoundingClientRect().height + rowGap) / (rowHeight + rowGap));
    tile.style.setProperty("--tile-rows", String(Math.max(span, 1)));
  });
}

function normalizeTag(tag) {
  return (tag || "").trim().toLocaleLowerCase("ru-RU");
}

function displayTagsFromSet(tagSet) {
  const tags = [];
  document.querySelectorAll("[data-character-filter-chip]").forEach((chip) => {
    if (tagSet.has(normalizeTag(chip.dataset.characterFilterChip))) tags.push(chip.dataset.characterFilterChip);
  });
  return tags;
}

function currentIncludedTags() {
  return displayTagsFromSet(includedCharacterTags);
}

function currentExcludedTags() {
  return displayTagsFromSet(excludedCharacterTags);
}

function tagsFromInput(input) {
  return input.value.split(",").map((item) => item.trim()).filter(Boolean);
}

function syncCharacterTagButtons(input) {
  const form = input.closest("form");
  if (!form) return;
  const active = new Set(tagsFromInput(input).map(normalizeTag));
  form.querySelectorAll("[data-insert-character-tag]").forEach((button) => {
    button.classList.toggle("is-active", active.has(normalizeTag(button.dataset.insertCharacterTag)));
  });
}

function filterCharacterTagPicker(searchInput) {
  const container = searchInput.closest(".map-modal-form, .upload-modal-dialog")?.querySelector(".map-modal-tags");
  if (!container) return;
  const query = normalizeTag(searchInput.value || "");
  container.querySelectorAll("button").forEach((button) => {
    const tag = normalizeTag(button.dataset.insertCharacterTag || button.dataset.uploadCharacterTag || button.textContent || "");
    button.hidden = Boolean(query) && !tag.includes(query);
  });
}

function filterCharacterFilterTags(searchInput) {
  const query = normalizeTag(searchInput.value || "");
  document.querySelectorAll("[data-character-filter-chip]").forEach((chip) => {
    const tag = normalizeTag(chip.dataset.characterFilterChip || chip.textContent || "");
    const visible = !query || tag.includes(query);
    chip.hidden = !visible;
    chip.style.display = visible ? "" : "none";
  });
}

function filterCharacterTaxonomyTags(searchInput) {
  const query = normalizeTag(searchInput.value || "");
  document.querySelectorAll("[data-character-tag-order-item]").forEach((item) => {
    const tag = normalizeTag(item.dataset.characterTag || item.textContent || "");
    const visible = !query || tag.includes(query);
    item.hidden = !visible;
    item.style.display = visible ? "" : "none";
  });
}

function setCharacterInputTags(input, tags) {
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
  syncCharacterTagButtons(input);
}

function toggleCharacterTag(input, tag) {
  if (normalizeTag(tag) === normalizeTag(serviceTag)) {
    setCharacterInputTags(input, [serviceTag]);
    return;
  }
  const currentRegularTags = tagsFromInput(input).filter((item) => normalizeTag(item) !== normalizeTag(serviceTag));
  const hasTag = currentRegularTags.some((item) => normalizeTag(item) === normalizeTag(tag));
  setCharacterInputTags(input, hasTag ? currentRegularTags.filter((item) => normalizeTag(item) !== normalizeTag(tag)) : [...currentRegularTags, tag]);
}

function addTagToInput(input, tag) {
  if (!input) return;
  const tags = tagsFromInput(input);
  if (!tags.some((item) => normalizeTag(item) === normalizeTag(tag))) tags.push(tag);
  input.value = tags.join(", ");
}

function syncReturnTagInputs() {
  const activeTags = currentIncludedTags();
  document.querySelectorAll("form").forEach((form) => {
    if (!form.querySelector("input[name='campaign_slug']")) return;
    form.querySelectorAll("input[name='return_tag'], input[name='return_group'], input[name='return_exclude_tag'], input[name='return_exclude_group']").forEach((input) => input.remove());
    activeTags.forEach((tag) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "return_tag";
      input.value = tag;
      form.appendChild(input);
    });
    currentExcludedTags().forEach((tag) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "return_exclude_tag";
      input.value = tag;
      form.appendChild(input);
    });
  });
}

function characterPageUrl(page = 1, queryOverride = null) {
  if (!campaignSlug) return;
  const url = new URL(window.location.href);
  url.searchParams.set("campaign", campaignSlug);
  url.searchParams.delete("tag");
  url.searchParams.delete("group");
  url.searchParams.delete("exclude_tag");
  url.searchParams.delete("exclude_group");
  url.searchParams.delete("page");
  currentIncludedTags().forEach((tag) => url.searchParams.append("tag", tag));
  currentExcludedTags().forEach((tag) => url.searchParams.append("exclude_tag", tag));
  const query = (queryOverride ?? characterSearchInput?.value ?? "").trim();
  if (query.length >= 3) url.searchParams.set("q", query);
  else url.searchParams.delete("q");
  if (page > 1) url.searchParams.set("page", String(page));
  return url;
}

function updateCharacterUrl() {
  const url = characterPageUrl();
  if (!url) return;
  window.history.replaceState({}, "", url.toString());
}

async function loadCharactersFragment(url, pushState = true) {
  const refreshToken = ++characterRefreshToken;
  const activeSearch = document.activeElement?.matches?.("[data-character-search]")
    ? {
        value: document.activeElement.value,
        start: document.activeElement.selectionStart,
        end: document.activeElement.selectionEnd,
      }
    : null;
  const current = document.querySelector("[data-characters-dynamic]");
  if (current) current.style.minHeight = `${current.offsetHeight}px`;
  try {
    const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
    const html = await response.text();
    if (refreshToken !== characterRefreshToken) return;
    const incoming = new DOMParser().parseFromString(html, "text/html").querySelector("[data-characters-dynamic]");
    if (!incoming || !current) {
      window.location.href = url;
      return;
    }
    const latestSearch = activeSearch
      ? (() => {
          const liveInput = document.querySelector("[data-character-search]");
          return liveInput
            ? {
                value: liveInput.value || "",
                start: liveInput.selectionStart ?? activeSearch.start,
                end: liveInput.selectionEnd ?? activeSearch.end,
              }
            : activeSearch;
        })()
      : null;
    current.replaceWith(incoming);
    syncCharacterDynamicRefs();
    if (latestSearch && characterSearchInput) {
      characterSearchInput.value = latestSearch.value;
      characterSearchInput.focus();
      if (typeof latestSearch.start === "number" && typeof latestSearch.end === "number") {
        characterSearchInput.setSelectionRange(latestSearch.start, latestSearch.end);
      }
    }
    setCharacterSelectMode(false);
    updateCharacterFilterChips();
    if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
    openInitialCharacterModal();
    window.requestAnimationFrame(() => {
      layoutMasonryBoard();
      const next = document.querySelector("[data-characters-dynamic]");
      if (next) next.style.minHeight = "";
    });
    document.querySelectorAll("[data-character-tile] img").forEach((image) => {
      if (image.complete) return;
      image.addEventListener("load", layoutMasonryBoard, { once: true });
    });
    if (pushState) window.history.pushState({}, "", url);
  } catch {
    window.location.href = url;
  }
}

function updateCharacterFilterChips() {
  const hasFilters = includedCharacterTags.size > 0 || excludedCharacterTags.size > 0;
  document.querySelectorAll("[data-character-filter-chip]").forEach((chip) => {
    const tag = normalizeTag(chip.dataset.characterFilterChip);
    chip.classList.toggle("is-included", includedCharacterTags.has(tag));
    chip.classList.toggle("is-excluded", excludedCharacterTags.has(tag));
    chip.classList.toggle("is-muted", hasFilters && !includedCharacterTags.has(tag) && !excludedCharacterTags.has(tag));
  });
}

function applyCharacterSearch() {
  const query = (characterSearchInput?.value || "").trim().toLocaleLowerCase("ru-RU");
  const shouldSearch = query.length >= 3;
  let visibleCount = 0;

  if (shouldSearch && (includedCharacterTags.size || excludedCharacterTags.size)) {
    includedCharacterTags.clear();
    excludedCharacterTags.clear();
    syncReturnTagInputs();
    updateCharacterUrl();
  }

  document.querySelectorAll("[data-character-tile]").forEach((tile) => {
    const name = (tile.dataset.characterName || "").toLocaleLowerCase("ru-RU");
    const tileTags = (tile.dataset.tags || "").split("||").map(normalizeTag).filter(Boolean);
    const matchesSearch = !shouldSearch || name.includes(query);
    const matchesIncluded = shouldSearch || [...includedCharacterTags].every((tag) => tileTags.includes(tag));
    const matchesExcluded = ![...excludedCharacterTags].some((tag) => tileTags.includes(tag));
    const isVisible = matchesSearch && matchesIncluded && matchesExcluded;
    tile.hidden = false;
    tile.style.display = isVisible ? "" : "none";
    if (isVisible) visibleCount += 1;
  });
  window.requestAnimationFrame(layoutMasonryBoard);

  updateCharacterFilterChips();
  const hint = document.querySelector("[data-character-filter-hint]");
  if (hint) {
    if (shouldSearch) hint.textContent = `Идёт поиск по имени. Найдено NPC: ${visibleCount}.`;
    else if (!includedCharacterTags.size && !excludedCharacterTags.size) hint.textContent = "Можно включить несколько тегов сразу или исключить лишние группы NPC.";
    else hint.textContent = `Показано NPC: ${visibleCount}.`;
  }
  const emptyState = document.querySelector("[data-character-client-empty]");
  if (emptyState) emptyState.hidden = visibleCount > 0;
  return visibleCount;
}

function setCharacterHoverMode(isEditMode) {
  document.querySelectorAll("[data-open-character-modal]").forEach((button) => {
    button.dataset.mode = isEditMode ? "edit" : "view";
    button.textContent = isEditMode ? button.dataset.editLabel : button.dataset.viewLabel;
    button.classList.toggle("info-action-button", !isEditMode);
    button.setAttribute("aria-label", isEditMode ? "Редактировать NPC" : "Открыть карточку NPC");
  });
}

function showCharacterToast(message) {
  if (!copyToast) return;
  copyToast.textContent = message;
  copyToast.classList.add("is-visible");
  window.setTimeout(() => copyToast.classList.remove("is-visible"), 1400);
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

  if (!copied) throw new Error("Legacy image copy failed.");
}

async function copyPngBlobViaServer(pngBlob) {
  const formData = new FormData();
  formData.append("image", pngBlob, "clipboard.png");
  await window.startLocalJob("/clipboard/copy-image", { method: "POST", body: formData });
}

async function copyImageToClipboard(imageUrl) {
  if (!imageUrl) throw new Error("Image URL is empty.");
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

async function copyCharacterImageViaServer(copyImageUrl) {
  const formData = new FormData();
  formData.append("campaign_slug", campaignSlug);
  await window.startLocalJob(copyImageUrl, { method: "POST", body: formData });
}

function shouldCopyCharacterImageInBrowser(imageUrl) {
  const cleanUrl = String(imageUrl || "").split("?", 1)[0].toLocaleLowerCase("ru-RU");
  return cleanUrl.endsWith(".webp") || cleanUrl.endsWith(".avif");
}

async function copyCharacterImage(copyImageUrl, browserImageUrl) {
  if (shouldCopyCharacterImageInBrowser(browserImageUrl)) {
    await copyImageToClipboard(browserImageUrl);
    return;
  }
  try {
    await copyCharacterImageViaServer(copyImageUrl);
  } catch (serverError) {
    await copyImageToClipboard(serverError.clipboardImageUrl || browserImageUrl);
  }
}

function escapeCharacterHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCharacterMarkdown(value) {
  const colorMap = {
    red: "red", "красный": "red", "красная": "red",
    green: "green", "зелёный": "green", "зеленый": "green", "зелёная": "green", "зеленая": "green",
    blue: "blue", "синий": "blue", "синяя": "blue",
    gold: "gold", "золото": "gold", "жёлтый": "gold", "желтый": "gold",
    aqua: "aqua", "бирюзовый": "aqua",
    purple: "purple", "фиолетовый": "purple",
  };
  const renderInline = (input) => escapeCharacterHtml(input)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\[\[([^\]]+)\]\]/g, '<span class="note-wiki-link">$1</span>')
    .replace(/\[([^\]\n|]+?)\s*\|\s*([^\]\n]+?)\]/g, (_match, label, target) => {
      const href = String(target || "").trim();
      if (/^https?:\/\//i.test(href)) {
        return `<a class="rule-inline-link" href="${escapeCharacterHtml(href)}" target="_blank" rel="noopener noreferrer">${label.trim()}</a>`;
      }
      return `<span class="rule-inline-link" title="${escapeCharacterHtml(href)}">${label.trim()}</span>`;
    })
    .replace(/\[([^\]\n]+?)\]\(([^)\n]+?)\)/g, (_match, label, href) => {
      const safeHref = String(href || "").trim();
      const isExternal = /^https?:\/\//i.test(safeHref);
      const isInternal = safeHref.startsWith("/") && !safeHref.startsWith("//") && !safeHref.includes("\\");
      if (!isExternal && !isInternal) return _match;
      const target = isExternal ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `<a class="rule-inline-link" href="${escapeCharacterHtml(safeHref)}"${target}>${label.trim()}</a>`;
    })
    .replace(/\{([A-Za-zА-Яа-яЁё-]+)\|([^{}\n]+)\}/g, (_match, color, text) => {
      const className = colorMap[String(color || "").trim().toLocaleLowerCase("ru-RU")];
      return className ? `<span class="rule-color rule-color-${className}">${text}</span>` : _match;
    })
    .replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, "<em>$1</em>")
    .replace(/(?<!\w)_([^_\n]+?)_(?!\w)/g, "<u>$1</u>");

  const blocks = String(value || "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
  const html = blocks.length
    ? blocks.map((block) => `<p>${renderInline(block).replace(/\n/g, "<br>")}</p>`).join("")
    : "<p>Заметок пока нет.</p>";
  return `<div class="rich-text">${html}</div>`;
}

function setCharacterSingleTitleVisibility(isVisible) {
  if (!characterSingleTitleWrap) return;
  characterSingleTitleWrap.hidden = !isVisible;
  characterSingleTitleWrap.style.display = isVisible ? "grid" : "none";
}

function updateCharacterUploadModalTexts(isSingle) {
  if (characterUploadModeKicker) characterUploadModeKicker.textContent = isSingle ? "Одиночная загрузка" : "Пакетная загрузка";
  if (characterUploadModeTitle) characterUploadModeTitle.textContent = isSingle ? "Настройте карточку NPC" : "Назначьте теги всем выбранным NPC";
  if (characterUploadModeDescription) {
    characterUploadModeDescription.textContent = isSingle
      ? "Вы можете задать имя NPC и выбрать теги для изображения. Если теги не выбрать, NPC попадёт в “Неотсортированные”."
      : "Выберите теги, которые будут применены ко всем загружаемым изображениям. Если ничего не выбрать, NPC попадут в “Неотсортированные”.";
  }
}

function updateCharacterFileCount() {
  if (!characterFileInput?.files.length) {
    characterFileCount.textContent = "PNG, JPG, WEBP, GIF, AVIF";
    setCharacterSingleTitleVisibility(false);
    if (characterSingleTitle) characterSingleTitle.value = "";
    if (characterSingleTitleInput) characterSingleTitleInput.value = "";
    return;
  }
  characterFileCount.textContent = `Выбрано файлов: ${characterFileInput.files.length}`;
  const isSingle = characterFileInput.files.length === 1;
  setCharacterSingleTitleVisibility(isSingle);
  updateCharacterUploadModalTexts(isSingle);
  if (!isSingle) {
    if (characterSingleTitle) characterSingleTitle.value = "";
    if (characterSingleTitleInput) characterSingleTitleInput.value = "";
    return;
  }
  const filename = characterFileInput.files[0]?.name || "";
  const stem = filename.includes(".") ? filename.slice(0, filename.lastIndexOf(".")) : filename;
  if (characterSingleTitle && !characterSingleTitle.value.trim()) {
    characterSingleTitle.value = stem;
  }
}

async function saveCharacterForm(form) {
  if (!form) return null;
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Character was not saved.");
  syncCharacterView(form, payload.character);
  return payload.character;
}

async function closeCharacterModals({ save = true, refresh = true } = {}) {
  const openForms = save
    ? [...document.querySelectorAll("[data-character-modal].is-open.is-editing [data-character-form]")]
    : [];
  document.querySelectorAll("[data-character-modal]").forEach((modal) => {
    modal.classList.remove("is-open", "is-editing");
    modal.setAttribute("aria-hidden", "true");
  });
  document.body.classList.remove("has-modal");
  const url = new URL(window.location.href);
  if (url.searchParams.has("character")) {
    url.searchParams.delete("character");
    window.history.replaceState({}, "", url.toString());
  }
  if (openForms.length) {
    await Promise.all(openForms.map((form) => saveCharacterForm(form)));
    if (refresh) await loadCharactersFragment(window.location.href, false);
  }
}

function setCharacterModalMode(modal, mode) {
  const isEdit = mode === "edit";
  modal.classList.toggle("is-editing", isEdit);
  modal.querySelector("[data-character-view]").hidden = isEdit;
  modal.querySelector("[data-character-edit]").hidden = !isEdit;
  modal.querySelectorAll("[data-character-edit-only]").forEach((item) => {
    item.hidden = !isEdit;
  });
  if (isEdit) window.setTimeout(() => modal.querySelector("input[name='name']")?.focus(), 40);
}

function characterFormValues(form) {
  const formData = new FormData(form);
  const tags = String(formData.get("tags") || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    id: form.closest("[data-character-modal]")?.dataset.characterModal || "",
    name: String(formData.get("name") || "").trim() || "Без имени",
    age: String(formData.get("age") || "").trim(),
    gender: String(formData.get("gender") || "Иное").trim(),
    race: String(formData.get("race") || "").trim(),
    notes: String(formData.get("notes") || "").trim(),
    tags: tags.length ? tags : [serviceTag],
  };
}

function setCopyField(field, value, fallback = "Не указано", options = {}) {
  if (!field) return;
  const text = value || fallback;
  field.dataset.copyValue = text;
  const valueNode = field.querySelector("[data-character-rich-value]") || field.querySelector("strong");
  if (!valueNode) return;
  if (options.markdown) valueNode.innerHTML = renderCharacterMarkdown(text);
  else valueNode.textContent = text;
}

function syncCharacterView(form, character) {
  if (!form || !character) return;
  const modal = form.closest("[data-character-modal]");
  const viewFields = modal?.querySelectorAll("[data-character-view] [data-copy-value]") || [];
  const tagsText = (character.tags || [serviceTag]).join(", ");
  const notesText = character.notes || "Заметок пока нет.";

  modal?.querySelector(".map-modal-heading h2")?.replaceChildren(document.createTextNode(character.name));
  setCopyField(viewFields[0], character.name);
  setCopyField(viewFields[1], character.age);
  setCopyField(viewFields[2], character.gender, "Иное");
  setCopyField(viewFields[3], character.race);
  setCopyField(viewFields[4], tagsText);
  setCopyField(viewFields[5], notesText, "Заметок пока нет.", { markdown: true });

  const tile = document.querySelector(`[data-open-character-modal="${CSS.escape(character.id)}"]`)?.closest("[data-character-tile]");
  if (tile) {
    tile.dataset.characterName = character.name.toLocaleLowerCase("ru-RU");
    tile.dataset.tags = (character.tags || [serviceTag]).join("||");
    const captionTitle = tile.querySelector(".character-caption strong");
    const captionTags = tile.querySelector(".character-caption span");
    if (captionTitle) captionTitle.textContent = character.name;
    if (captionTags) captionTags.textContent = (character.tags || [serviceTag]).join(" · ");
    const modalButton = tile.querySelector("[data-open-character-modal]");
    if (modalButton) modalButton.setAttribute("aria-label", `Открыть карточку ${character.name}`);
  }

  document.querySelectorAll(`[data-character-modal="${CSS.escape(character.id)}"] [data-copy-character-art], [data-character-modal="${CSS.escape(character.id)}"] [data-copy-character-image]`).forEach((button) => {
    if (character.foundry_path) button.dataset.copyFoundryPath = character.foundry_path;
  });
  applyCharacterSearch();
}

async function openCharacterModal(characterId, mode = "view") {
  await closeCharacterModals();
  const modal = document.querySelector(`[data-character-modal="${CSS.escape(characterId)}"]`);
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  setCharacterModalMode(modal, mode);
  const tagsInput = modal.querySelector("input[name='tags']");
  if (tagsInput) setCharacterInputTags(tagsInput, tagsFromInput(tagsInput));
}

function openInitialCharacterModal() {
  const dynamic = document.querySelector("[data-characters-dynamic]");
  const characterId = dynamic?.dataset.openCharacterId || "";
  if (!characterId) return;
  dynamic.dataset.openCharacterId = "";
  openCharacterModal(characterId, "view");
}

function openCharacterUploadModal() {
  if (!characterFileInput?.files.length) {
    characterFileInput?.click();
    return;
  }
  const isSingle = characterFileInput.files.length === 1;
  setCharacterSingleTitleVisibility(isSingle);
  updateCharacterUploadModalTexts(isSingle);
  if (!isSingle && characterSingleTitle) characterSingleTitle.value = "";
  characterUploadModal.classList.add("is-open");
  characterUploadModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  if (!characterSingleTitleWrap?.hidden) {
    characterSingleTitle?.focus();
    characterSingleTitle?.select();
  } else {
    uploadCharacterTagsText?.focus();
  }
}

function closeCharacterUploadModal({ resetFiles = true } = {}) {
  characterUploadModal.classList.remove("is-open");
  characterUploadModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("has-modal");
  if (resetFiles && characterFileInput) {
    characterFileInput.value = "";
    updateCharacterFileCount();
  }
}

function selectedCharacterIds() {
  return [...document.querySelectorAll("[data-character-select]")].filter((input) => input.checked).map((input) => input.value);
}

function setCharacterSelectMode(isEnabled) {
  characterSelectModeEnabled = isEnabled;
  document.body.classList.toggle("is-selecting-maps", isEnabled);
  document.querySelector("[data-toggle-character-select-mode]")?.classList.toggle("is-active", isEnabled);
  document.querySelector("[data-toggle-character-select-mode]")?.setAttribute("aria-expanded", String(isEnabled));
  const bulkDeleteForm = document.querySelector("[data-character-bulk-delete-form]");
  if (bulkDeleteForm) bulkDeleteForm.hidden = !isEnabled;
  if (!isEnabled) {
    document.querySelectorAll("[data-character-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-character-tile]")?.classList.remove("is-selected");
    });
  }
  updateCharacterBulkDeleteState();
}

function updateCharacterBulkDeleteState() {
  const ids = selectedCharacterIds();
  const selectedCount = document.querySelector("[data-character-selected-count]");
  const bulkDeleteButton = document.querySelector("[data-character-bulk-delete-button]");
  const bulkDeleteBar = document.querySelector("[data-character-bulk-delete-bar]");
  const bulkDeleteInputs = document.querySelector("[data-character-bulk-delete-inputs]");
  if (selectedCount) selectedCount.textContent = String(ids.length);
  if (bulkDeleteButton) bulkDeleteButton.disabled = ids.length === 0;
  if (bulkDeleteBar) bulkDeleteBar.hidden = !characterSelectModeEnabled;
  if (bulkDeleteInputs) {
    bulkDeleteInputs.innerHTML = "";
    ids.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "character_ids";
      input.value = id;
      bulkDeleteInputs.appendChild(input);
    });
  }
}

function getCharacterTagOrderItems() {
  return [...document.querySelectorAll("[data-character-tag-order-item]")];
}

function getCharacterOrderModalItems() {
  return [...document.querySelectorAll("[data-character-order-modal-item]")];
}

function updateCharacterOrderNumbers() {
  getCharacterOrderModalItems().forEach((item, index) => {
    const number = item.querySelector("[data-rule-order-number]");
    if (number) number.textContent = String(index + 1);
  });
}

function syncCharacterTagDependentOrder() {
  const orderedItems = getCharacterOrderModalItems();
  const editorList = document.querySelector("[data-character-tag-order-list]");
  const filterList = document.querySelector("[data-character-filters]");

  orderedItems.forEach((item, index) => {
    const tag = item.dataset.characterTag;
    const nextTag = orderedItems[index + 1]?.dataset.characterTag || serviceTag;
    const editorItem = document.querySelector(`[data-character-tag-order-item][data-character-tag="${CSS.escape(tag)}"]`);
    const nextEditorItem = document.querySelector(`[data-character-tag-order-item][data-character-tag="${CSS.escape(nextTag)}"]`);
    const chip = document.querySelector(`[data-character-filter-chip="${CSS.escape(tag)}"]`);
    const nextChip = document.querySelector(`[data-character-filter-chip="${CSS.escape(nextTag)}"]`);

    if (editorItem && editorList) editorList.insertBefore(editorItem, nextEditorItem || null);
    if (chip && filterList) filterList.insertBefore(chip, nextChip || null);

    document.querySelectorAll(".map-modal-tags").forEach((list) => {
      const button = list.querySelector(`[data-insert-character-tag="${CSS.escape(tag)}"], [data-upload-character-tag="${CSS.escape(tag)}"]`);
      const nextButton = list.querySelector(`[data-insert-character-tag="${CSS.escape(nextTag)}"], [data-upload-character-tag="${CSS.escape(nextTag)}"]`);
      if (button) list.insertBefore(button, nextButton || null);
    });
  });
}

async function saveCharacterTagOrder(tags = getCharacterOrderModalItems().map((item) => item.dataset.characterTag)) {
  if (!tags.length || !campaignSlug) return;
  const response = await fetch("/characters/groups/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ campaign_slug: campaignSlug, tags }),
  });
  if (!response.ok) throw new Error("Character tag order was not saved.");
}

function characterTagAlreadyExists(tag) {
  const key = normalizeTag(tag);
  return getCharacterTagOrderItems().some((item) => normalizeTag(item.dataset.characterTag) === key);
}

function createCharacterFilterChip(tag) {
  const chip = document.createElement("span");
  chip.className = "rule-filter-chip";
  chip.dataset.characterFilterChip = tag;
  const includeButton = document.createElement("button");
  includeButton.type = "button";
  includeButton.dataset.characterIncludeTag = tag;
  includeButton.setAttribute("aria-label", `Показать NPC с тегом ${tag}`);
  includeButton.textContent = tag;
  const excludeButton = document.createElement("button");
  excludeButton.type = "button";
  excludeButton.dataset.characterExcludeTag = tag;
  excludeButton.setAttribute("aria-label", `Исключить NPC с тегом ${tag}`);
  excludeButton.textContent = "−";
  chip.append(includeButton, excludeButton);
  return chip;
}

function createCharacterTagDeleteForm(tag) {
  const form = document.createElement("form");
  form.action = "/characters/groups/delete";
  form.method = "post";
  form.dataset.characterTagOrderItem = "";
  form.dataset.characterTag = tag;
  const campaignInput = document.createElement("input");
  campaignInput.type = "hidden";
  campaignInput.name = "campaign_slug";
  campaignInput.value = campaignSlug;
  const tagInput = document.createElement("input");
  tagInput.type = "hidden";
  tagInput.name = "tag";
  tagInput.value = tag;
  const view = document.createElement("div");
  view.className = "audio-tag-row-view map-tag-row-view";
  const label = document.createElement("span");
  label.textContent = tag;
  view.append(label);
  form.append(campaignInput, tagInput, view);
  const renameButton = document.createElement("button");
  renameButton.type = "button";
  renameButton.className = "audio-taxonomy-icon-button map-tag-icon-button";
  renameButton.dataset.characterRenameTag = tag;
  renameButton.setAttribute("aria-label", `Переименовать тег ${tag}`);
  renameButton.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z"/></svg>';
  const button = document.createElement("button");
  if (normalizeTag(tag) === normalizeTag(serviceTag)) {
    button.type = "button";
    button.disabled = true;
    button.textContent = "Сервисный";
  } else {
    button.type = "button";
    button.className = "hold-delete-button";
    button.dataset.holdSubmit = "";
    button.dataset.holdStaticIcon = "";
    button.style.setProperty("--hold-progress", "0");
    button.setAttribute("aria-label", `Удалить тег ${tag}`);
    button.innerHTML = '<span data-hold-delete-label><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></span>';
  }
  if (normalizeTag(tag) !== normalizeTag(serviceTag)) view.appendChild(renameButton);
  view.appendChild(button);
  return form;
}

function createCharacterOrderModalItem(tag) {
  const item = document.createElement("div");
  item.className = "rule-order-item";
  item.draggable = true;
  item.dataset.characterOrderModalItem = "";
  item.dataset.characterTag = tag;
  item.innerHTML = `<span class="rule-order-number" data-rule-order-number></span><span class="tag-drag-handle" aria-hidden="true">↕</span><strong></strong>`;
  item.querySelector("strong").textContent = tag;
  return item;
}

function addCharacterTagToPage(tag) {
  if (!tag || characterTagAlreadyExists(tag)) return;
  document.querySelector("[data-character-tag-order-list]")?.appendChild(createCharacterTagDeleteForm(tag));
  document.querySelector("[data-character-filters]")?.appendChild(createCharacterFilterChip(tag));
  characterTagOrderModalList?.appendChild(createCharacterOrderModalItem(tag));
  document.querySelectorAll(".map-modal-tags").forEach((list) => {
    const isUploadList = Boolean(list.closest("[data-character-upload-modal]"));
    const button = document.createElement("button");
    button.type = "button";
    if (isUploadList) button.dataset.uploadCharacterTag = tag;
    else button.dataset.insertCharacterTag = tag;
    button.textContent = tag;
    list.appendChild(button);
  });
  updateCharacterOrderNumbers();
  syncCharacterTagDependentOrder();
  applyCharacterSearch();
}

function openCharacterTagEditor() {
  const modal = document.querySelector("[data-group-editor]");
  const toggle = document.querySelector("[data-toggle-group-editor]");
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  toggle?.classList.add("is-active");
  toggle?.setAttribute("aria-expanded", "true");
  document.body.classList.add("has-modal");
  window.setTimeout(() => modal.querySelector("[data-character-tag-create-input]")?.focus(), 30);
}

function closeCharacterTagEditor() {
  const modal = document.querySelector("[data-group-editor]");
  const toggle = document.querySelector("[data-toggle-group-editor]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  toggle?.classList.remove("is-active");
  toggle?.setAttribute("aria-expanded", "false");
  if (!document.querySelector(".map-modal.is-open, .rule-modal.is-open, .rule-side-modal.is-open, [data-character-tag-rename-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function openCharacterTagRenameModal(form) {
  const tag = form?.dataset.characterTag || "";
  const modal = document.querySelector("[data-character-tag-rename-modal]");
  if (!modal || !tag || normalizeTag(tag) === normalizeTag(serviceTag)) return;
  pendingCharacterTagRenameForm = form;
  const title = modal.querySelector("[data-character-tag-rename-title]");
  if (title) title.textContent = `Переименовать «${tag}»`;
  const input = modal.querySelector("[data-character-tag-rename-input]");
  if (input) input.value = tag;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  window.setTimeout(() => {
    input?.focus();
    input?.select();
  }, 40);
}

function closeCharacterTagRenameModal() {
  const modal = document.querySelector("[data-character-tag-rename-modal]");
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  pendingCharacterTagRenameForm = null;
  const input = modal.querySelector("[data-character-tag-rename-input]");
  if (input) input.value = "";
  if (!document.querySelector(".character-modal.is-open, [data-group-editor].is-open, [data-character-tag-order-modal].is-open, [data-character-tag-delete-modal].is-open") && !characterUploadModal?.classList.contains("is-open")) {
    document.body.classList.remove("has-modal");
  }
}

async function saveCharacterTagRename() {
  const form = pendingCharacterTagRenameForm;
  const oldTag = form?.dataset.characterTag || "";
  const input = document.querySelector("[data-character-tag-rename-input]");
  const newTag = (input?.value || "").trim();
  const renameUrl = document.querySelector("[data-character-tag-editor]")?.dataset.characterTagRenameUrl || "/characters/groups/rename";
  if (!oldTag || !newTag || !campaignSlug) return;
  const body = new FormData();
  body.set("campaign_slug", campaignSlug);
  body.set("old_tag", oldTag);
  body.set("new_tag", newTag);
  const response = await fetch(renameUrl, {
    method: "POST",
    body,
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "Character tag rename failed.");
  closeCharacterTagRenameModal();
  const url = characterPageUrl();
  if (url) await loadCharactersFragment(url.toString(), false);
  openCharacterTagEditor();
  showCharacterToast("Тег переименован.");
}

function openCharacterTagOrderModal() {
  if (!characterTagOrderModal) return;
  characterTagOrderModal.classList.add("is-open");
  characterTagOrderModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  characterTagOrderDirty = false;
  updateCharacterOrderNumbers();
}

async function closeCharacterTagOrderModal({ save = true } = {}) {
  if (!characterTagOrderModal) return;
  if (save && characterTagOrderDirty) {
    try {
      await saveCharacterTagOrder();
      characterTagOrderDirty = false;
    } catch {
      window.alert("Не удалось сохранить порядок тегов. Попробуйте ещё раз.");
    }
  }
  characterTagOrderModal.classList.remove("is-open");
  characterTagOrderModal.setAttribute("aria-hidden", "true");
  syncCharacterTagDependentOrder();
  if (!document.querySelector(".character-modal.is-open, [data-group-editor].is-open, [data-character-tag-rename-modal].is-open") && !characterUploadModal?.classList.contains("is-open") && !characterTagDeleteModal?.classList.contains("is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function openCharacterTagDeleteModal(form) {
  const tag = form?.dataset.characterTag || "";
  if (!characterTagDeleteModal || !tag || normalizeTag(tag) === normalizeTag(serviceTag)) return;
  pendingCharacterTagDeleteForm = form;
  characterTagDeleteModal.querySelector("[data-character-tag-delete-title]").textContent = `Удалить «${tag}»?`;
  characterTagDeleteModal.querySelector("[data-character-tag-delete-message]").textContent = `Тег «${tag}» будет снят со всех NPC. Если у NPC не останется других тегов, он попадёт в «${serviceTag}».`;
  characterTagDeleteModal.classList.add("is-open");
  characterTagDeleteModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeCharacterTagDeleteModal() {
  if (!characterTagDeleteModal) return;
  characterTagDeleteModal.classList.remove("is-open");
  characterTagDeleteModal.setAttribute("aria-hidden", "true");
  pendingCharacterTagDeleteForm = null;
  if (!document.querySelector(".character-modal.is-open, [data-group-editor].is-open, [data-character-tag-order-modal].is-open, [data-character-tag-rename-modal].is-open") && !characterUploadModal?.classList.contains("is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function removeDeletedCharacterTagFromTiles(tag) {
  document.querySelectorAll("[data-character-tile]").forEach((tile) => {
    const tags = (tile.dataset.tags || "").split("||").filter(Boolean);
    if (!tags.some((item) => normalizeTag(item) === normalizeTag(tag))) return;
    const nextTags = tags.filter((item) => normalizeTag(item) !== normalizeTag(tag));
    tile.dataset.tags = (nextTags.length ? nextTags : [serviceTag]).join("||");
    const caption = tile.querySelector(".character-caption span");
    if (caption) caption.textContent = tile.dataset.tags.split("||").join(" · ");
  });
  document.querySelectorAll("input[name='tags']").forEach((input) => {
    setCharacterInputTags(input, tagsFromInput(input).filter((item) => normalizeTag(item) !== normalizeTag(tag)));
  });
}

async function confirmCharacterTagDelete() {
  if (!pendingCharacterTagDeleteForm) return;
  const form = pendingCharacterTagDeleteForm;
  const tag = form.dataset.characterTag || "";
  const button = characterTagDeleteModal?.querySelector("[data-confirm-character-tag-delete-action]");
  if (button) button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Character tag was not deleted.");
    form.remove();
    document.querySelector(`[data-character-filter-chip="${CSS.escape(tag)}"]`)?.remove();
    document.querySelector(`[data-character-order-modal-item][data-character-tag="${CSS.escape(tag)}"]`)?.remove();
    document.querySelectorAll(`[data-insert-character-tag="${CSS.escape(tag)}"], [data-upload-character-tag="${CSS.escape(tag)}"]`).forEach((item) => item.remove());
    includedCharacterTags.delete(normalizeTag(tag));
    excludedCharacterTags.delete(normalizeTag(tag));
    removeDeletedCharacterTagFromTiles(tag);
    updateCharacterOrderNumbers();
    closeCharacterTagDeleteModal();
    applyCharacterSearch();
  } catch {
    window.alert("Не удалось удалить тег. Попробуйте ещё раз.");
  } finally {
    if (button) button.disabled = false;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  applyCharacterSearch();
  openInitialCharacterModal();
  layoutMasonryBoard();
  document.querySelectorAll("[data-character-tile] img").forEach((image) => {
    if (image.complete) return;
    image.addEventListener("load", layoutMasonryBoard, { once: true });
  });
});
window.addEventListener("resize", layoutMasonryBoard);

characterFileInput?.addEventListener("change", () => {
  updateCharacterFileCount();
  if (characterFileInput.files.length) openCharacterUploadModal();
});

characterUploadForm?.addEventListener("dragover", (event) => {
  event.preventDefault();
  characterUploadForm.classList.add("is-dragging");
});

characterUploadForm?.addEventListener("dragleave", () => characterUploadForm.classList.remove("is-dragging"));

characterUploadForm?.addEventListener("drop", (event) => {
  event.preventDefault();
  characterUploadForm.classList.remove("is-dragging");
  characterFileInput.files = event.dataTransfer.files;
  updateCharacterFileCount();
  openCharacterUploadModal();
});

document.addEventListener("click", async (event) => {
  const groupEditorToggle = event.target.closest("[data-toggle-group-editor]");
  if (groupEditorToggle) {
    const groupEditor = document.querySelector("[data-group-editor]");
    if (groupEditor?.classList.contains("is-open")) closeCharacterTagEditor();
    else openCharacterTagEditor();
    return;
  }
  if (event.target.closest("[data-close-group-editor]")) return closeCharacterTagEditor();
  if (event.target.closest("[data-open-character-tag-order]")) return openCharacterTagOrderModal();
  if (event.target.closest("[data-close-character-tag-order]")) return closeCharacterTagOrderModal();
  if (event.target.closest("[data-save-character-tag-order]")) {
    saveCharacterTagOrder().then(() => window.location.reload()).catch(() => window.alert("Не удалось сохранить порядок тегов. Попробуйте ещё раз."));
    return;
  }
  const renameCharacterTagButton = event.target.closest("[data-character-rename-tag]");
  if (renameCharacterTagButton) {
    openCharacterTagRenameModal(renameCharacterTagButton.closest("[data-character-tag-order-item]"));
    return;
  }
  if (event.target.closest("[data-close-character-tag-rename]")) return closeCharacterTagRenameModal();
  if (event.target.closest("[data-save-character-tag-rename]")) {
    saveCharacterTagRename().catch(() => showCharacterToast("Не удалось переименовать тег."));
    return;
  }
  if (event.target.closest("[data-close-character-tag-delete]")) return closeCharacterTagDeleteModal();
  if (event.target.closest("[data-confirm-character-tag-delete-action]")) return confirmCharacterTagDelete();

  const includeTagButton = event.target.closest("[data-character-include-tag]");
  if (includeTagButton) {
    if (characterSearchInput) characterSearchInput.value = "";
    const tag = normalizeTag(includeTagButton.dataset.characterIncludeTag);
    includedCharacterTags.has(tag) ? includedCharacterTags.delete(tag) : (includedCharacterTags.add(tag), excludedCharacterTags.delete(tag));
    syncReturnTagInputs();
    const url = characterPageUrl();
    if (url) await loadCharactersFragment(url.toString());
    return;
  }
  const excludeTagButton = event.target.closest("[data-character-exclude-tag]");
  if (excludeTagButton) {
    if (characterSearchInput) characterSearchInput.value = "";
    const tag = normalizeTag(excludeTagButton.dataset.characterExcludeTag);
    excludedCharacterTags.has(tag) ? excludedCharacterTags.delete(tag) : (excludedCharacterTags.add(tag), includedCharacterTags.delete(tag));
    syncReturnTagInputs();
    const url = characterPageUrl();
    if (url) await loadCharactersFragment(url.toString());
    return;
  }
  if (event.target.closest("[data-character-clear-filters]")) {
    includedCharacterTags.clear();
    excludedCharacterTags.clear();
    syncReturnTagInputs();
    if (characterSearchInput) characterSearchInput.value = "";
    const url = characterPageUrl();
    if (url) await loadCharactersFragment(url.toString());
    return;
  }
  const dynamicLink = event.target.closest("[data-character-dynamic-link]");
  if (dynamicLink) {
    event.preventDefault();
    await loadCharactersFragment(dynamicLink.href);
    return;
  }
  if (event.target.closest("[data-toggle-character-select-mode]")) return setCharacterSelectMode(!characterSelectModeEnabled);
  if (event.target.closest("[data-clear-character-selection]")) {
    document.querySelectorAll("[data-character-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-character-tile]")?.classList.remove("is-selected");
    });
    updateCharacterBulkDeleteState();
    return;
  }
  const modalButton = event.target.closest("[data-open-character-modal]");
  if (modalButton) {
    await openCharacterModal(modalButton.dataset.openCharacterModal, event.ctrlKey || event.metaKey ? "edit" : modalButton.dataset.mode || "view");
    return;
  }
  if (event.target.closest("[data-close-character-modal]")) {
    await closeCharacterModals();
    return;
  }
  const insertTagButton = event.target.closest("[data-insert-character-tag]");
  if (insertTagButton) {
    const input = insertTagButton.closest("form")?.querySelector("input[name='tags']");
    if (input) {
      toggleCharacterTag(input, insertTagButton.dataset.insertCharacterTag);
      const form = input.closest("[data-character-form]");
      syncCharacterView(form, characterFormValues(form));
      input.focus();
    }
    return;
  }
  const copyField = event.target.closest("[data-copy-value]");
  if (copyField) {
    await copyTextToClipboard(copyField.dataset.copyValue || "");
    showCharacterToast("Текст скопирован");
    return;
  }
  const copyFoundryArtButton = event.target.closest("[data-copy-character-art]");
  if (copyFoundryArtButton) {
    if (copyFoundryArtButton.dataset.copyFoundryPath) {
      await copyTextToClipboard(copyFoundryArtButton.dataset.copyFoundryPath);
      showCharacterToast("Foundry-путь арта скопирован");
      return;
    }
    showCharacterToast("Foundry-путь не настроен");
    return;
  }
  const copyCharacterImageButton = event.target.closest("[data-copy-character-image]");
  if (copyCharacterImageButton) {
    try {
      showCharacterToast("Готовлю изображение...");
      await copyCharacterImage(
        copyCharacterImageButton.dataset.copyImageUrl,
        copyCharacterImageButton.dataset.browserImageUrl
      );
      showCharacterToast("Изображение скопировано");
    } catch {
      showCharacterToast("Не удалось скопировать изображение");
    }
    return;
  }
  if (event.target.closest("[data-open-character-upload-modal]")) return openCharacterUploadModal();
  if (event.target.closest("[data-close-character-upload-modal]")) return closeCharacterUploadModal();
  const uploadTagButton = event.target.closest("[data-upload-character-tag]");
  if (uploadTagButton) {
    addTagToInput(uploadCharacterTagsText, uploadTagButton.dataset.uploadCharacterTag);
    uploadCharacterTagsText?.focus();
    return;
  }
  if (event.target.closest("[data-confirm-character-upload]")) {
    batchTagsInput.value = uploadCharacterTagsText?.value || serviceTag;
    if (characterSingleTitleInput) {
      characterSingleTitleInput.value = characterSingleTitleWrap?.hidden ? "" : (characterSingleTitle?.value || "").trim();
    }
    closeCharacterUploadModal({ resetFiles: false });
    characterUploadForm.requestSubmit();
  }
});

document.addEventListener("dragstart", (event) => {
  const item = event.target.closest("[data-character-order-modal-item]");
  if (!item) return;
  draggedCharacterTagItem = item;
  item.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", item.dataset.characterTag || "");
});

document.addEventListener("dragover", (event) => {
  const targetItem = event.target.closest("[data-character-order-modal-item]");
  if (!targetItem || !draggedCharacterTagItem || targetItem === draggedCharacterTagItem) return;
  event.preventDefault();
  const list = targetItem.closest("[data-character-order-modal-list]");
  if (!list) return;
  const targetRect = targetItem.getBoundingClientRect();
  list.insertBefore(draggedCharacterTagItem, event.clientY > targetRect.top + targetRect.height / 2 ? targetItem.nextSibling : targetItem);
  characterTagOrderDirty = true;
  updateCharacterOrderNumbers();
  syncCharacterTagDependentOrder();
});

document.addEventListener("drop", (event) => {
  if (!draggedCharacterTagItem) return;
  event.preventDefault();
});

document.addEventListener("dragend", () => {
  draggedCharacterTagItem?.classList.remove("is-dragging");
  draggedCharacterTagItem = null;
});

document.addEventListener("change", (event) => {
  const perPageSelect = event.target.closest("[data-characters-per-page]");
  if (perPageSelect) {
    const url = characterPageUrl();
    if (!url) return;
    url.searchParams.set("per_page", perPageSelect.value);
    url.searchParams.delete("page");
    loadCharactersFragment(url.toString());
    return;
  }

  const selectInput = event.target.closest("[data-character-select]");
  if (selectInput) {
    selectInput.closest("[data-character-tile]")?.classList.toggle("is-selected", selectInput.checked);
    updateCharacterBulkDeleteState();
    return;
  }
  const tagsInput = event.target.closest("input[name='tags']");
  if (tagsInput) {
    setCharacterInputTags(tagsInput, tagsFromInput(tagsInput));
    const form = tagsInput.closest("[data-character-form]");
    syncCharacterView(form, characterFormValues(form));
    return;
  }
  const characterField = event.target.closest("[data-character-form] input, [data-character-form] select, [data-character-form] textarea");
  if (characterField) {
    const form = characterField.closest("[data-character-form]");
    syncCharacterView(form, characterFormValues(form));
  }
});

document.addEventListener("input", (event) => {
  const tagSearchInput = event.target.closest("[data-character-tag-search]");
  if (tagSearchInput) {
    filterCharacterTagPicker(tagSearchInput);
    return;
  }
  const filterTagSearchInput = event.target.closest("[data-character-filter-tag-search]");
  if (filterTagSearchInput) {
    filterCharacterFilterTags(filterTagSearchInput);
    return;
  }
  const taxonomyTagSearchInput = event.target.closest("[data-character-taxonomy-tag-search]");
  if (taxonomyTagSearchInput) {
    filterCharacterTaxonomyTags(taxonomyTagSearchInput);
    return;
  }
  if (event.target.closest("[data-character-search]")) {
    applyCharacterSearch();
    window.clearTimeout(characterSearchTimer);
    const queryAtInput = event.target.value.trim();
    characterSearchTimer = window.setTimeout(() => {
      const query = queryAtInput;
      if (query.length > 0 && query.length < 3) return;
      includedCharacterTags.clear();
      excludedCharacterTags.clear();
      const url = characterPageUrl(1, query);
      if (url) loadCharactersFragment(url.toString());
    }, 260);
    return;
  }
  const tagsInput = event.target.closest("input[name='tags']");
  if (tagsInput) syncCharacterTagButtons(tagsInput);
  const characterForm = event.target.closest("[data-character-form]");
  if (characterForm) syncCharacterView(characterForm, characterFormValues(characterForm));
});

document.addEventListener("submit", async (event) => {
  const searchForm = event.target.closest("[data-character-search-form]");
  if (searchForm) {
    event.preventDefault();
    const query = searchForm.querySelector("[data-character-search]")?.value.trim() || "";
    if (query.length > 0 && query.length < 3) {
      applyCharacterSearch();
      return;
    }
    includedCharacterTags.clear();
    excludedCharacterTags.clear();
    const url = characterPageUrl(1, query);
    if (url) await loadCharactersFragment(url.toString());
    return;
  }
  const characterForm = event.target.closest("[data-character-form]");
  if (characterForm) {
    event.preventDefault();
    const submitButton = document.querySelector(`[type="submit"][form="${CSS.escape(characterForm.id)}"]`);
    if (submitButton) submitButton.disabled = true;
    try {
      await saveCharacterForm(characterForm);
      setCharacterModalMode(characterForm.closest("[data-character-modal]"), "view");
      showCharacterToast("NPC сохранён");
    } catch {
      window.alert("Не удалось сохранить NPC. Попробуйте ещё раз.");
    } finally {
      if (submitButton) submitButton.disabled = false;
    }
    return;
  }
  const tagCreateForm = event.target.closest("[data-character-tag-create-form]");
  if (tagCreateForm) {
    event.preventDefault();
    const input = tagCreateForm.querySelector("[data-character-tag-create-input]");
    const formData = new FormData(tagCreateForm);
    const tag = String(formData.get("tag") || "").trim();
    if (!tag) return;
    const submitButton = tagCreateForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      const response = await fetch(tagCreateForm.action, {
        method: "POST",
        body: formData,
        headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      });
      if (!response.ok) throw new Error("Character tag was not created.");
      const payload = await response.json();
      if (payload.created) addCharacterTagToPage(payload.tag || tag);
      if (input) input.value = "";
    } catch {
      window.alert("Не удалось создать тег. Попробуйте ещё раз.");
    } finally {
      submitButton.disabled = false;
    }
    return;
  }
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && event.target.closest("[data-character-tag-rename-input]")) {
    event.preventDefault();
    saveCharacterTagRename().catch(() => showCharacterToast("Не удалось переименовать тег."));
    return;
  }
  if (event.key === "Enter" && event.target.closest("[data-character-tag-search], [data-character-filter-tag-search]")) {
    event.preventDefault();
    return;
  }
  if (event.key === "Control" || event.metaKey) setCharacterHoverMode(true);
  if (event.key === "Escape") {
    await closeCharacterModals();
    closeCharacterUploadModal();
    closeCharacterTagOrderModal();
    closeCharacterTagDeleteModal();
    closeCharacterTagRenameModal();
  }
});

document.addEventListener("keyup", (event) => {
  if (event.key === "Control" || (!event.ctrlKey && !event.metaKey)) setCharacterHoverMode(false);
});

window.addEventListener("blur", () => setCharacterHoverMode(false));
