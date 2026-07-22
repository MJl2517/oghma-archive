const godsPage = document.querySelector("[data-gods-page]");
const godDomainFilters = document.querySelector("[data-god-domain-filters]");
let includedGodDomains = new Set((godsPage?.dataset.activeDomains || "").split("||").filter(Boolean).map(normalizeGodDomain));
let excludedGodDomains = new Set((godsPage?.dataset.excludedDomains || "").split("||").filter(Boolean).map(normalizeGodDomain));
let includedGodAlignments = new Set((godsPage?.dataset.activeAlignments || "").split("||").filter(Boolean).map(normalizeGodDomain));
let excludedGodAlignments = new Set((godsPage?.dataset.excludedAlignments || "").split("||").filter(Boolean).map(normalizeGodDomain));
let selectedGodRanks = new Set((godsPage?.dataset.activeRanks || "").split("||").filter(Boolean).map(normalizeGodDomain));
let excludedGodRanks = new Set((godsPage?.dataset.excludedRanks || "").split("||").filter(Boolean).map(normalizeGodDomain));
let selectedGodPantheons = new Set((godsPage?.dataset.activePantheons || "").split("||").filter(Boolean).map(normalizeGodDomain));
let excludedGodPantheons = new Set((godsPage?.dataset.excludedPantheons || "").split("||").filter(Boolean).map(normalizeGodDomain));
let godFilterDebounce = null;
let godsRefreshToken = 0;
let draggedGodCategoryItem = null;
let godFilterPanelForcedOpen = false;
let godSelectModeEnabled = false;
const godScrollStorageKey = "ogma:gods:scroll";

function normalizeGodDomain(value) {
  return String(value || "").trim().toLocaleLowerCase("ru-RU");
}

function displayGodDomainsFromSet(domainSet) {
  const domains = [];
  document.querySelectorAll("[data-god-domain-item]").forEach((chip) => {
    if (domainSet.has(normalizeGodDomain(chip.dataset.godDomain))) domains.push(chip.dataset.godDomain);
  });
  return domains;
}

function updateGodDomainChips() {
  const hasFilters = includedGodDomains.size > 0 || excludedGodDomains.size > 0 || includedGodAlignments.size > 0 || excludedGodAlignments.size > 0 || selectedGodRanks.size > 0 || excludedGodRanks.size > 0 || selectedGodPantheons.size > 0 || excludedGodPantheons.size > 0;
  document.querySelectorAll("[data-god-domain-item]").forEach((chip) => {
    const domain = normalizeGodDomain(chip.dataset.godDomain);
    chip.classList.toggle("is-included", includedGodDomains.has(domain));
    chip.classList.toggle("is-excluded", excludedGodDomains.has(domain));
    chip.classList.toggle("is-muted", hasFilters && !includedGodDomains.has(domain) && !excludedGodDomains.has(domain));
  });
  document.querySelectorAll("[data-god-filter-item]").forEach((chip) => {
    const group = chip.dataset.godFilterGroup;
    const value = normalizeGodDomain(chip.dataset.godFilterValue);
    const selectedSet = group === "alignment" ? includedGodAlignments : group === "rank" ? selectedGodRanks : selectedGodPantheons;
    const excludedSet = group === "alignment" ? excludedGodAlignments : group === "rank" ? excludedGodRanks : excludedGodPantheons;
    chip.classList.toggle("is-included", selectedSet.has(value));
    chip.classList.toggle("is-excluded", excludedSet.has(value));
    chip.classList.toggle("is-muted", hasFilters && !selectedSet.has(value) && !excludedSet.has(value));
  });
}

function godFilterUrl() {
  const form = document.querySelector(".gods-filter-row");
  const url = new URL(form?.action || window.location.href, window.location.origin);
  new FormData(form).forEach((value, key) => {
    const clean = String(value || "").trim();
    if (clean && !["domain", "exclude_domain", "alignment", "exclude_alignment", "rank", "exclude_rank", "pantheon", "exclude_pantheon"].includes(key)) url.searchParams.append(key, clean);
  });
  displayGodDomainsFromSet(includedGodDomains).forEach((domain) => url.searchParams.append("domain", domain));
  displayGodDomainsFromSet(excludedGodDomains).forEach((domain) => url.searchParams.append("exclude_domain", domain));
  appendGodFilterValues(url, "alignment", includedGodAlignments);
  appendGodFilterValues(url, "exclude_alignment", excludedGodAlignments);
  document.querySelectorAll('[data-god-filter-item][data-god-filter-group="rank"]').forEach((chip) => {
    if (selectedGodRanks.has(normalizeGodDomain(chip.dataset.godFilterValue))) url.searchParams.append("rank", chip.dataset.godFilterValue);
    if (excludedGodRanks.has(normalizeGodDomain(chip.dataset.godFilterValue))) url.searchParams.append("exclude_rank", chip.dataset.godFilterValue);
  });
  document.querySelectorAll('[data-god-filter-item][data-god-filter-group="pantheon"]').forEach((chip) => {
    if (selectedGodPantheons.has(normalizeGodDomain(chip.dataset.godFilterValue))) url.searchParams.append("pantheon", chip.dataset.godFilterValue);
    if (excludedGodPantheons.has(normalizeGodDomain(chip.dataset.godFilterValue))) url.searchParams.append("exclude_pantheon", chip.dataset.godFilterValue);
  });
  return url.toString();
}

function appendGodFilterValues(url, param, valueSet) {
  document.querySelectorAll('[data-god-filter-item][data-god-filter-group="alignment"]').forEach((chip) => {
    if (valueSet.has(normalizeGodDomain(chip.dataset.godFilterValue))) url.searchParams.append(param, chip.dataset.godFilterValue);
  });
}

function syncGodFilterStateFromPage() {
  const page = document.querySelector("[data-gods-page]");
  includedGodDomains = new Set((page?.dataset.activeDomains || "").split("||").filter(Boolean).map(normalizeGodDomain));
  excludedGodDomains = new Set((page?.dataset.excludedDomains || "").split("||").filter(Boolean).map(normalizeGodDomain));
  includedGodAlignments = new Set((page?.dataset.activeAlignments || "").split("||").filter(Boolean).map(normalizeGodDomain));
  excludedGodAlignments = new Set((page?.dataset.excludedAlignments || "").split("||").filter(Boolean).map(normalizeGodDomain));
  selectedGodRanks = new Set((page?.dataset.activeRanks || "").split("||").filter(Boolean).map(normalizeGodDomain));
  excludedGodRanks = new Set((page?.dataset.excludedRanks || "").split("||").filter(Boolean).map(normalizeGodDomain));
  selectedGodPantheons = new Set((page?.dataset.activePantheons || "").split("||").filter(Boolean).map(normalizeGodDomain));
  excludedGodPantheons = new Set((page?.dataset.excludedPantheons || "").split("||").filter(Boolean).map(normalizeGodDomain));
  updateGodDomainChips();
}

async function loadGodsFragment(url, pushState = true) {
  const previousScrollY = window.scrollY;
  const activeSearch = document.activeElement?.matches?.('.gods-filter-row input[name="q"]') ? document.activeElement : null;
  const activeSearchSelection = activeSearch
    ? {
        start: activeSearch.selectionStart,
        end: activeSearch.selectionEnd,
        direction: activeSearch.selectionDirection,
      }
    : null;
  const refreshToken = ++godsRefreshToken;
  const current = document.querySelector("[data-gods-dynamic]");
  const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
  const html = await response.text();
  if (refreshToken !== godsRefreshToken) return;
  const incoming = new DOMParser().parseFromString(html, "text/html").querySelector("[data-gods-dynamic]");
  if (incoming && current) {
    current.replaceWith(incoming);
    syncGodFilterStateFromPage();
    if (godFilterPanelForcedOpen) {
      const panel = document.querySelector("[data-god-filter-panel]");
      const toggle = document.querySelector("[data-toggle-god-filters]");
      if (panel) panel.hidden = false;
      toggle?.classList.add("is-active");
      toggle?.setAttribute("aria-expanded", "true");
    }
    setGodSelectMode(godSelectModeEnabled);
    if (typeof updateFavoriteButtons === "function") updateFavoriteButtons();
    if (document.querySelector(".god-view-modal.is-open, .god-edit-modal.is-open")) {
      lockGodModalScroll();
      syncAllGodDomainPickers();
      window.scrollTo({ top: previousScrollY, left: 0, behavior: "auto" });
    }
    if (activeSearchSelection && !document.querySelector(".god-view-modal.is-open, .god-edit-modal.is-open")) {
      const nextSearch = document.querySelector('.gods-filter-row input[name="q"]');
      nextSearch?.focus({ preventScroll: true });
      nextSearch?.setSelectionRange(activeSearchSelection.start, activeSearchSelection.end, activeSearchSelection.direction);
    }
    if (pushState) window.history.pushState({}, "", url);
  } else {
    rememberGodScrollPosition();
    window.location.href = url;
  }
}

function selectedGodIds() {
  return [...document.querySelectorAll("[data-god-select]")].filter((input) => input.checked).map((input) => input.value);
}

function updateGodBulkDeleteState() {
  const ids = selectedGodIds();
  const count = document.querySelector("[data-god-selected-count]");
  const button = document.querySelector("[data-god-bulk-delete-button]");
  const inputs = document.querySelector("[data-god-bulk-delete-inputs]");
  const bar = document.querySelector("[data-god-bulk-delete-bar]");
  if (count) count.textContent = String(ids.length);
  if (button) button.disabled = ids.length === 0;
  if (bar) bar.hidden = !godSelectModeEnabled;
  if (inputs) {
    inputs.innerHTML = "";
    ids.forEach((id) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "god_ids";
      input.value = id;
      inputs.appendChild(input);
    });
  }
}

function setGodSelectMode(isEnabled) {
  godSelectModeEnabled = isEnabled;
  document.body.classList.toggle("is-selecting-gods", isEnabled);
  document.querySelector("[data-toggle-god-select-mode]")?.classList.toggle("is-active", isEnabled);
  document.querySelector("[data-toggle-god-select-mode]")?.setAttribute("aria-expanded", String(isEnabled));
  const form = document.querySelector("[data-god-bulk-delete-form]");
  if (form) form.hidden = !isEnabled;
  if (!isEnabled) {
    document.querySelectorAll("[data-god-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-god-card]")?.classList.remove("is-selected");
    });
  }
  updateGodBulkDeleteState();
}

function closeGodSelects(exceptSelect = null) {
  document.querySelectorAll("[data-god-select]").forEach((select) => {
    if (select === exceptSelect) return;
    const menu = select.querySelector(".god-select-menu");
    const button = select.querySelector("[data-god-select-button]");
    if (menu) menu.hidden = true;
    button?.setAttribute("aria-expanded", "false");
  });
}

function closeGodTagSelects(exceptSelect = null) {
  document.querySelectorAll("[data-god-tag-select]").forEach((select) => {
    if (select === exceptSelect) return;
    const menu = select.querySelector(".god-tag-select-menu");
    const button = select.querySelector("[data-god-tag-select-button]");
    if (menu) menu.hidden = true;
    button?.setAttribute("aria-expanded", "false");
  });
}

function godTagValues(select) {
  const input = select?.querySelector("[data-god-tag-value]");
  return (input?.value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function setGodTagValues(select, values) {
  const input = select?.querySelector("[data-god-tag-value]");
  const label = select?.querySelector("[data-god-tag-select-label]");
  if (!input || !label) return;
  const seen = new Set();
  const cleanValues = values.filter((value) => {
    const clean = String(value || "").trim();
    const key = normalizeGodDomain(clean);
    if (!clean || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  input.value = cleanValues.join(", ");
  label.textContent = input.value || "Выберите";
  select.querySelectorAll("[data-god-tag-option]").forEach((option) => {
    option.setAttribute("aria-selected", String(seen.has(normalizeGodDomain(option.dataset.godTagOption))));
  });
}

function filterGodTagOptions(searchInput) {
  const query = normalizeGodDomain(searchInput.value || "");
  searchInput.closest("[data-god-tag-select]")?.querySelectorAll("[data-god-tag-option]").forEach((option) => {
    const visible = !query || normalizeGodDomain(option.dataset.godTagOption || option.textContent || "").includes(query);
    option.hidden = !visible;
  });
}

function tagsFromInput(input) {
  return input.value.split(",").map((item) => item.trim()).filter(Boolean);
}

function setInputTags(input, tags) {
  const seen = new Set();
  const normalized = [];
  tags.forEach((tag) => {
    const clean = tag.trim();
    const key = normalizeGodDomain(clean);
    if (clean && !seen.has(key)) {
      seen.add(key);
      normalized.push(clean);
    }
  });
  input.value = normalized.join(", ");
  syncGodDomainPicker(input.closest("[data-god-form]"));
}

function toggleGodDomain(input, domain) {
  const tags = tagsFromInput(input);
  const key = normalizeGodDomain(domain);
  const hasTag = tags.some((item) => normalizeGodDomain(item) === key);
  setInputTags(input, hasTag ? tags.filter((item) => normalizeGodDomain(item) !== key) : [...tags, domain]);
}

function syncGodDomainPicker(form) {
  const input = form?.querySelector('input[name="domains"]');
  if (!input) return;
  const selected = new Set(tagsFromInput(input).map(normalizeGodDomain));
  form.querySelectorAll("[data-insert-god-domain]").forEach((button) => {
    const isSelected = selected.has(normalizeGodDomain(button.dataset.insertGodDomain));
    button.classList.toggle("is-active", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
}

function syncAllGodDomainPickers() {
  document.querySelectorAll("[data-god-form]").forEach(syncGodDomainPicker);
}

function lockGodModalScroll() {
  const hasStableScrollbarGutter = window.CSS?.supports?.("scrollbar-gutter: stable");
  const scrollbarWidth = hasStableScrollbarGutter ? 0 : Math.max(0, window.innerWidth - document.documentElement.clientWidth);
  document.body.style.setProperty("--modal-scrollbar-compensation", `${scrollbarWidth}px`);
  document.body.classList.add("has-modal");
}

function unlockGodModalScroll() {
  document.body.classList.remove("has-modal");
  document.body.style.removeProperty("--modal-scrollbar-compensation");
}

function rememberGodScrollPosition() {
  try {
    window.sessionStorage.setItem(godScrollStorageKey, String(window.scrollY));
  } catch (error) {
    // Session storage can be unavailable in strict browser modes.
  }
}

function restoreGodScrollPosition() {
  if (!document.querySelector(".god-view-modal.is-open, .god-edit-modal.is-open")) return;
  try {
    const saved = Number(window.sessionStorage.getItem(godScrollStorageKey));
    window.sessionStorage.removeItem(godScrollStorageKey);
    if (Number.isFinite(saved) && saved > 0) {
      requestAnimationFrame(() => window.scrollTo({ top: saved, left: 0, behavior: "auto" }));
    }
  } catch (error) {
    // Scroll restoration is a comfort feature; failing silently is safer here.
  }
}

function clearGodModalUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("god") && !url.searchParams.has("edit")) return;
  url.searchParams.delete("god");
  url.searchParams.delete("edit");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}

function openGodModal(modal) {
  if (!modal) return;
  lockGodModalScroll();
  syncAllGodDomainPickers();
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function closeGodModals(keepScrollLock = false) {
  document.querySelectorAll(".god-view-modal, .god-edit-modal, .god-create-modal").forEach((modal) => {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  });
  if (!keepScrollLock) {
    unlockGodModalScroll();
    clearGodModalUrl();
  }
}

document.addEventListener("click", (event) => {
  const selectButton = event.target.closest("[data-god-select-button]");
  if (selectButton) {
    event.preventDefault();
    const select = selectButton.closest("[data-god-select]");
    const menu = select?.querySelector(".god-select-menu");
    if (!menu) return;
    const nextOpen = menu.hidden;
    closeGodSelects(select);
    menu.hidden = !nextOpen;
    selectButton.setAttribute("aria-expanded", String(nextOpen));
    return;
  }

  const selectOption = event.target.closest("[data-god-select-value]");
  if (selectOption) {
    event.preventDefault();
    const select = selectOption.closest("[data-god-select]");
    const input = select?.querySelector('input[type="hidden"]');
    const label = select?.querySelector("[data-god-select-label]");
    const value = selectOption.dataset.godSelectValue || "";
    if (input) input.value = value;
    if (label) label.textContent = value || "Все";
    includedGodAlignments = value ? new Set([normalizeGodDomain(value)]) : new Set();
    excludedGodAlignments.clear();
    select?.querySelectorAll("[data-god-select-value]").forEach((option) => {
      option.setAttribute("aria-selected", String(option === selectOption));
    });
    closeGodSelects();
    if (select?.closest(".gods-filter-row")) {
      loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    }
    return;
  }

  if (!event.target.closest("[data-god-select]")) closeGodSelects();

  const tagSelectButton = event.target.closest("[data-god-tag-select-button]");
  if (tagSelectButton) {
    event.preventDefault();
    const select = tagSelectButton.closest("[data-god-tag-select]");
    const menu = select?.querySelector(".god-tag-select-menu");
    if (!menu) return;
    const nextOpen = menu.hidden;
    closeGodTagSelects(select);
    menu.hidden = !nextOpen;
    tagSelectButton.setAttribute("aria-expanded", String(nextOpen));
    if (nextOpen) select.querySelector("[data-god-tag-search]")?.focus();
    return;
  }

  const tagOption = event.target.closest("[data-god-tag-option]");
  if (tagOption) {
    event.preventDefault();
    const select = tagOption.closest("[data-god-tag-select]");
    const value = tagOption.dataset.godTagOption || "";
    const isMultiple = select?.dataset.godTagMultiple === "true";
    const values = godTagValues(select);
    const key = normalizeGodDomain(value);
    const hasValue = values.some((item) => normalizeGodDomain(item) === key);
    setGodTagValues(select, isMultiple ? (hasValue ? values.filter((item) => normalizeGodDomain(item) !== key) : [...values, value]) : [value]);
    if (!isMultiple) closeGodTagSelects();
    return;
  }

  if (!event.target.closest("[data-god-tag-select]")) closeGodTagSelects();

  const groupedFilterButton = event.target.closest("[data-god-toggle-filter]");
  if (groupedFilterButton) {
    const group = groupedFilterButton.dataset.godToggleFilter;
    const value = normalizeGodDomain(groupedFilterButton.dataset.godToggleValue);
    const selectedSet = group === "alignment" ? includedGodAlignments : group === "rank" ? selectedGodRanks : selectedGodPantheons;
    const excludedSet = group === "alignment" ? excludedGodAlignments : group === "rank" ? excludedGodRanks : excludedGodPantheons;
    selectedSet.has(value) ? selectedSet.delete(value) : selectedSet.add(value);
    excludedSet.delete(value);
    updateGodDomainChips();
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    return;
  }

  const groupedExcludeButton = event.target.closest("[data-god-exclude-filter]");
  if (groupedExcludeButton) {
    const group = groupedExcludeButton.dataset.godExcludeFilter;
    const value = normalizeGodDomain(groupedExcludeButton.dataset.godExcludeValue);
    const selectedSet = group === "alignment" ? includedGodAlignments : group === "rank" ? selectedGodRanks : selectedGodPantheons;
    const excludedSet = group === "alignment" ? excludedGodAlignments : group === "rank" ? excludedGodRanks : excludedGodPantheons;
    excludedSet.has(value) ? excludedSet.delete(value) : excludedSet.add(value);
    selectedSet.delete(value);
    updateGodDomainChips();
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    return;
  }

  const createButton = event.target.closest("[data-open-god-create]");
  if (createButton) {
    event.preventDefault();
    openGodModal(document.querySelector("[data-god-create-modal]"));
    return;
  }

  const viewButton = event.target.closest("[data-open-god-view]");
  if (viewButton) {
    event.preventDefault();
    const modal = document.querySelector(`[data-god-view-modal="${viewButton.dataset.openGodView}"]`);
    if (modal) {
      openGodModal(modal);
    } else if (viewButton.dataset.godViewUrl) {
      loadGodsFragment(viewButton.dataset.godViewUrl).catch(() => {
        rememberGodScrollPosition();
        window.location.href = viewButton.dataset.godViewUrl;
      });
    }
    return;
  }

  const editButton = event.target.closest("[data-open-god-edit]");
  if (editButton) {
    event.preventDefault();
    const modal = document.querySelector(`[data-god-edit-modal="${editButton.dataset.openGodEdit}"]`);
    if (modal) {
      closeGodModals(true);
      openGodModal(modal);
    } else if (editButton.dataset.godEditUrl) {
      loadGodsFragment(editButton.dataset.godEditUrl).catch(() => {
        rememberGodScrollPosition();
        window.location.href = editButton.dataset.godEditUrl;
      });
    }
    return;
  }

  if (event.target.closest("[data-close-god-modal]")) {
    closeGodModals();
    return;
  }

  const domainButton = event.target.closest("[data-insert-god-domain]");
  if (domainButton) {
    const input = domainButton.closest("[data-god-form]")?.querySelector('input[name="domains"]');
    if (input) toggleGodDomain(input, domainButton.dataset.insertGodDomain);
    return;
  }

  const includeButton = event.target.closest("[data-god-include-domain]");
  if (includeButton) {
    const domain = normalizeGodDomain(includeButton.dataset.godIncludeDomain);
    includedGodDomains.has(domain) ? includedGodDomains.delete(domain) : (includedGodDomains.add(domain), excludedGodDomains.delete(domain));
    updateGodDomainChips();
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    return;
  }

  const excludeButton = event.target.closest("[data-god-exclude-domain]");
  if (excludeButton) {
    const domain = normalizeGodDomain(excludeButton.dataset.godExcludeDomain);
    excludedGodDomains.has(domain) ? excludedGodDomains.delete(domain) : (excludedGodDomains.add(domain), includedGodDomains.delete(domain));
    updateGodDomainChips();
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    return;
  }

  const resetFilters = event.target.closest("[data-gods-reset-filters]");
  if (resetFilters) {
    event.preventDefault();
    includedGodDomains.clear();
    excludedGodDomains.clear();
    includedGodAlignments.clear();
    excludedGodAlignments.clear();
    selectedGodRanks.clear();
    excludedGodRanks.clear();
    selectedGodPantheons.clear();
    excludedGodPantheons.clear();
    loadGodsFragment(resetFilters.href).catch(() => window.location.href = resetFilters.href);
    return;
  }

  const toggleFilters = event.target.closest("[data-toggle-god-filters]");
  if (toggleFilters) {
    const panel = document.querySelector("[data-god-filter-panel]");
    if (panel) {
      panel.hidden = !panel.hidden;
      godFilterPanelForcedOpen = !panel.hidden;
      toggleFilters.classList.toggle("is-active", !panel.hidden);
      toggleFilters.setAttribute("aria-expanded", String(!panel.hidden));
    }
    return;
  }

  if (event.target.closest("[data-toggle-god-select-mode]")) {
    setGodSelectMode(!godSelectModeEnabled);
    return;
  }

  if (event.target.closest("[data-god-clear-selection]")) {
    document.querySelectorAll("[data-god-select]").forEach((input) => {
      input.checked = false;
      input.closest("[data-god-card]")?.classList.remove("is-selected");
    });
    updateGodBulkDeleteState();
    return;
  }

  const toggleCategoryEditor = event.target.closest("[data-toggle-god-category-editor]");
  if (toggleCategoryEditor) {
    const category = toggleCategoryEditor.dataset.toggleGodCategoryEditor;
    const panel = document.querySelector(`[data-god-category-editor="${category}"]`);
    if (panel) {
      panel.hidden = !panel.hidden;
      toggleCategoryEditor.classList.toggle("is-active", !panel.hidden);
      toggleCategoryEditor.setAttribute("aria-expanded", String(!panel.hidden));
    }
    return;
  }

  const saveCategoryOrder = event.target.closest("[data-save-god-category-order]");
  if (saveCategoryOrder) {
    const category = saveCategoryOrder.dataset.saveGodCategoryOrder;
    const values = [...document.querySelectorAll(`[data-god-category-order-item][data-god-category="${category}"]`)].map((item) => item.dataset.godCategoryValue);
    fetch("/gods/filters/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign_slug: document.querySelector('input[name="campaign"]')?.value || "", category, values }),
    })
      .then((response) => {
        if (!response.ok) throw new Error("Order was not saved.");
        return loadGodsFragment(window.location.href, false);
      })
      .catch(() => window.alert("Не удалось сохранить порядок."));
    return;
  }
});

document.addEventListener("input", (event) => {
  const tagSearch = event.target.closest("[data-god-tag-search]");
  if (tagSearch) {
    filterGodTagOptions(tagSearch);
    return;
  }

  const domainInput = event.target.closest('[data-god-form] input[name="domains"]');
  if (domainInput) {
    syncGodDomainPicker(domainInput.closest("[data-god-form]"));
    return;
  }

  const search = event.target.closest('.gods-filter-row input[name="q"]');
  if (!search) return;
  window.clearTimeout(godFilterDebounce);
  godFilterDebounce = window.setTimeout(() => {
    loadGodsFragment(godFilterUrl(), true).catch(() => window.location.href = godFilterUrl());
  }, 450);
});

document.addEventListener("change", (event) => {
  const importInput = event.target.closest("[data-god-import-input]");
  if (importInput) {
    const form = importInput.closest("[data-god-import-form]");
    if (form && importInput.files?.length) form.submit();
    return;
  }

  const godSelect = event.target.closest("[data-god-select]");
  if (godSelect) {
    godSelect.closest("[data-god-card]")?.classList.toggle("is-selected", godSelect.checked);
    updateGodBulkDeleteState();
    return;
  }

  if (event.target.closest('.gods-filter-row input[name="alignment"]')) {
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
  }
});

document.addEventListener("submit", (event) => {
  const filterForm = event.target.closest(".gods-filter-row");
  if (filterForm) {
    event.preventDefault();
    loadGodsFragment(godFilterUrl()).catch(() => window.location.href = godFilterUrl());
    return;
  }

  const categoryCreateForm = event.target.closest("[data-god-category-create-form]");
  if (categoryCreateForm) {
    event.preventDefault();
    const submitButton = categoryCreateForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    fetch(categoryCreateForm.action, {
      method: "POST",
      body: new FormData(categoryCreateForm),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Value was not created.");
        return response.json();
      })
      .then(() => loadGodsFragment(window.location.href, false))
      .catch(() => window.alert("Не удалось создать тег."))
      .finally(() => {
        if (submitButton) submitButton.disabled = false;
      });
    return;
  }

  const categoryDeleteForm = event.target.closest('form[action*="/gods/filters/delete"]');
  if (categoryDeleteForm) {
    event.preventDefault();
    fetch(categoryDeleteForm.action, {
      method: "POST",
      body: new FormData(categoryDeleteForm),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    })
      .then((response) => {
        if (!response.ok) throw new Error("Value was not deleted.");
        return response.json();
      })
      .then(() => loadGodsFragment(godFilterUrl(), false))
      .catch(() => window.alert("Не удалось удалить тег."));
  }
});

document.addEventListener("dragstart", (event) => {
  const item = event.target.closest("[data-god-category-order-item]");
  if (!item) return;
  draggedGodCategoryItem = item;
  item.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", item.dataset.godCategoryValue || "");
});

document.addEventListener("dragover", (event) => {
  const targetItem = event.target.closest("[data-god-category-order-item]");
  if (!targetItem || !draggedGodCategoryItem || targetItem === draggedGodCategoryItem) return;
  if (targetItem.dataset.godCategory !== draggedGodCategoryItem.dataset.godCategory) return;
  event.preventDefault();
  const list = targetItem.closest("[data-god-category-order-list]");
  if (!list) return;
  const targetRect = targetItem.getBoundingClientRect();
  list.insertBefore(draggedGodCategoryItem, event.clientY > targetRect.top + targetRect.height / 2 ? targetItem.nextSibling : targetItem);
});

document.addEventListener("drop", (event) => {
  if (!draggedGodCategoryItem) return;
  event.preventDefault();
});

document.addEventListener("dragend", () => {
  draggedGodCategoryItem?.classList.remove("is-dragging");
  draggedGodCategoryItem = null;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeGodSelects();
    closeGodTagSelects();
    closeGodModals();
  }
});

updateGodDomainChips();
syncAllGodDomainPickers();
if (document.querySelector(".god-view-modal.is-open, .god-edit-modal.is-open")) {
  lockGodModalScroll();
  syncAllGodDomainPickers();
  restoreGodScrollPosition();
}

window.addEventListener("popstate", () => {
  loadGodsFragment(window.location.href, false);
});
