const demoPlaceholder = document.querySelector("[data-demo-placeholder]");
const demoContent = document.querySelector("[data-demo-content]");
const demoTitle = document.querySelector("[data-demo-title]");
const demoSubtitle = document.querySelector("[data-demo-subtitle]");
const demoMeta = document.querySelector("[data-demo-meta]");
const demoBody = document.querySelector("[data-demo-body]");
const demoStateStorageKey = "ogma-demo-state";
let demoUpdatedAt = "";
let imageView = {
  scale: 1,
  x: 0,
  y: 0,
  isDragging: false,
  pointerId: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
};

function escapeDemoHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTags(tags = []) {
  return tags.map((tag) => `<span>${escapeDemoHtml(tag)}</span>`).join("");
}

function demoImage() {
  return demoBody.querySelector("[data-demo-pan-image]");
}

function applyImageView() {
  const image = demoImage();
  if (!image) return;
  image.style.transform = `translate(${imageView.x}px, ${imageView.y}px) scale(${imageView.scale})`;
}

function resetImageView() {
  imageView = {
    scale: 1,
    x: 0,
    y: 0,
    isDragging: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
  };
  applyImageView();
}

function imageMarkup(content) {
  return `<img class="demo-main-image" data-demo-pan-image src="${escapeDemoHtml(content.image_url)}" alt="${escapeDemoHtml(content.title)}">`;
}

function renderDemoContent(content) {
  if (!content) {
    demoPlaceholder.hidden = false;
    demoContent.hidden = true;
    return;
  }

  demoPlaceholder.hidden = true;
  demoContent.hidden = false;
  demoContent.dataset.demoLayout = content.layout || "text";
  const isImageOnly = content.layout === "image" || content.layout === "character";
  demoContent.classList.toggle("is-image-only", isImageOnly);
  demoTitle.textContent = content.title || "Материал";
  demoSubtitle.textContent = content.subtitle || "";

  const metaParts = [];
  if (content.source) metaParts.push(`<span>${escapeDemoHtml(content.source)}</span>`);
  if (content.page) metaParts.push(`<span>стр. ${escapeDemoHtml(content.page)}</span>`);
  if (Array.isArray(content.tags) && content.tags.length) metaParts.push(renderTags(content.tags));
  demoMeta.innerHTML = metaParts.join("");

  if (content.layout === "image") {
    demoBody.innerHTML = imageMarkup(content);
    resetImageView();
    return;
  }

  if (content.layout === "character") {
    demoBody.innerHTML = imageMarkup(content);
    resetImageView();
    return;
  }

  demoBody.innerHTML = `<article class="rule-content demo-rule-content">${content.content_html || "<p>Текста пока нет.</p>"}</article>`;
}

async function refreshDemoState() {
  const response = await fetch("/demo/state", { headers: { "Accept": "application/json" } });
  if (!response.ok) return;
  const state = await response.json();
  if (state.enabled === false) return;
  if (state.updated_at === demoUpdatedAt) return;
  demoUpdatedAt = state.updated_at || "";
  renderDemoContent(state.content);
}

function receiveDemoState(state) {
  if (!state || state.updated_at === demoUpdatedAt) return;
  demoUpdatedAt = state.updated_at || "";
  renderDemoContent(state.content);
}

window.addEventListener("storage", (event) => {
  if (event.key === demoStateStorageKey) refreshDemoState();
});

demoBody.addEventListener("wheel", (event) => {
  const image = demoImage();
  if (!image || !demoContent.classList.contains("is-image-only")) return;
  event.preventDefault();

  const rect = demoBody.getBoundingClientRect();
  const pointX = event.clientX - rect.left - rect.width / 2;
  const pointY = event.clientY - rect.top - rect.height / 2;
  const previousScale = imageView.scale;
  const zoomFactor = event.deltaY < 0 ? 1.12 : 0.89;
  const nextScale = Math.min(5, Math.max(0.35, previousScale * zoomFactor));
  if (nextScale === previousScale) return;

  const ratio = nextScale / previousScale;
  imageView.x = pointX - (pointX - imageView.x) * ratio;
  imageView.y = pointY - (pointY - imageView.y) * ratio;
  imageView.scale = nextScale;
  applyImageView();
}, { passive: false });

demoBody.addEventListener("pointerdown", (event) => {
  const image = demoImage();
  if (!image || !demoContent.classList.contains("is-image-only")) return;
  imageView.isDragging = true;
  imageView.pointerId = event.pointerId;
  imageView.startX = event.clientX;
  imageView.startY = event.clientY;
  imageView.originX = imageView.x;
  imageView.originY = imageView.y;
  demoBody.classList.add("is-panning");
  demoBody.setPointerCapture?.(event.pointerId);
});

demoBody.addEventListener("pointermove", (event) => {
  if (!imageView.isDragging || event.pointerId !== imageView.pointerId) return;
  imageView.x = imageView.originX + event.clientX - imageView.startX;
  imageView.y = imageView.originY + event.clientY - imageView.startY;
  applyImageView();
});

function stopImagePan(event) {
  if (event?.pointerId && imageView.pointerId !== event.pointerId) return;
  imageView.isDragging = false;
  imageView.pointerId = null;
  demoBody.classList.remove("is-panning");
}

demoBody.addEventListener("pointerup", stopImagePan);
demoBody.addEventListener("pointercancel", stopImagePan);
demoBody.addEventListener("dblclick", () => {
  if (demoContent.classList.contains("is-image-only")) resetImageView();
});

refreshDemoState();
