let activeHoldDelete = null;

function lockHoldDeleteButtonSize(button) {
  if (!button || button.dataset.holdSizeLocked === "true") return;
  const rect = button.getBoundingClientRect();
  button.dataset.holdSizeLocked = "true";
  button.style.setProperty("--hold-locked-width", `${rect.width}px`);
  button.style.setProperty("--hold-locked-height", `${rect.height}px`);
  button.style.width = `${rect.width}px`;
  button.style.minWidth = `${rect.width}px`;
  button.style.height = `${rect.height}px`;
  button.style.minHeight = `${rect.height}px`;
}

function releaseHoldDeleteButtonSize(button) {
  if (!button || button.dataset.holdSizeLocked !== "true") return;
  delete button.dataset.holdSizeLocked;
  button.style.removeProperty("--hold-locked-width");
  button.style.removeProperty("--hold-locked-height");
  button.style.removeProperty("width");
  button.style.removeProperty("min-width");
  button.style.removeProperty("height");
  button.style.removeProperty("min-height");
}

function resetHoldDeleteButton(button) {
  if (!button) return;
  button.classList.remove("is-holding");
  button.style.setProperty("--hold-progress", "0");
  const label = button.querySelector("[data-hold-delete-label]");
  if (label && !button.matches("[data-hold-static-icon]")) {
    label.textContent = button.dataset.holdLabel || "Удерживайте, чтобы удалить";
  }
  releaseHoldDeleteButtonSize(button);
}

function cancelHoldDelete() {
  if (!activeHoldDelete) return;
  window.clearTimeout(activeHoldDelete.timeout);
  window.cancelAnimationFrame(activeHoldDelete.frame);
  resetHoldDeleteButton(activeHoldDelete.button);
  activeHoldDelete = null;
}

function submitHeldDelete(button) {
  const form = button.form || button.closest("form");
  if (!form) return;
  const event = new CustomEvent("hold-delete:submit", {
    bubbles: true,
    cancelable: true,
    detail: { button, form },
  });
  if (!button.dispatchEvent(event)) return;
  if (form.requestSubmit) form.requestSubmit();
  else form.submit();
}

function updateLocalOrderNumbers(list) {
  list?.querySelectorAll("[data-rule-order-number]").forEach((number, index) => {
    number.textContent = String(index + 1);
  });
}

function sortOrderModalAlphabetically(button) {
  const modal = button.closest(".map-modal");
  const list = modal?.querySelector(".rule-order-list");
  if (!list) return;
  [...list.children]
    .sort((left, right) => {
      const leftText = left.querySelector("strong")?.textContent || "";
      const rightText = right.querySelector("strong")?.textContent || "";
      return leftText.localeCompare(rightText, "ru", { sensitivity: "base" });
    })
    .forEach((item) => list.appendChild(item));
  updateLocalOrderNumbers(list);
}

function addAlphabeticOrderButtons() {
  document.querySelectorAll(".rule-tag-order-modal .upload-modal-actions, .rule-source-order-modal .upload-modal-actions").forEach((actions) => {
    if (actions.querySelector("[data-sort-order-alphabetically]")) return;
    const modal = actions.closest(".map-modal");
    if (!modal?.querySelector(".rule-order-list")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "order-alpha-button";
    button.dataset.sortOrderAlphabetically = "";
    button.textContent = "По алфавиту";
    actions.insertBefore(button, actions.lastElementChild);
  });
}

function startHoldDelete(button) {
  if (button.disabled) return;
  cancelHoldDelete();
  const duration = Number(button.dataset.holdDuration || 1900);
  const startedAt = performance.now();
  const label = button.querySelector("[data-hold-delete-label]");
  button.dataset.holdLabel = label?.textContent || button.dataset.holdLabel || "Удерживайте, чтобы удалить";
  lockHoldDeleteButtonSize(button);
  button.classList.add("is-holding");
  if (label && !button.matches("[data-hold-static-icon]")) label.textContent = "Держите...";

  const tick = (now) => {
    if (!activeHoldDelete || activeHoldDelete.button !== button) return;
    const progress = Math.min((now - startedAt) / duration, 1);
    button.style.setProperty("--hold-progress", String(progress));
    if (progress < 1) activeHoldDelete.frame = window.requestAnimationFrame(tick);
  };

  activeHoldDelete = {
    button,
    frame: window.requestAnimationFrame(tick),
    timeout: window.setTimeout(() => {
      activeHoldDelete = null;
      button.classList.remove("is-holding");
      button.style.setProperty("--hold-progress", "1");
      if (label && !button.matches("[data-hold-static-icon]")) label.textContent = "Удаляю...";
      submitHeldDelete(button);
    }, duration),
  };
}

document.addEventListener("pointerdown", (event) => {
  const button = event.target.closest("[data-hold-submit]");
  if (!button) return;
  event.preventDefault();
  button.setPointerCapture?.(event.pointerId);
  startHoldDelete(button);
});

document.addEventListener("click", (event) => {
  const alphabeticOrderButton = event.target.closest("[data-sort-order-alphabetically]");
  if (alphabeticOrderButton) {
    event.preventDefault();
    sortOrderModalAlphabetically(alphabeticOrderButton);
    return;
  }

  const button = event.target.closest("[data-hold-submit]");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
}, true);

document.addEventListener("DOMContentLoaded", addAlphabeticOrderButtons);

new MutationObserver(addAlphabeticOrderButtons).observe(document.documentElement, {
  childList: true,
  subtree: true,
});

["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
  document.addEventListener(eventName, (event) => {
    const button = event.target.closest?.("[data-hold-submit]");
    if (!button || activeHoldDelete?.button !== button) return;
    cancelHoldDelete();
  });
});
