let activeMarkdownField = null;
let markdownToastTimer = null;
let ruleSideAbortController = null;

function rememberMarkdownField(field) {
  if (field?.matches?.("textarea")) {
    activeMarkdownField = field;
  }
}

function fieldForHelpButton(button) {
  const label = button.closest("label");
  const scopedField = label?.querySelector("textarea");
  if (scopedField) return scopedField;

  const title = button.closest(".markdown-field-title");
  const nextField = title?.nextElementSibling;
  if (nextField?.matches?.("textarea")) return nextField;

  const form = button.closest("form");
  const formField = form?.querySelector("textarea");
  if (formField) return formField;

  return document.activeElement;
}

function markdownHelpModal() {
  return document.querySelector("[data-markdown-help-modal]");
}

function ruleSideModal() {
  return document.querySelector("[data-rule-side-modal]");
}

function showMarkdownHelp() {
  closeRuleSidePanel({ restoreFocus: false });
  const modal = markdownHelpModal();
  if (!modal) return;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");
}

function closeRuleSidePanel({ restoreFocus = false } = {}) {
  const modal = ruleSideModal();
  if (!modal) return;
  ruleSideAbortController?.abort();
  ruleSideAbortController = null;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (
    !document.querySelector(".map-modal.is-open, .rule-modal.is-open, .spotlight.is-open")
    && !document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open")
    && !markdownHelpModal()?.classList.contains("is-open")
  ) {
    document.body.classList.remove("has-modal");
  }
  if (restoreFocus) window.setTimeout(() => activeMarkdownField?.focus(), 20);
}

function normalizeRuleSideContent(content, ruleTitle = "") {
  if (!content) return;
  const firstHeading = content.querySelector(":scope > h1:first-child, :scope > h2:first-child");
  firstHeading?.remove();
}

async function openRuleSidePanel(ruleId) {
  if (!ruleId) return;
  closeMarkdownHelp({ restoreFocus: false });
  const modal = ruleSideModal();
  if (!modal) return;

  const kicker = modal.querySelector("[data-rule-side-kicker]");
  const title = modal.querySelector("[data-rule-side-title]");
  const meta = modal.querySelector("[data-rule-side-meta]");
  const content = modal.querySelector("[data-rule-side-content]");

  if (kicker) kicker.textContent = "Правило";
  if (title) title.textContent = "Загружаю...";
  if (meta) meta.innerHTML = "";
  if (content) content.innerHTML = "<p>Загружаю правило...</p>";

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("has-modal");

  ruleSideAbortController?.abort();
  ruleSideAbortController = new AbortController();
  try {
    const response = await fetch(`/rules/${encodeURIComponent(ruleId)}/preview`, {
      headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      signal: ruleSideAbortController.signal,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "rule_not_found");
    const rule = payload.rule || {};
    if (kicker) kicker.textContent = rule.tag || "Правило";
    if (title) title.textContent = rule.title || "Правило";
    if (meta) {
      meta.innerHTML = [
        rule.source ? `<span class="rule-source-badge">${escapeMarkdownHtml(rule.source)}</span>` : "",
        rule.page ? `<span>стр. ${escapeMarkdownHtml(rule.page)}</span>` : "",
        rule.book_url ? `<a href="${escapeMarkdownHtml(rule.book_url)}" target="_blank" rel="noopener noreferrer">Открыть оригинал</a>` : "",
      ].filter(Boolean).join("");
    }
    if (content) {
      content.innerHTML = rule.content_html || "<p>Текста пока нет.</p>";
      normalizeRuleSideContent(content, rule.title || "");
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    if (title) title.textContent = "Правило не найдено";
    if (content) content.innerHTML = "<p>Не удалось открыть правило из глоссария.</p>";
  }
}

function escapeMarkdownHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toggleMarkdownHelp() {
  const modal = markdownHelpModal();
  if (!modal) return;
  if (modal.classList.contains("is-open")) {
    closeMarkdownHelp();
  } else {
    showMarkdownHelp();
  }
}

function closeMarkdownHelp({ restoreFocus = true } = {}) {
  const modal = markdownHelpModal();
  if (!modal) return;
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  if (
    !document.querySelector(".map-modal.is-open, .rule-modal.is-open, .spotlight.is-open")
    && !document.querySelector(".note-view-modal.is-open, .note-edit-modal.is-open")
  ) {
    document.body.classList.remove("has-modal");
  }
  if (restoreFocus) {
    window.setTimeout(() => activeMarkdownField?.focus(), 20);
  }
}

function showMarkdownToast(message) {
  let toast = document.querySelector("[data-markdown-help-toast]");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "copy-toast markdown-help-toast";
    toast.dataset.markdownHelpToast = "";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(markdownToastTimer);
  markdownToastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 1500);
}

async function copyMarkdownSnippet(snippet) {
  try {
    await navigator.clipboard.writeText(snippet);
  } catch {
    const fallback = document.createElement("textarea");
    fallback.value = snippet;
    document.body.appendChild(fallback);
    fallback.select();
    document.execCommand("copy");
    fallback.remove();
  }
  showMarkdownToast("Шаблон скопирован");
}

function insertMarkdownSnippet(snippet) {
  const field = activeMarkdownField;
  if (!field) {
    copyMarkdownSnippet(snippet);
    return;
  }

  const start = field.selectionStart ?? field.value.length;
  const end = field.selectionEnd ?? field.value.length;
  const before = field.value.slice(0, start);
  const after = field.value.slice(end);
  const needsLeadingSpace = before && !/[\s\n]$/.test(before);
  const needsTrailingSpace = after && !/^[\s\n]/.test(after);
  const insertion = `${needsLeadingSpace ? " " : ""}${snippet}${needsTrailingSpace ? " " : ""}`;
  field.value = `${before}${insertion}${after}`;
  const cursor = before.length + insertion.length;
  field.focus();
  field.setSelectionRange(cursor, cursor);
  field.dispatchEvent(new Event("input", { bubbles: true }));
  showMarkdownToast("Шаблон вставлен");
}

function wrapMarkdownSelection(field, before, after = before, placeholder = "текст") {
  rememberMarkdownField(field);
  const start = field.selectionStart ?? field.value.length;
  const end = field.selectionEnd ?? field.value.length;
  const selected = field.value.slice(start, end);
  const text = selected || placeholder;
  const wrapped = `${before}${text}${after}`;
  field.setRangeText(wrapped, start, end, "preserve");
  const selectionStart = start + before.length;
  const selectionEnd = selectionStart + text.length;
  field.focus();
  field.setSelectionRange(selectionStart, selectionEnd);
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function prefixMarkdownLines(field, prefix, placeholder = "текст") {
  rememberMarkdownField(field);
  const start = field.selectionStart ?? field.value.length;
  const end = field.selectionEnd ?? field.value.length;
  const selected = field.value.slice(start, end) || placeholder;
  const lines = selected.split("\n");
  const prefixed = lines.map((line) => `${prefix}${line || placeholder}`).join("\n");
  field.setRangeText(prefixed, start, end, "preserve");
  field.focus();
  field.setSelectionRange(start, start + prefixed.length);
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function applyMarkdownShortcut(event) {
  const field = event.target;
  if (!field?.matches?.("textarea")) return false;
  const key = event.key.toLocaleLowerCase("ru-RU");
  if (!event.ctrlKey && !event.metaKey) return false;

  if (!event.altKey && (key === "b" || key === "и")) {
    event.preventDefault();
    wrapMarkdownSelection(field, "**", "**", "жирный текст");
    showMarkdownToast("Жирный текст");
    return true;
  }
  if (!event.altKey && (key === "i" || key === "ш")) {
    event.preventDefault();
    wrapMarkdownSelection(field, "*", "*", "курсив");
    showMarkdownToast("Курсив");
    return true;
  }
  if (!event.altKey && (key === "u" || key === "г")) {
    event.preventDefault();
    wrapMarkdownSelection(field, "_", "_", "подчёркнутый текст");
    showMarkdownToast("Подчёркивание");
    return true;
  }
  if (event.altKey && (key === "h" || key === "р")) {
    event.preventDefault();
    prefixMarkdownLines(field, "## ", "Заголовок");
    showMarkdownToast("Заголовок");
    return true;
  }
  if (event.altKey && (key === "l" || key === "д")) {
    event.preventDefault();
    prefixMarkdownLines(field, "- ", "пункт списка");
    showMarkdownToast("Список");
    return true;
  }
  if (event.altKey && (key === "q" || key === "й")) {
    event.preventDefault();
    prefixMarkdownLines(field, "> ", "цитата");
    showMarkdownToast("Цитата");
    return true;
  }
  if (!event.altKey && (key === "`" || key === "ё")) {
    event.preventDefault();
    wrapMarkdownSelection(field, "`", "`", "термин");
    showMarkdownToast("Код/термин");
    return true;
  }
  if (!event.altKey && (key === "k" || key === "л")) {
    event.preventDefault();
    wrapMarkdownSelection(field, "[", "](https://example.com)", "текст ссылки");
    showMarkdownToast("Ссылка");
    return true;
  }
  return false;
}

function applyMarkdownHelpFilter(filter, modal = markdownHelpModal()) {
  const activeFilter = filter || "all";
  modal?.querySelectorAll("[data-markdown-help-filter]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.markdownHelpFilter === activeFilter);
  });
  modal?.querySelectorAll("[data-markdown-help-category]").forEach((card) => {
    card.hidden = activeFilter !== "all" && card.dataset.markdownHelpCategory !== activeFilter;
  });
}

function scrollMarkdownTabs(button, direction) {
  const tabs = button.closest(".markdown-help-tabs-shell")?.querySelector("[data-markdown-help-tabs]");
  if (!tabs) return;
  const distance = Math.max(160, Math.floor(tabs.clientWidth * 0.72));
  tabs.scrollBy({ left: distance * direction, behavior: "smooth" });
}

document.addEventListener("focusin", (event) => {
  rememberMarkdownField(event.target);
});

document.addEventListener("click", (event) => {
  const inlineRuleLink = event.target.closest("a.rule-inline-link[data-open-rule-modal]");
  if (inlineRuleLink) {
    event.preventDefault();
    event.stopImmediatePropagation();
    openRuleSidePanel(inlineRuleLink.dataset.openRuleModal);
    return;
  }

  if (event.target.closest("[data-close-rule-side]")) {
    event.preventDefault();
    closeRuleSidePanel({ restoreFocus: true });
    return;
  }

  const helpButton = event.target.closest("[data-open-markdown-help]");
  if (helpButton) {
    event.preventDefault();
    rememberMarkdownField(fieldForHelpButton(helpButton));
    toggleMarkdownHelp();
    return;
  }

  if (event.target.closest("[data-close-markdown-help]")) {
    event.preventDefault();
    closeMarkdownHelp();
    return;
  }

  const copyButton = event.target.closest("[data-copy-markdown-snippet]");
  if (copyButton) {
    event.preventDefault();
    copyMarkdownSnippet(copyButton.dataset.copyMarkdownSnippet || "");
    return;
  }

  const insertButton = event.target.closest("[data-insert-markdown-snippet]");
  if (insertButton) {
    event.preventDefault();
    insertMarkdownSnippet(insertButton.dataset.insertMarkdownSnippet || "");
    return;
  }

  const filterButton = event.target.closest("[data-markdown-help-filter]");
  if (filterButton) {
    event.preventDefault();
    applyMarkdownHelpFilter(filterButton.dataset.markdownHelpFilter || "all", filterButton.closest("[data-markdown-help-modal]"));
    filterButton.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
    return;
  }

  const tabsPrev = event.target.closest("[data-markdown-help-tabs-prev]");
  if (tabsPrev) {
    event.preventDefault();
    scrollMarkdownTabs(tabsPrev, -1);
    return;
  }

  const tabsNext = event.target.closest("[data-markdown-help-tabs-next]");
  if (tabsNext) {
    event.preventDefault();
    scrollMarkdownTabs(tabsNext, 1);
  }
});

document.addEventListener("keydown", (event) => {
  if (applyMarkdownShortcut(event)) return;
  if (event.key === "Escape" && ruleSideModal()?.classList.contains("is-open")) {
    closeRuleSidePanel({ restoreFocus: true });
    return;
  }
  if (event.key === "Escape" && markdownHelpModal()?.classList.contains("is-open")) {
    closeMarkdownHelp();
  }
});

applyMarkdownHelpFilter("all");
