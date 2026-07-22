(() => {
  const glyphIcons = new Map([
    ["×", "x"],
    ["⚙", "settings"],
    ["−", "minus"],
    ["+", "plus"],
    ["☆", "star"],
    ["★", "star-filled"],
    ["↕", "move-vertical"],
    ["✎", "pencil"],
    ["📁", "folder"],
    ["⛓", "link"],
    ["↗", "external-link"],
    ["✓", "check"],
    ["‹", "chevron-left"],
    ["›", "chevron-right"],
    ["i", "info"],
    ["?", "help-circle"],
    ["⌕", "search"],
    ["⌘", "command"],
    ["◐", "contrast"],
    ["▣", "monitor"],
    ["◷", "clock"],
    ["◇", "diamond"],
    ["⌂", "home"],
  ]);

  const inlineHostSelector = [
    "span[aria-hidden='true']",
    ".search-glyph",
    ".tag-drag-handle",
    ".favorites-drag-handle",
    ".favorites-group-arrow",
  ].join(",");

  function isEligibleHost(element) {
    if (!(element instanceof HTMLElement) || element.classList.contains("ui-icon")) return false;
    if (element.childElementCount > 0) return false;
    if (["BUTTON", "A", "SUMMARY"].includes(element.tagName)) return true;
    return element.matches(inlineHostSelector);
  }

  function enhanceElement(element) {
    if (!isEligibleHost(element)) return;
    const glyph = element.textContent.trim();
    const iconName = glyphIcons.get(glyph);
    if (!iconName) return;

    const icon = document.createElement("span");
    icon.className = `ui-icon ui-icon-${iconName}`;
    icon.setAttribute("aria-hidden", "true");
    element.replaceChildren(icon);
    element.classList.add("ui-icon-host");
    element.dataset.uiIcon = iconName;
    if (["BUTTON", "A", "SUMMARY"].includes(element.tagName)) {
      element.classList.add("ui-icon-only");
    }
  }

  function enhanceTree(root) {
    if (root instanceof HTMLElement) enhanceElement(root);
    if (!(root instanceof Element || root instanceof Document || root instanceof DocumentFragment)) return;
    root.querySelectorAll("button,a,summary,span[aria-hidden='true'],.search-glyph,.tag-drag-handle,.favorites-drag-handle,.favorites-group-arrow")
      .forEach(enhanceElement);
  }

  enhanceTree(document);

  const observer = new MutationObserver((records) => {
    for (const record of records) {
      enhanceTree(record.target);
      record.addedNodes.forEach(enhanceTree);
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.OghmaIcons = Object.freeze({ enhance: enhanceTree });
})();
