const diceTray = document.querySelector("[data-dice-tray]");
const dicePanel = document.querySelector("[data-dice-panel]");
const diceExpression = document.querySelector("[data-dice-expression]");
const diceResult = document.querySelector("[data-dice-result]");
const diceHistory = document.querySelector("[data-dice-history]");

const diceState = {
  die: 20,
  advantage: "none",
};

const historyKey = "ogma-dice-history";

function randomDie(sides) {
  return Math.floor(Math.random() * sides) + 1;
}

function splitExpression(expression) {
  const compact = expression.replace(/\s+/g, "").toLowerCase();
  if (!compact) throw new Error("Введите формулу.");

  const parts = compact.match(/[+-]?[^+-]+/g) || [];
  if (parts.join("") !== compact) throw new Error("Не понял формулу.");
  return parts;
}

function parsePart(part) {
  const sign = part.startsWith("-") ? -1 : 1;
  const clean = part.replace(/^[+-]/, "");
  const diceMatch = clean.match(/^(\d*)d(\d+)$/);

  if (diceMatch) {
    return {
      type: "dice",
      sign,
      count: Math.max(1, Math.min(100, Number(diceMatch[1] || 1))),
      sides: Math.max(2, Math.min(1000, Number(diceMatch[2]))),
    };
  }

  if (/^\d+$/.test(clean)) {
    return { type: "number", sign, value: Number(clean) };
  }

  throw new Error("Не понял формулу.");
}

function parseExpression(expression) {
  return splitExpression(expression).map(parsePart);
}

function formatExpression(parts) {
  const diceParts = parts
    .filter((part) => part.type === "dice" && part.sign > 0 && part.count > 0)
    .sort((left, right) => left.sides - right.sides)
    .map((part) => `${part.count}d${part.sides}`);
  const numberParts = parts
    .filter((part) => part.type === "number" && part.value !== 0)
    .map((part) => `${part.sign > 0 ? "+" : "-"}${part.value}`);

  return [...diceParts, ...numberParts].join(" + ").replace(/\+ -/g, "- ") || "1d20";
}

function updateDiceButtons(parts) {
  const diceCounts = new Map();
  parts
    .filter((part) => part.type === "dice" && part.sign > 0)
    .forEach((part) => diceCounts.set(part.sides, part.count));

  document.querySelectorAll("[data-die]").forEach((button) => {
    const count = diceCounts.get(Number(button.dataset.die)) || 0;
    button.classList.toggle("is-active", count > 0);
    button.dataset.count = count ? String(count) : "";
  });
}

function partsFromCurrentExpression() {
  try {
    return parseExpression(diceExpression.value);
  } catch {
    return [];
  }
}

function changeDieCount(sides, delta) {
  const parts = partsFromCurrentExpression();
  let target = parts.find((part) => part.type === "dice" && part.sign > 0 && part.sides === sides);

  if (!target && delta > 0) {
    target = { type: "dice", sign: 1, count: 0, sides };
    parts.push(target);
  }

  if (!target) return;

  target.count = Math.max(0, Math.min(100, target.count + delta));
  const nextParts = parts.filter((part) => part.type !== "dice" || part.count > 0);
  diceExpression.value = formatExpression(nextParts);
  updateDiceButtons(nextParts);
}

function canUseAdvantage(parts) {
  const diceParts = parts.filter((part) => part.type === "dice");
  return diceParts.length === 1 && diceParts[0].sign === 1 && diceParts[0].count === 1 && diceParts[0].sides === 20;
}

function rollExpression(expression) {
  const parts = parseExpression(expression);
  const useAdvantage = diceState.advantage !== "none" && canUseAdvantage(parts);
  const details = [];
  let total = 0;

  parts.forEach((part) => {
    if (part.type === "number") {
      total += part.sign * part.value;
      details.push(`${part.sign < 0 ? "-" : "+"}${part.value}`);
      return;
    }

    if (useAdvantage && part.sides === 20) {
      const first = randomDie(20);
      const second = randomDie(20);
      const chosen = diceState.advantage === "adv" ? Math.max(first, second) : Math.min(first, second);
      total += chosen;
      details.push(`[${first}, ${second}] -> ${chosen}`);
      return;
    }

    const rolls = Array.from({ length: part.count }, () => randomDie(part.sides));
    const sum = rolls.reduce((accumulator, value) => accumulator + value, 0);
    total += part.sign * sum;
    details.push(`${part.sign < 0 ? "-" : ""}${part.count}d${part.sides}[${rolls.join(", ")}]`);
  });

  return {
    total,
    expression,
    label: useAdvantage ? (diceState.advantage === "adv" ? "Преимущество" : "Помеха") : "Обычный",
    details: details.join(" "),
  };
}

function readHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(historyKey) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.slice(0, 16).flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const total = Number(item.total);
      if (!Number.isFinite(total) || Math.abs(total) > 1_000_000_000) return [];
      return [{
        total,
        expression: String(item.expression || "").slice(0, 256),
        label: String(item.label || "").slice(0, 64),
        details: String(item.details || "").slice(0, 1024),
      }];
    });
  } catch {
    return [];
  }
}

function writeHistory(items) {
  localStorage.setItem(historyKey, JSON.stringify(items.slice(0, 16)));
}

function renderHistory() {
  if (!diceHistory) return;
  const items = readHistory();
  diceHistory.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "dice-history-empty";
    empty.textContent = "История пуста.";
    diceHistory.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("li");
    const summary = document.createElement("span");
    const total = document.createElement("strong");
    const expression = document.createElement("small");
    const details = document.createElement("em");
    total.textContent = String(item.total);
    expression.textContent = `${item.expression} · ${item.label}`;
    details.textContent = item.details;
    summary.append(total, expression);
    row.append(summary, details);
    diceHistory.appendChild(row);
  });
}

function showRoll(result) {
  const total = document.createElement("strong");
  const expression = document.createElement("span");
  const details = document.createElement("small");
  total.textContent = String(result.total);
  expression.textContent = `${result.expression} · ${result.label}`;
  details.textContent = result.details;
  diceResult.replaceChildren(total, expression, details);

  const history = readHistory();
  history.unshift({ ...result, createdAt: new Date().toISOString() });
  writeHistory(history);
  renderHistory();
}

function setDicePanel(isOpen) {
  diceTray?.classList.toggle("is-open", isOpen);
  dicePanel?.setAttribute("aria-hidden", String(!isOpen));
  document.querySelectorAll("[data-dice-toggle]").forEach((button) => {
    button.setAttribute("aria-expanded", String(isOpen));
  });
}

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-dice-toggle]")) {
    setDicePanel(!diceTray?.classList.contains("is-open"));
    return;
  }

  const dieButton = event.target.closest("[data-die]");
  if (dieButton) {
    changeDieCount(Number(dieButton.dataset.die), event.ctrlKey || event.metaKey ? -1 : 1);
    return;
  }

  const advantageButton = event.target.closest("[data-advantage]");
  if (advantageButton) {
    diceState.advantage = advantageButton.dataset.advantage;
    document.querySelectorAll("[data-advantage]").forEach((button) => {
      button.classList.toggle("is-active", button === advantageButton);
    });
    return;
  }

  if (event.target.closest("[data-roll-dice]")) {
    try {
      showRoll(rollExpression(diceExpression.value));
    } catch (error) {
      const message = document.createElement("span");
      message.textContent = String(error?.message || "Некорректное выражение.");
      diceResult.replaceChildren(message);
    }
    return;
  }

  if (event.target.closest("[data-clear-dice-history]")) {
    localStorage.removeItem(historyKey);
    renderHistory();
  }
});

diceExpression?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    try {
      showRoll(rollExpression(diceExpression.value));
    } catch (error) {
      const message = document.createElement("span");
      message.textContent = String(error?.message || "Некорректное выражение.");
      diceResult.replaceChildren(message);
    }
  }
});

diceExpression?.addEventListener("input", () => {
  updateDiceButtons(partsFromCurrentExpression());
});

updateDiceButtons(partsFromCurrentExpression());
renderHistory();
