let favoriteState = null;
let pendingFavoriteItem = null;
let favoriteToastTimer = null;
let favoriteLastActiveGroupId = "";
let favoriteSortMode = false;
let favoriteItemSortGroupId = "";
let favoriteDragState = null;
const favoriteOpenGroupIds = new Set();

function favoriteKey(type, id, campaign = "") {
  return `${type || ""}||${id || ""}||${campaign || ""}`;
}

function favoriteDock() {
  return document.querySelector("[data-favorites-dock]");
}

function favoritePanel() {
  return document.querySelector("[data-favorites-panel]");
}

function favoritePicker() {
  return document.querySelector("[data-favorite-picker]");
}

function favoriteActiveGroup() {
  if (!favoriteState?.groups?.length) return null;
  return favoriteState.groups.find((group) => group.id === favoriteState.active_group_id) || favoriteState.groups[0];
}

function favoriteButtonItem(button) {
  return {
    type: button.dataset.favoriteType || "",
    id: button.dataset.favoriteId || "",
    campaign_slug: button.dataset.favoriteCampaign || "",
    title: button.dataset.favoriteTitle || "",
  };
}

function isFavoriteItemActive(item) {
  const key = favoriteKey(item.type, item.id, item.campaign_slug);
  return Boolean(favoriteState?.memberships?.[key]?.length);
}

function showFavoriteToast(message) {
  let toast = document.querySelector("[data-favorite-toast]");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "copy-toast favorite-toast";
    toast.dataset.favoriteToast = "";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(favoriteToastTimer);
  favoriteToastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1700);
}

async function loadFavorites() {
  const response = await fetch("/favorites", { headers: { "Accept": "application/json", "X-Requested-With": "fetch" } });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "favorites_failed");
  favoriteState = payload;
  renderFavorites();
  updateFavoriteButtons();
  return payload;
}

async function submitFavoriteForm(url, formData = new FormData()) {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "favorites_failed");
  favoriteState = payload;
  renderFavorites();
  updateFavoriteButtons();
  return payload;
}

async function submitFavoriteJson(url, data = {}) {
  const response = await fetch(url, {
    method: "POST",
    body: JSON.stringify(data),
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "X-Requested-With": "fetch",
    },
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(payload.error || "favorites_failed");
  favoriteState = payload;
  renderFavorites();
  updateFavoriteButtons();
  return payload;
}

function toggleFavoritesPanel(force = null) {
  const dock = favoriteDock();
  const panel = favoritePanel();
  if (!dock || !panel) return;
  const shouldOpen = force ?? !dock.classList.contains("is-open");
  dock.classList.toggle("is-open", shouldOpen);
  panel.setAttribute("aria-hidden", String(!shouldOpen));
  document.querySelectorAll("[data-favorites-toggle]").forEach((button) => {
    button.setAttribute("aria-expanded", String(shouldOpen));
  });
  if (shouldOpen && !favoriteState) loadFavorites().catch(() => showFavoriteToast("Не удалось открыть избранное"));
}

function closeFavoritePicker() {
  const picker = favoritePicker();
  if (!picker) return;
  picker.classList.remove("is-open");
  picker.setAttribute("aria-hidden", "true");
  pendingFavoriteItem = null;
}

function openFavoritePicker(item) {
  const picker = favoritePicker();
  const list = document.querySelector("[data-favorite-picker-groups]");
  if (!picker || !list || !favoriteState) return;
  pendingFavoriteItem = item;
  const title = document.querySelector("[data-favorite-picker-title]");
  if (title) title.textContent = item.title ? `Группы: ${item.title}` : "Выбрать группу";
  list.replaceChildren();
  favoriteState.groups.forEach((group) => {
    const key = favoriteKey(item.type, item.id, item.campaign_slug);
    const active = (favoriteState.memberships?.[key] || []).includes(group.id);
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.favoritePickerGroup = group.id;
    button.classList.toggle("is-active", active);
    const marker = document.createElement("span");
    marker.textContent = active ? "★" : "☆";
    const name = document.createElement("strong");
    name.textContent = group.name || "Основное";
    const count = document.createElement("small");
    count.textContent = `${group.count || 0}`;
    button.append(marker, name, count);
    list.appendChild(button);
  });
  picker.classList.add("is-open");
  picker.setAttribute("aria-hidden", "false");
}

async function toggleFavoriteItem(item, groupId = "") {
  if (!item.type || !item.id) return;
  const formData = new FormData();
  formData.append("type", item.type);
  formData.append("id", item.id);
  formData.append("campaign_slug", item.campaign_slug || "");
  if (groupId) formData.append("group_id", groupId);
  const payload = await submitFavoriteForm("/favorites/items/toggle", formData);
  const changed = payload.changed || {};
  showFavoriteToast(changed.added ? "Добавлено в избранное" : "Убрано из избранного");
}

function updateFavoriteButtons() {
  document.querySelectorAll("[data-favorite-toggle]").forEach((button) => {
    const item = favoriteButtonItem(button);
    const active = item.type && item.id && isFavoriteItemActive(item);
    button.classList.toggle("is-active", active);
    button.textContent = active ? "★" : "☆";
    button.setAttribute("aria-pressed", String(active));
  });
}

document.addEventListener("favorites:refresh-buttons", updateFavoriteButtons);

function favoriteSortItemPayload(element) {
  return {
    type: element.dataset.favoriteType || "",
    id: element.dataset.favoriteId || "",
    campaign_slug: element.dataset.favoriteCampaign || "",
  };
}

function updateFavoriteSortControls() {
  const dock = favoriteDock();
  if (dock) dock.classList.toggle("is-sorting", favoriteSortMode);
  if (dock) dock.classList.toggle("is-sorting-items", Boolean(favoriteItemSortGroupId));
  document.querySelectorAll("[data-favorites-sort-toggle]").forEach((button) => {
    button.classList.toggle("is-active", favoriteSortMode);
    button.setAttribute("aria-pressed", String(favoriteSortMode));
  });
  document.querySelectorAll("[data-favorites-items-sort-toggle]").forEach((button) => {
    const active = button.dataset.favoriteGroupId === favoriteItemSortGroupId;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function renderFavoriteGroupsLegacy() {
  const list = document.querySelector("[data-favorites-groups]");
  if (!list || !favoriteState) return;
  list.replaceChildren();
  favoriteState.groups.forEach((group) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.favoriteGroup = group.id;
    button.classList.toggle("is-active", group.id === favoriteState.active_group_id);
    const name = document.createElement("span");
    name.textContent = group.name || "Основное";
    const count = document.createElement("small");
    count.textContent = String(group.count || 0);
    button.append(name, count);
    list.appendChild(button);
  });
}

function renderFavoriteActiveTools(group) {
  const title = document.querySelector("[data-favorites-active-title]");
  if (title) title.textContent = group?.name || "Основное";
  const tools = document.querySelector("[data-favorites-active-tools]");
  const renameForm = document.querySelector("[data-favorite-rename-group-form]");
  const deleteForm = document.querySelector("[data-favorite-delete-group-form]");
  if (!tools || !group) return;
  tools.hidden = false;
  const renameInput = renameForm?.querySelector('input[name="name"]');
  if (renameInput) renameInput.value = group.name || "Основное";
  if (renameForm) renameForm.action = `/favorites/groups/${encodeURIComponent(group.id)}/rename`;
  if (deleteForm) deleteForm.action = `/favorites/groups/${encodeURIComponent(group.id)}/delete`;
}

function createFavoriteItemNode(item, groupId) {
  const sortingThisGroup = favoriteItemSortGroupId === groupId;
  const row = document.createElement("article");
  row.className = "favorite-item";
  row.classList.toggle("is-missing", Boolean(item.missing));
  row.dataset.favoriteSortItem = "";
  row.dataset.favoriteType = item.type || "";
  row.dataset.favoriteId = item.id || "";
  row.dataset.favoriteCampaign = item.campaign_slug || "";
  row.draggable = sortingThisGroup;
  const dragHandle = document.createElement("span");
  dragHandle.className = "favorites-drag-handle favorite-item-drag-handle";
  dragHandle.setAttribute("aria-hidden", "true");
  dragHandle.textContent = "↕";
  dragHandle.draggable = sortingThisGroup;
  const link = document.createElement("a");
  link.href = item.url || "#";
  link.dataset.favoriteItemLink = "";
  link.dataset.favoriteType = item.type || "";
  link.dataset.favoriteId = item.id || "";
  link.dataset.favoriteCampaign = item.campaign_slug || "";
  const title = document.createElement("strong");
  title.textContent = item.title || "Элемент";
  const subtitle = document.createElement("small");
  subtitle.textContent = item.subtitle || item.category_label || "";
  link.append(title, subtitle);
  const remove = document.createElement("button");
  remove.type = "button";
  remove.dataset.favoriteRemove = "";
  remove.dataset.favoriteType = item.type || "";
  remove.dataset.favoriteId = item.id || "";
  remove.dataset.favoriteCampaign = item.campaign_slug || "";
  remove.dataset.favoriteGroupId = groupId || "";
  remove.setAttribute("aria-label", "Убрать из избранного");
  remove.textContent = "×";
  row.append(dragHandle, link, remove);
  return row;
}

function renderFavoriteContent(group) {
  const content = document.querySelector("[data-favorites-content]");
  if (!content) return;
  content.replaceChildren();
  if (!group?.categories?.length) {
    const empty = document.createElement("div");
    empty.className = "favorites-empty";
    empty.dataset.favoritesEmpty = "";
    const title = document.createElement("strong");
    title.textContent = "В этой группе пока пусто.";
    const text = document.createElement("span");
    text.textContent = "Откройте карточку и нажмите ★.";
    empty.append(title, text);
    content.appendChild(empty);
    return;
  }
  group.categories.forEach((category) => {
    const section = document.createElement("section");
    section.className = "favorites-category";
    section.dataset.favoritesCategory = category.type || "";
    const heading = document.createElement("h3");
    heading.textContent = category.label || "";
    const items = document.createElement("div");
    (category.items || []).forEach((item) => items.appendChild(createFavoriteItemNode(item, group.id)));
    section.append(heading, items);
    content.appendChild(section);
  });
}

function renderFavoritesLegacy() {
  if (!favoriteState) return;
  const dock = favoriteDock();
  if (dock) dock.dataset.favoritesActiveGroup = favoriteState.active_group_id || "";
  const group = favoriteActiveGroup();
  renderFavoriteGroups();
  renderFavoriteActiveTools(group);
  renderFavoriteContent(group);
}

function createFavoriteEmptyNode() {
  const empty = document.createElement("div");
  empty.className = "favorites-empty";
  empty.dataset.favoritesEmpty = "";
  const title = document.createElement("strong");
  title.textContent = "В этой группе пока пусто.";
  const text = document.createElement("span");
  text.textContent = "Откройте карточку и нажмите ★.";
  empty.append(title, text);
  return empty;
}

function createFavoriteGroupTools(group) {
  const tools = document.createElement("div");
  tools.className = "favorites-active-tools";

  const sortButton = document.createElement("button");
  sortButton.type = "button";
  sortButton.className = "favorites-sort-button favorites-items-sort-button";
  sortButton.dataset.favoritesItemsSortToggle = "";
  sortButton.dataset.favoriteGroupId = group.id || "";
  sortButton.title = "Сортировать элементы группы";
  sortButton.setAttribute("aria-label", "Сортировать элементы группы");
  sortButton.setAttribute("aria-pressed", "false");
  sortButton.textContent = "↕";

  const renameForm = document.createElement("form");
  renameForm.className = "favorites-rename-form";
  renameForm.action = `/favorites/groups/${encodeURIComponent(group.id)}/rename`;
  renameForm.method = "post";
  renameForm.dataset.favoriteRenameGroupForm = "";

  const renameInput = document.createElement("input");
  renameInput.name = "name";
  renameInput.value = group.name || "Основное";
  renameInput.setAttribute("aria-label", "Название группы");

  const renameButton = document.createElement("button");
  renameButton.type = "submit";
  renameButton.className = "favorites-save-button";
  renameButton.title = "Сохранить название";
  renameButton.setAttribute("aria-label", "Сохранить название");
  const saveIcon = document.createElement("span");
  saveIcon.className = "favorite-save-icon";
  saveIcon.setAttribute("aria-hidden", "true");
  renameButton.appendChild(saveIcon);
  renameForm.append(renameInput, renameButton);

  const deleteForm = document.createElement("form");
  deleteForm.action = `/favorites/groups/${encodeURIComponent(group.id)}/delete`;
  deleteForm.method = "post";
  deleteForm.dataset.favoriteDeleteGroupForm = "";

  const deleteButton = document.createElement("button");
  deleteButton.type = "submit";
  deleteButton.title = "Удалить группу";
  deleteButton.setAttribute("aria-label", "Удалить группу");
  deleteButton.textContent = "×";
  deleteForm.appendChild(deleteButton);

  tools.append(sortButton, renameForm, deleteForm);
  return tools;
}

function createFavoriteCategoryNode(category, groupId) {
  const section = document.createElement("section");
  section.className = "favorites-category";
  section.dataset.favoritesCategory = category.type || "";

  const heading = document.createElement("h3");
  heading.textContent = category.label || "";

  const items = document.createElement("div");
  (category.items || []).forEach((item) => items.appendChild(createFavoriteItemNode(item, groupId)));

  section.append(heading, items);
  return section;
}

function createFavoriteGroupNode(group) {
  const groupId = group.id || "";
  const details = document.createElement("details");
  details.className = "favorites-group";
  details.dataset.favoriteGroup = groupId;
  details.classList.toggle("is-active", groupId === favoriteState.active_group_id);
  details.classList.toggle("is-sorting-items", groupId === favoriteItemSortGroupId);
  details.open = favoriteOpenGroupIds.has(groupId);
  details.draggable = favoriteSortMode;

  const summary = document.createElement("summary");
  summary.draggable = favoriteSortMode;
  const dragHandle = document.createElement("span");
  dragHandle.className = "favorites-drag-handle";
  dragHandle.setAttribute("aria-hidden", "true");
  dragHandle.textContent = "↕";
  dragHandle.draggable = favoriteSortMode;
  const arrow = document.createElement("span");
  arrow.className = "favorites-group-arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "›";
  const name = document.createElement("strong");
  name.textContent = group.name || "Основное";
  const count = document.createElement("small");
  count.textContent = String(group.count || 0);
  summary.append(dragHandle, arrow, name, count);

  const body = document.createElement("div");
  body.className = "favorites-group-body";
  body.appendChild(createFavoriteGroupTools(group));
  if (group.categories?.length) {
    group.categories.forEach((category) => body.appendChild(createFavoriteCategoryNode(category, groupId)));
  } else {
    body.appendChild(createFavoriteEmptyNode());
  }

  details.append(summary, body);
  return details;
}

function renderFavoriteGroups() {
  const list = document.querySelector("[data-favorites-groups]");
  if (!list || !favoriteState) return;
  const currentGroupIds = new Set((favoriteState.groups || []).map((group) => group.id || ""));
  favoriteOpenGroupIds.forEach((groupId) => {
    if (!currentGroupIds.has(groupId)) favoriteOpenGroupIds.delete(groupId);
  });
  list.replaceChildren();
  favoriteState.groups.forEach((group) => list.appendChild(createFavoriteGroupNode(group)));
}

function renderFavorites() {
  if (!favoriteState) return;
  const dock = favoriteDock();
  if (dock) dock.dataset.favoritesActiveGroup = favoriteState.active_group_id || "";
  if (favoriteState.active_group_id && favoriteState.active_group_id !== favoriteLastActiveGroupId) {
    favoriteOpenGroupIds.add(favoriteState.active_group_id);
  }
  favoriteLastActiveGroupId = favoriteState.active_group_id || "";
  const title = document.querySelector("[data-favorites-active-title]");
  if (title) title.textContent = "Закладки";
  renderFavoriteGroups();
  updateFavoriteSortControls();
}

function favoriteDragAfterElement(container, y, selector) {
  const elements = [...container.querySelectorAll(selector)].filter((element) => element !== favoriteDragState?.element);
  return elements.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) return { offset, element: child };
    return closest;
  }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
}

function favoriteGroupOrder() {
  return [...document.querySelectorAll("[data-favorites-groups] > [data-favorite-group]")]
    .map((group) => group.dataset.favoriteGroup || "")
    .filter(Boolean);
}

function favoriteItemOrder(groupElement) {
  return [...groupElement.querySelectorAll("[data-favorite-sort-item]")]
    .map(favoriteSortItemPayload)
    .filter((item) => item.type && item.id);
}

async function saveFavoriteGroupOrder() {
  const groupIds = favoriteGroupOrder();
  if (!groupIds.length) return;
  await submitFavoriteJson("/favorites/groups/reorder", { group_ids: groupIds });
}

async function saveFavoriteItemOrder(groupElement) {
  const groupId = groupElement?.dataset.favoriteGroup || "";
  const items = favoriteItemOrder(groupElement);
  if (!groupId || !items.length) return;
  await submitFavoriteJson(`/favorites/groups/${encodeURIComponent(groupId)}/items/reorder`, { items });
}

function setFavoriteSortMode(enabled) {
  favoriteSortMode = enabled;
  if (enabled) favoriteItemSortGroupId = "";
  favoriteDragState = null;
  renderFavorites();
}

function setFavoriteItemSortGroup(groupId) {
  favoriteItemSortGroupId = favoriteItemSortGroupId === groupId ? "" : groupId;
  if (favoriteItemSortGroupId) {
    favoriteSortMode = false;
    favoriteOpenGroupIds.add(favoriteItemSortGroupId);
  }
  favoriteDragState = null;
  renderFavorites();
}

document.addEventListener("click", async (event) => {
  if (event.target.closest("[data-favorites-toggle]")) {
    event.preventDefault();
    toggleFavoritesPanel();
    return;
  }

  if (event.target.closest("[data-favorites-sort-toggle]")) {
    event.preventDefault();
    setFavoriteSortMode(!favoriteSortMode);
    return;
  }

  const itemSortToggle = event.target.closest("[data-favorites-items-sort-toggle]");
  if (itemSortToggle) {
    event.preventDefault();
    setFavoriteItemSortGroup(itemSortToggle.dataset.favoriteGroupId || "");
    return;
  }

  const favoriteToggle = event.target.closest("[data-favorite-toggle]");
  if (favoriteToggle) {
    event.preventDefault();
    event.stopPropagation();
    const item = favoriteButtonItem(favoriteToggle);
    if (!favoriteState) {
      await loadFavorites().catch(() => null);
    }
    if (!favoriteState) {
      showFavoriteToast("Не удалось открыть избранное");
      return;
    }
    if ((favoriteState.groups || []).length <= 1) {
      toggleFavoriteItem(item).catch(() => showFavoriteToast("Не удалось изменить избранное"));
    } else {
      openFavoritePicker(item);
    }
    return;
  }

  const groupSummary = event.target.closest("[data-favorite-group] > summary");
  if (groupSummary) {
    event.preventDefault();
    if (favoriteSortMode || favoriteItemSortGroupId) return;
    const group = groupSummary.closest("[data-favorite-group]");
    const groupId = group.dataset.favoriteGroup || "";
    const shouldOpen = !group.open;
    if (shouldOpen) {
      favoriteOpenGroupIds.add(groupId);
      submitFavoriteForm(`/favorites/groups/${encodeURIComponent(groupId)}/activate`)
        .catch(() => showFavoriteToast("Не удалось переключить группу"));
    } else {
      favoriteOpenGroupIds.delete(groupId);
      renderFavorites();
    }
    return;
  }

  const pickerGroup = event.target.closest("[data-favorite-picker-group]");
  if (pickerGroup && pendingFavoriteItem) {
    event.preventDefault();
    toggleFavoriteItem(pendingFavoriteItem, pickerGroup.dataset.favoritePickerGroup)
      .then(() => openFavoritePicker(pendingFavoriteItem))
      .catch(() => showFavoriteToast("Не удалось изменить группу"));
    return;
  }

  const removeButton = event.target.closest("[data-favorite-remove]");
  if (removeButton) {
    event.preventDefault();
    const item = favoriteButtonItem(removeButton);
    toggleFavoriteItem(item, removeButton.dataset.favoriteGroupId || "")
      .catch(() => showFavoriteToast("Не удалось убрать из избранного"));
    return;
  }

  if (event.target.closest("[data-close-favorite-picker]")) {
    event.preventDefault();
    closeFavoritePicker();
  }
});

document.addEventListener("dragstart", (event) => {
  if (!favoriteSortMode && !favoriteItemSortGroupId) return;
  const item = event.target.closest("[data-favorite-sort-item]");
  if (item && item.closest("[data-favorite-group]")?.dataset.favoriteGroup === favoriteItemSortGroupId) {
    event.stopPropagation();
    favoriteDragState = {
      kind: "item",
      element: item,
      group: item.closest("[data-favorite-group]"),
    };
    item.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", "favorite-item");
    return;
  }

  const group = event.target.closest("[data-favorite-group]");
  if (favoriteSortMode && group && event.target.closest("summary")) {
    event.stopPropagation();
    favoriteDragState = { kind: "group", element: group };
    group.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", "favorite-group");
  }
});

document.addEventListener("dragover", (event) => {
  if ((!favoriteSortMode && !favoriteItemSortGroupId) || !favoriteDragState) return;

  if (favoriteDragState.kind === "group") {
    const list = document.querySelector("[data-favorites-groups]");
    const overGroup = event.target.closest("[data-favorite-group]");
    if (!list || !overGroup || overGroup === favoriteDragState.element) return;
    event.preventDefault();
    const afterElement = favoriteDragAfterElement(list, event.clientY, "[data-favorite-group]");
    if (afterElement == null) list.appendChild(favoriteDragState.element);
    else list.insertBefore(favoriteDragState.element, afterElement);
    return;
  }

  if (favoriteDragState.kind === "item") {
    const overItem = event.target.closest("[data-favorite-sort-item]");
    const overGroup = event.target.closest("[data-favorite-group]");
    if (!overGroup || overGroup !== favoriteDragState.group || !overItem || overItem === favoriteDragState.element) return;
    const category = overItem.closest("[data-favorites-category]");
    if (!category || category !== favoriteDragState.element.closest("[data-favorites-category]")) return;
    event.preventDefault();
    const list = overItem.parentElement;
    const afterElement = favoriteDragAfterElement(list, event.clientY, "[data-favorite-sort-item]");
    if (afterElement == null) list.appendChild(favoriteDragState.element);
    else list.insertBefore(favoriteDragState.element, afterElement);
  }
});

document.addEventListener("drop", (event) => {
  if ((!favoriteSortMode && !favoriteItemSortGroupId) || !favoriteDragState) return;
  event.preventDefault();
  const state = favoriteDragState;
  if (state.kind === "group") {
    saveFavoriteGroupOrder()
      .then(() => showFavoriteToast("Порядок групп сохранён"))
      .catch(() => showFavoriteToast("Не удалось сохранить порядок групп"));
  } else if (state.kind === "item") {
    saveFavoriteItemOrder(state.group)
      .then(() => showFavoriteToast("Порядок элементов сохранён"))
      .catch(() => showFavoriteToast("Не удалось сохранить порядок элементов"));
  }
});

document.addEventListener("dragend", () => {
  if (favoriteDragState?.element) favoriteDragState.element.classList.remove("is-dragging");
  favoriteDragState = null;
});

document.addEventListener("submit", (event) => {
  const createForm = event.target.closest("[data-favorite-create-group-form]");
  if (createForm) {
    event.preventDefault();
    const submitButton = createForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    submitFavoriteForm(createForm.action, new FormData(createForm))
      .then(() => {
        createForm.reset();
        showFavoriteToast("Группа создана");
      })
      .catch(() => showFavoriteToast("Не удалось создать группу"))
      .finally(() => {
        if (submitButton) submitButton.disabled = false;
      });
    return;
  }

  const renameForm = event.target.closest("[data-favorite-rename-group-form]");
  if (renameForm) {
    event.preventDefault();
    submitFavoriteForm(renameForm.action, new FormData(renameForm))
      .then(() => showFavoriteToast("Группа переименована"))
      .catch(() => showFavoriteToast("Не удалось переименовать группу"));
    return;
  }

  const deleteForm = event.target.closest("[data-favorite-delete-group-form]");
  if (deleteForm) {
    event.preventDefault();
    submitFavoriteForm(deleteForm.action, new FormData(deleteForm))
      .then(() => showFavoriteToast("Группа удалена"))
      .catch(() => showFavoriteToast("Последнюю группу нельзя удалить"));
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeFavoritePicker();
    if (favoriteDock()?.classList.contains("is-open")) toggleFavoritesPanel(false);
  }
});
