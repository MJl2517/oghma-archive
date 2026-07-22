const modal = document.querySelector("[data-search-modal]");
const input = document.querySelector("[data-search-input]");
let rows = [...document.querySelectorAll("[data-result-row]")];
const openButtons = document.querySelectorAll("[data-open-search]");
const closeButtons = document.querySelectorAll("[data-close-search]");
const emptySearchMessage = document.querySelector("[data-search-empty]");
const previewModal = document.querySelector("[data-spotlight-preview-modal]");
const previewKicker = previewModal?.querySelector("[data-spotlight-preview-kicker]");
const previewTitle = previewModal?.querySelector("[data-spotlight-preview-title]");
const previewMeta = previewModal?.querySelector("[data-spotlight-preview-meta]");
const previewBody = previewModal?.querySelector("[data-spotlight-preview-body]");
const previewPage = previewModal?.querySelector("[data-spotlight-preview-page]");
const previewHint = previewModal?.querySelector("[data-spotlight-preview-hint]");
const previewFavorite = previewModal?.querySelector("[data-favorite-toggle]");
let activeRowIndex = -1;
let previewRequestToken = 0;
const allowedMaterials = new Set(
  String(modal?.dataset?.spotlightMaterials || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
);
const allowedCampaigns = new Set(
  String(modal?.dataset?.spotlightCampaigns || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
);
const campaignMode = String(modal?.dataset?.spotlightCampaignMode || "all").trim().toLowerCase();
const spotlightBackend = String(modal?.dataset?.spotlightBackend || "json").trim().toLowerCase();
const useServerSearch = spotlightBackend === "sqlite";
let requestToken = 0;

function searchableText(row) {
  return [row.dataset.title, row.dataset.description, row.dataset.terms].join(" ").toLowerCase();
}

function getVisibleRows() {
  return rows.filter((row) => !row.hidden);
}

function setActiveRow(index) {
  const visibleRows = getVisibleRows();
  visibleRows.forEach((row) => {
    row.classList.remove("is-active");
    row.setAttribute("aria-selected", "false");
  });
  if (index < 0 || index >= visibleRows.length) {
    activeRowIndex = -1;
    return null;
  }
  activeRowIndex = index;
  const row = visibleRows[activeRowIndex];
  row.classList.add("is-active");
  row.setAttribute("aria-selected", "true");
  row.scrollIntoView({ block: "nearest" });
  return row;
}

function moveActiveRow(direction) {
  const visibleRows = getVisibleRows();
  if (!visibleRows.length) {
    setActiveRow(-1);
    return null;
  }
  if (activeRowIndex < 0) {
    return setActiveRow(direction > 0 ? 0 : visibleRows.length - 1);
  }
  const nextIndex = (activeRowIndex + direction + visibleRows.length) % visibleRows.length;
  return setActiveRow(nextIndex);
}

function filterRows(query) {
  if (useServerSearch) {
    return;
  }
  const normalizedQuery = query.trim().toLowerCase();
  let visibleCount = 0;
  rows.forEach((row) => {
    const materialKind = row.dataset.searchKind || "";
    const campaignSlug = row.dataset.searchCampaign || "";
    const materialAllowed = !allowedMaterials.size || allowedMaterials.has(materialKind);
    const campaignAllowed = !campaignSlug || campaignMode !== "selected" || allowedCampaigns.has(campaignSlug);
    const isVisible =
      normalizedQuery.length >= 3 &&
      materialAllowed &&
      campaignAllowed &&
      searchableText(row).includes(normalizedQuery);
    row.hidden = !isVisible;
    row.style.display = isVisible ? "" : "none";
    if (isVisible) visibleCount += 1;
  });

  const visibleRows = getVisibleRows();
  if (!visibleRows.length) {
    setActiveRow(-1);
  } else if (activeRowIndex >= visibleRows.length) {
    setActiveRow(visibleRows.length - 1);
  }

  if (emptySearchMessage) {
    emptySearchMessage.hidden = visibleCount > 0;
    emptySearchMessage.textContent = normalizedQuery.length < 3 ? "Введите минимум 3 символа." : "Нет данных.";
  }
}

function rowIconClass(kind) {
  if (kind === "rules") return "icon-rune";
  if (kind === "maps") return "icon-map";
  if (kind === "campaigns") return "icon-archive";
  if (kind === "gods") return "icon-rune";
  if (kind === "generators") return "icon-rune";
  return "icon-archive";
}

function kindLabel(kind) {
  if (kind === "rules") return "Правило";
  if (kind === "campaigns") return "Кампейн";
  if (kind === "characters") return "Персонаж";
  if (kind === "party_members") return "Персонаж группы";
  if (kind === "notes") return "Заметка";
  if (kind === "gods") return "Божество";
  if (kind === "maps") return "Карта";
  if (kind === "scenes") return "Сцена";
  if (kind === "audio") return "Аудио";
  if (kind === "resources") return "Ресурс";
  if (kind === "generators") return "Генератор";
  return "Материал";
}

function resultMeta(item) {
  const label = kindLabel(item.kind);
  const campaign = String(item.campaign_name || item.campaign_slug || "").trim();
  return campaign ? `${label} · ${campaign}` : label;
}

function rowPreviewUrl(row) {
  if (row.dataset.spotlightPreviewUrl) return row.dataset.spotlightPreviewUrl;
  if (row.matches("a[href]")) return row.getAttribute("href") || "";
  if (row.dataset.openRuleModal) return `/rules?rule=${encodeURIComponent(row.dataset.openRuleModal)}`;
  return "";
}

function rowPreviewMeta(row) {
  const kind = kindLabel(row.dataset.searchKind || "");
  const campaign = String(row.dataset.searchCampaign || "").trim();
  if (campaign) return `${kind} · ${campaign}`;
  const smallText = row.querySelector("small")?.textContent?.trim();
  return smallText || kind;
}

function escapeSearchHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setPreviewMeta(html, text = "") {
  if (!previewMeta) return;
  previewMeta.hidden = !(html || text);
  if (html) previewMeta.innerHTML = html;
  else previewMeta.textContent = text;
}

function syncPreviewFavorite(row, kind, title) {
  if (!previewFavorite) return;
  const isRule = kind === "rules";
  previewFavorite.hidden = !isRule;
  previewFavorite.dataset.favoriteType = isRule ? "rule" : "";
  previewFavorite.dataset.favoriteId = isRule ? row.dataset.spotlightPreviewId || row.dataset.openRuleModal || "" : "";
  previewFavorite.dataset.favoriteCampaign = "";
  previewFavorite.dataset.favoriteTitle = isRule ? title || "" : "";
  previewFavorite.setAttribute("aria-label", isRule ? "Добавить правило в избранное" : "Добавить в избранное");
  document.dispatchEvent(new CustomEvent("favorites:refresh-buttons"));
}

function setPreviewHint(message = "") {
  if (!previewHint) return;
  previewHint.textContent = message;
  previewHint.hidden = !message;
}

async function loadRulePreview(row, token) {
  if (!previewBody) return;
  const itemId = row.dataset.spotlightPreviewId || row.dataset.openRuleModal || "";
  const kind = row.dataset.searchKind || "";
  const campaign = row.dataset.searchCampaign || "";
  if (!kind || !itemId) return;
  previewBody.hidden = false;
  previewBody.innerHTML = "<p>Загружаю материал...</p>";

  try {
    const url = new URL("/spotlight/preview", window.location.origin);
    url.searchParams.set("kind", kind);
    url.searchParams.set("id", itemId);
    if (campaign) url.searchParams.set("campaign", campaign);
    const response = await fetch(url, {
      headers: { Accept: "application/json", "X-Requested-With": "fetch" },
    });
    const payload = await response.json();
    if (token !== previewRequestToken) return;
    if (!response.ok || !payload.ok) throw new Error(payload.error || "preview_not_found");
    if (previewKicker) previewKicker.textContent = payload.kicker || kindLabel(kind);
    if (previewTitle) previewTitle.textContent = payload.title || row.dataset.title || "Материал";
    setPreviewMeta(payload.meta_html || "", payload.meta || rowPreviewMeta(row));
    if (previewPage) {
      previewPage.href = payload.page_url || rowPreviewUrl(row) || "#";
      previewPage.hidden = !(payload.page_url || rowPreviewUrl(row));
    }
    syncPreviewFavorite(row, kind, payload.title || row.dataset.title || "Материал");
    previewBody.innerHTML = renderSpotlightPreviewBody(payload, kind);
    setPreviewHint("");
  } catch (error) {
    if (token !== previewRequestToken) return;
    previewBody.innerHTML = "<p>Не удалось загрузить содержимое материала.</p>";
    setPreviewHint("Можно открыть страницу материала кнопкой ниже.");
  }
}

function renderSpotlightPreviewBody(payload, kind = "") {
  if (kind === "rules") {
    return payload.content_html || "<p>Текста пока нет.</p>";
  }
  const media = payload.image_url
    ? `<figure class="spotlight-preview-media"><img src="${escapeSearchHtml(payload.image_url)}" alt="${escapeSearchHtml(payload.title || "Материал")}"></figure>`
    : "";
  const tags = Array.isArray(payload.tags) && payload.tags.length
    ? `<div class="spotlight-preview-tags">${payload.tags.map((tag) => `<span>${escapeSearchHtml(tag)}</span>`).join("")}</div>`
    : "";
  const content = payload.content_html ? `<div class="spotlight-preview-main">${payload.content_html}</div>` : "";
  const fields = Array.isArray(payload.fields) && payload.fields.length
    ? `<div class="spotlight-preview-fields">${payload.fields
        .map((field) => `
          <section class="spotlight-preview-field">
            <strong>${escapeSearchHtml(field.label || "")}</strong>
            <div>${field.value_html || escapeSearchHtml(field.value || "")}</div>
          </section>
        `)
        .join("")}</div>`
    : "";
  return [media, tags, content, fields].filter(Boolean).join("") || "<p>Содержимое пока не добавлено.</p>";
}

function openSpotlightPreview(row) {
  if (!previewModal || !row) return;
  const token = ++previewRequestToken;
  const url = rowPreviewUrl(row);
  const title = row.dataset.title || row.querySelector("strong")?.textContent?.trim() || "Материал";
  const kind = kindLabel(row.dataset.searchKind || "");
  const rawKind = row.dataset.searchKind || "";

  if (previewKicker) previewKicker.textContent = kind;
  if (previewTitle) previewTitle.textContent = title;
  setPreviewMeta("", rowPreviewMeta(row));
  syncPreviewFavorite(row, rawKind, title);
  if (previewBody) {
    previewBody.hidden = true;
    previewBody.innerHTML = "";
  }
  setPreviewHint(
    url
      ? "Spotlight открыл результат без перехода. Используйте кнопку ниже, если нужно перейти на страницу материала."
      : "У этого результата нет отдельной страницы для перехода.",
  );
  if (previewPage) {
    previewPage.href = url || "#";
    previewPage.hidden = !url;
  }

  previewModal.classList.add("is-open");
  previewModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");

  loadRulePreview(row, token);
}

function closeSpotlightPreview() {
  if (!previewModal) return;
  previewRequestToken += 1;
  previewModal.classList.remove("is-open");
  previewModal.setAttribute("aria-hidden", "true");
  if (!document.querySelector(".spotlight.is-open, .map-modal.is-open, .rule-modal.is-open")) {
    document.body.classList.remove("has-modal");
  }
}

function removeDynamicRows() {
  document.querySelectorAll("[data-result-row-dynamic='1']").forEach((row) => row.remove());
  rows = [...document.querySelectorAll("[data-result-row]")];
}

function ensureServerRows(query, items) {
  removeDynamicRows();
  rows.forEach((row) => {
    row.hidden = true;
    row.style.display = "none";
  });
  const container = document.querySelector("[data-search-results]");
  if (!container) return;
  items.forEach((item) => {
    const el = document.createElement("button");
    el.className = "result-row result-row-button";
    el.type = "button";
    if (item.kind === "rules") {
      el.dataset.openRuleModal = item.rule_id || "";
    }
    el.tabIndex = 0;
    el.dataset.resultRow = "";
    el.dataset.resultRowDynamic = "1";
    el.dataset.searchKind = item.kind || "";
    el.dataset.searchCampaign = item.campaign_slug || "";
    el.dataset.spotlightPreviewId = item.item_id || item.rule_id || "";
    el.dataset.spotlightPreviewUrl = item.url || "";
    el.dataset.title = item.title || "";
    el.dataset.description = item.description || "";
    el.dataset.descriptionHtml = item.description_html || "";
    el.dataset.terms = `${item.kind || ""} ${item.title || ""} ${item.description || ""}`.trim();
    const icon = document.createElement("span");
    icon.className = `card-icon ${rowIconClass(item.kind)}`;
    icon.setAttribute("aria-hidden", "true");
    const textWrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.title || "";
    const small = document.createElement("small");
    small.textContent = resultMeta(item);
    textWrap.appendChild(strong);
    textWrap.appendChild(small);
    el.appendChild(icon);
    el.appendChild(textWrap);
    container.appendChild(el);
  });
  rows = [...document.querySelectorAll("[data-result-row]")];
  const visibleCount = items.length;
  if (emptySearchMessage) {
    emptySearchMessage.hidden = visibleCount > 0;
    emptySearchMessage.textContent = query.trim().length < 3 ? "Введите минимум 3 символа." : "Нет данных.";
  }
}

async function filterRowsServer(query) {
  const normalizedQuery = query.trim();
  if (normalizedQuery.length < 3) {
    removeDynamicRows();
    rows.forEach((row) => {
      row.hidden = true;
      row.style.display = "none";
    });
    if (emptySearchMessage) {
      emptySearchMessage.hidden = false;
      emptySearchMessage.textContent = "Введите минимум 3 символа.";
    }
    setActiveRow(-1);
    return;
  }
  const token = ++requestToken;
  try {
    const response = await fetch(`/spotlight/search?q=${encodeURIComponent(normalizedQuery)}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (token !== requestToken) return;
    const items = Array.isArray(payload.items) ? payload.items : [];
    ensureServerRows(normalizedQuery, items);
    setActiveRow(items.length ? 0 : -1);
  } catch (error) {
    if (token !== requestToken) return;
    ensureServerRows(normalizedQuery, []);
    setActiveRow(-1);
  }
}

function openSearch() {
  rows = [...document.querySelectorAll("[data-result-row]")];
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
  input.value = "";
  if (useServerSearch) {
    removeDynamicRows();
    rows.forEach((row) => {
      row.hidden = true;
      row.style.display = "none";
    });
    if (emptySearchMessage) {
      emptySearchMessage.hidden = false;
      emptySearchMessage.textContent = "Введите минимум 3 символа.";
    }
  } else {
    filterRows("");
  }
  setActiveRow(-1);
  window.setTimeout(() => input.focus(), 30);
}

function closeSearch() {
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (!document.querySelector("[data-spotlight-preview-modal].is-open")) {
    document.body.classList.remove("has-modal");
  }
  setActiveRow(-1);
}

openButtons.forEach((button) => button.addEventListener("click", openSearch));
closeButtons.forEach((button) => button.addEventListener("click", closeSearch));
input.addEventListener("input", (event) => {
  if (useServerSearch) {
    filterRowsServer(event.target.value);
    return;
  }
  filterRows(event.target.value);
});
input.addEventListener("keydown", (event) => {
  if (!modal.classList.contains("is-open")) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    moveActiveRow(1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    moveActiveRow(-1);
    return;
  }
  if (event.key === "Enter") {
    const row = setActiveRow(activeRowIndex);
    if (!row) return;
    event.preventDefault();
    row.click();
  }
});

document.addEventListener("keydown", (event) => {
  const isQuestionSearch =
    event.shiftKey &&
    (event.key === "?" || event.code === "Slash" || event.code === "Digit7") &&
    !event.target.matches("input, textarea");

  if (isQuestionSearch) {
    event.preventDefault();
    openSearch();
  }

  if (event.key === "Escape" && previewModal?.classList.contains("is-open")) {
    closeSpotlightPreview();
    return;
  }

  if (event.key === "Escape" && modal.classList.contains("is-open")) {
    closeSearch();
  }

  const pageSearchInput = event.target.closest?.(".page-search-form input[name='q']");
  if (event.key === "Escape" && pageSearchInput) {
    event.preventDefault();
    if (pageSearchInput.value) {
      pageSearchInput.value = "";
      pageSearchInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    pageSearchInput.blur();
  }
});

document.addEventListener("keydown", (event) => {
  const row = event.target.closest("[data-result-row]");
  if (!row) return;
  if (event.key === "Enter") {
    row.click();
  }
});

document.addEventListener("mouseover", (event) => {
  const row = event.target.closest("[data-result-row]");
  if (!row) return;
  const visibleRows = getVisibleRows();
  const index = visibleRows.indexOf(row);
  if (index >= 0) setActiveRow(index);
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-spotlight-preview]")) {
    closeSpotlightPreview();
    return;
  }

  const searchResult = event.target.closest("[data-search-modal] [data-result-row]");
  if (searchResult) {
    event.preventDefault();
    closeSearch();
    openSpotlightPreview(searchResult);
  }
});
