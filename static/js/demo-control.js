const demoOpenButton = document.querySelector("[data-demo-open]");
const demoClearButton = document.querySelector("[data-demo-clear]");
let demoToastTimer = null;
const demoStateStorageKey = "ogma-demo-state";

function showDemoToast(message) {
  let toast = document.querySelector("[data-demo-toast]");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "copy-toast demo-toast";
    toast.dataset.demoToast = "";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(demoToastTimer);
  demoToastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1500);
}

function setDemoClearVisible(isVisible) {
  if (!demoClearButton) return;
  demoClearButton.hidden = !isVisible;
  demoClearButton.classList.toggle("is-visible", isVisible);
}

async function syncDemoClearState() {
  if (!demoClearButton) return;
  try {
    const response = await fetch("/demo/state", { headers: { "Accept": "application/json" } });
    const state = await response.json();
    setDemoClearVisible(Boolean(state.content));
  } catch {
    setDemoClearVisible(false);
  }
}

function broadcastDemoState() {
  try {
    localStorage.setItem(demoStateStorageKey, String(Date.now()));
  } catch {
    // The server state is saved already; this only wakes open demo windows.
  }
}

async function showDemoItem(button) {
  const response = await fetch("/demo/show", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/json" },
    body: JSON.stringify({
      kind: button.dataset.demoKind,
      id: button.dataset.demoId,
      scope: button.dataset.demoScope || "shared",
      campaign_slug: button.dataset.demoCampaign || "",
    }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "demo_error");
  }
  broadcastDemoState();
  setDemoClearVisible(true);
}

demoOpenButton?.addEventListener("click", () => {
  window.open("/demo", "ogma-demo", "popup=yes,width=1280,height=720");
});

demoClearButton?.addEventListener("click", async () => {
  try {
    const response = await fetch("/demo/clear", { method: "POST", headers: { "Accept": "application/json" } });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error("clear_failed");
    broadcastDemoState();
    setDemoClearVisible(false);
    showDemoToast("Демонстрация очищена");
  } catch {
    showDemoToast("Не удалось очистить демонстрацию");
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-demo-show]");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
  try {
    await showDemoItem(button);
    showDemoToast("Материал отправлен на экран");
  } catch {
    showDemoToast("Не удалось отправить материал");
  }
});

document.addEventListener("keydown", (event) => {
  const button = event.target.closest("[data-demo-show]");
  if (!button || (event.key !== "Enter" && event.key !== " ")) return;
  event.preventDefault();
  button.click();
});

syncDemoClearState();
