const settingsPage = document.querySelector("[data-settings-page]");
const settingsFeedback = document.querySelector("[data-settings-feedback]");
const settingsToast = document.querySelector("[data-settings-toast]");
const foundryDataInput = document.querySelector("[data-foundry-data-dir]");
const foundryDataCapabilityInput = document.querySelector("[data-foundry-data-capability]");
const foundryAssetsInput = document.querySelector("[data-foundry-assets-dir]");
const foundrySyncForm = document.querySelector("[data-foundry-sync-form]");
const foundryEnabledInput = document.querySelector("input[name='foundry_enabled']");
const settingsSections = [...document.querySelectorAll(".settings-category[id]")];
const settingsNavLinks = [...document.querySelectorAll(".settings-nav-list a[href^='#']")];
const settingsLayout = document.querySelector(".settings-layout");
const updatePanel = document.querySelector("[data-update-panel]");

settingsSections.forEach((section) => {
  section.open = true;
  section.querySelector("summary")?.addEventListener("click", (event) => {
    event.preventDefault();
    section.open = true;
  });
});

function updateSettingsNavigation(activeId, updateHash) {
  settingsNavLinks.forEach((link) => {
    const isActive = link.getAttribute("href") === `#${activeId}`;
    link.classList.toggle("is-active", isActive);
    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  if (updateHash && window.location.hash !== `#${activeId}`) {
    history.replaceState(null, "", `#${activeId}`);
  }
}

function settingsScrollTarget() {
  if (!settingsLayout) return 0;
  return Math.max(0, Math.round(settingsLayout.getBoundingClientRect().top + window.scrollY - 16));
}

function shouldLiftSettingsView() {
  return window.scrollY > settingsScrollTarget() + 28;
}

function setActiveSettingsSection(sectionId, { updateHash = false } = {}) {
  const fallbackId = settingsSections[0]?.id;
  const activeId = settingsSections.some((section) => section.id === sectionId) ? sectionId : fallbackId;
  if (!activeId) return;

  updateSettingsNavigation(activeId, updateHash);

  if (shouldLiftSettingsView()) {
    window.scrollTo(0, settingsScrollTarget());
  }

  const activeSection = settingsSections.find((section) => section.id === activeId);
  settingsSections.forEach((section) => {
    section.hidden = section !== activeSection;
    section.open = true;
  });

  updateSettingsNavigation(activeId, updateHash);
}

if (settingsSections.length && settingsNavLinks.length) {
  settingsNavLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setActiveSettingsSection(link.hash.slice(1), { updateHash: true });
    });
  });

  window.addEventListener("hashchange", () => {
    setActiveSettingsSection(window.location.hash.slice(1));
  });

  setActiveSettingsSection(window.location.hash.slice(1));
}

function showSettingsFeedback(message, state = "success") {
  const target = settingsToast || settingsFeedback;
  if (!target) return;
  target.hidden = false;
  target.textContent = message;
  target.classList.toggle("is-error", state === "error");
  target.classList.toggle("is-success", state !== "error");
  target.classList.add("is-visible");
  window.clearTimeout(target._hideTimer);
  target._hideTimer = window.setTimeout(() => target.classList.remove("is-visible"), 3600);
}

async function postForm(url, formData, { allowPayloadError = false } = {}) {
  const response = await fetch(url, {
    method: "POST",
    body: formData,
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || (!allowPayloadError && payload.ok === false)) {
    throw new Error(payload.error || `Не удалось выполнить запрос (${response.status}).`);
  }
  return payload;
}

function updateFoundryLinkCards(links = []) {
  const cards = [...document.querySelectorAll(".foundry-link-card")];
  links.forEach((link, index) => {
    const card = cards[index];
    if (!card) return;
    card.classList.remove("is-linked", "is-missing", "is-conflict", "is-error");
    card.classList.add(`is-${link.state}`);
    const message = card.querySelector("span");
    if (message) message.textContent = link.message;
  });
}

async function syncFoundryLinks({ automatic = false } = {}) {
  if (!foundrySyncForm) return;
  if (!automatic) showSettingsFeedback("Создаю и обновляю ссылки Foundry...");

  const payload = await window.startLocalJob(foundrySyncForm.action, {
    method: "POST",
    body: new FormData(foundrySyncForm),
    headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
  });
  updateFoundryLinkCards(payload.links || []);
  showSettingsFeedback(payload.summary?.message || "Обновление проведено.", payload.summary?.state || "success");
}

document.addEventListener("click", async (event) => {
  const pickerButton = event.target.closest("[data-pick-folder]");
  if (pickerButton) {
    const field = pickerButton.dataset.pickFolder;
    const formData = new FormData();
    formData.append("field", field);

    try {
      showSettingsFeedback("Открываю выбор папки...");
      const payload = await window.startLocalJob("/settings/foundry/pick-folder", {
        method: "POST",
        body: formData,
        headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      });
      if (payload.cancelled) {
        showSettingsFeedback("Выбор папки отменен.");
        return;
      }
      if (field === "assets_dir" && foundryAssetsInput) foundryAssetsInput.value = payload.value;
      if (field === "data_dir" && foundryDataInput && foundryDataCapabilityInput) {
        foundryDataInput.value = payload.display_name || "Foundry Data";
        foundryDataCapabilityInput.value = payload.capability_id || "";
      }
      showSettingsFeedback("Папка выбрана. Сохраните настройки, чтобы применить путь.");
    } catch (error) {
      showSettingsFeedback(error.message, "error");
    }
    return;
  }

  const openButton = event.target.closest("[data-open-settings-folder]");
  if (openButton) {
    const formData = new FormData();
    formData.append("folder", openButton.dataset.openSettingsFolder);
    window.startLocalJob("/folders/open", {
      method: "POST",
      body: formData,
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    }).catch(() => showSettingsFeedback("Не удалось открыть папку.", "error"));
    return;
  }
});

foundrySyncForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await syncFoundryLinks();
  } catch (error) {
    showSettingsFeedback(error.message, "error");
  }
});

if (settingsPage && foundrySyncForm) {
  window.setInterval(() => {
    if (document.visibilityState === "visible" && foundryEnabledInput?.checked) {
      syncFoundryLinks({ automatic: true }).catch(() => {});
    }
  }, 5 * 60 * 1000);
}

function formatUpdateSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "";
  return `${(value / 1024 / 1024).toFixed(1).replace(".", ",")} МБ`;
}

function renderUpdateStatus(payload = {}) {
  if (!updatePanel) return;
  const current = payload.current_version || updatePanel.dataset.currentVersion || "—";
  const latest = payload.latest_version || "—";
  const available = payload.available === true;
  const downloaded = payload.downloaded === true;
  const packaged = payload.packaged === true || updatePanel.dataset.packaged === "true";
  const currentNode = updatePanel.querySelector("[data-update-current]");
  const latestNode = updatePanel.querySelector("[data-update-latest]");
  const titleNode = updatePanel.querySelector("[data-update-title]");
  const messageNode = updatePanel.querySelector("[data-update-message]");
  const summaryNode = document.querySelector("[data-update-summary]");
  const downloadButton = updatePanel.querySelector("[data-update-download]");
  const installButton = updatePanel.querySelector("[data-update-install]");
  const releaseLink = updatePanel.querySelector("[data-update-release]");

  if (currentNode) currentNode.textContent = current;
  if (latestNode) latestNode.textContent = latest;
  if (summaryNode) summaryNode.textContent = available ? `Доступна ${latest}` : `v${current}`;
  if (titleNode) {
    titleNode.textContent = available
      ? `Доступна Oghma ${latest}`
      : `Установлена актуальная Oghma ${current}`;
  }
  if (messageNode) {
    if (downloaded && available) {
      messageNode.textContent = packaged
        ? "Обновление загружено и проверено. Можно открыть мастер установки."
        : "Обновление загружено и проверено. Установщик сохранён в служебной папке.";
    } else if (available) {
      const size = formatUpdateSize(payload.installer_size);
      messageNode.textContent = `Релиз готов к загрузке${size ? ` · ${size}` : ""}. Ваши данные останутся на месте.`;
    } else {
      messageNode.textContent = "Новых опубликованных версий нет.";
    }
  }
  if (downloadButton) downloadButton.hidden = !available || downloaded;
  if (installButton) installButton.hidden = !available || !downloaded || !packaged;
  if (releaseLink) {
    const releaseUrl = String(payload.release_url || "");
    releaseLink.hidden = !releaseUrl;
    if (releaseUrl) releaseLink.href = releaseUrl;
  }
}

async function runUpdateAction(kind) {
  if (!updatePanel) return;
  const url = updatePanel.dataset[`${kind}Url`];
  if (!url) return;
  const buttons = [...updatePanel.querySelectorAll("button")];
  buttons.forEach((button) => { button.disabled = true; });
  const messages = {
    check: "Проверяю GitHub Releases...",
    download: "Загружаю установщик и проверяю SHA-256...",
    install: "Подготавливаю мастер обновления...",
  };
  showSettingsFeedback(messages[kind] || "Выполняю операцию...");
  try {
    const payload = await window.startLocalJob(url, {
      method: "POST",
      body: new FormData(),
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
    });
    if (kind === "install") {
      showSettingsFeedback(payload.message || "Oghma закрывается. Сейчас откроется мастер обновления.");
      return;
    }
    renderUpdateStatus(payload);
    showSettingsFeedback(
      payload.available
        ? (payload.downloaded ? "Обновление загружено и проверено." : `Доступна Oghma ${payload.latest_version}.`)
        : "Установлена актуальная версия Oghma.",
    );
  } catch (error) {
    showSettingsFeedback(error.message, "error");
  } finally {
    if (kind !== "install") buttons.forEach((button) => { button.disabled = false; });
  }
}

updatePanel?.querySelector("[data-update-check]")?.addEventListener("click", () => runUpdateAction("check"));
updatePanel?.querySelector("[data-update-download]")?.addEventListener("click", () => runUpdateAction("download"));
updatePanel?.querySelector("[data-update-install]")?.addEventListener("click", () => {
  if (window.confirm("Oghma будет закрыта, затем откроется мастер обновления. Продолжить?")) {
    runUpdateAction("install");
  }
});
