# Калькулятор боевых энкаунтеров и расчёт сложности

Инструкция для агента, который должен воспроизвести расчёт сложности боевых сцен в другом проекте.

## Цель

Нужно рассчитать бюджет опыта для текущей группы персонажей и показать мастеру варианты боевой сцены:

- бюджет для низкой, средней и высокой сложности;
- варианты одинаковых существ;
- варианты `лидер + миньоны`;
- варианты двух сильных существ;
- предупреждения о рисках сцены.

Расчёт основан на таблице XP на персонажа и таблице XP по показателю опасности существа.

## 1. Какие персонажи участвуют в расчёте

Если в проекте есть чекбокс присутствия игрока, учитывать только присутствующих персонажей.

```js
const presentMembers = members.filter((member) => member.isPresent !== false);
```

Если состояния присутствия нет, считать всех персонажей присутствующими.

Учитывать только персонажей с уровнем от `1` до `20`.

```js
function encounterLevelRows(members) {
  return members
    .map((member) => ({
      name: member.name || "Без имени",
      level: Number(member.level) || 0,
    }))
    .filter((row) => row.level >= 1 && row.level <= 20);
}
```

Если после фильтрации нет уровней, калькулятор должен вернуть ошибку:

```js
{
  ok: false,
  message: "В группе нет персонажей с уровнем от 1 до 20.",
  members: [],
  difficulties: []
}
```

## 2. Сложности

Используются три категории:

```js
const ENCOUNTER_DIFFICULTIES = [
  ["low", "Низкая"],
  ["medium", "Средняя"],
  ["high", "Высокая"],
];
```

Смысл категорий:

- `Низкая` — бой должен создать напряжение, но группа обычно побеждает без потерь.
- `Средняя` — без лечения и ресурсов может стать опасно; слабые персонажи могут выйти из строя.
- `Высокая` — потенциально смертельная сцена, требует тактики и ресурсов.

## 3. Таблица XP на персонажа

Таблица определяет бюджет XP для одного персонажа конкретного уровня.

```js
const XP_BY_LEVEL = {
  1: { low: 50, medium: 75, high: 100 },
  2: { low: 100, medium: 150, high: 200 },
  3: { low: 150, medium: 225, high: 400 },
  4: { low: 250, medium: 375, high: 500 },
  5: { low: 500, medium: 750, high: 1100 },
  6: { low: 600, medium: 1000, high: 1400 },
  7: { low: 750, medium: 1300, high: 1700 },
  8: { low: 1000, medium: 1700, high: 2100 },
  9: { low: 1300, medium: 2000, high: 2600 },
  10: { low: 1600, medium: 2300, high: 3100 },
  11: { low: 1900, medium: 2900, high: 4100 },
  12: { low: 2200, medium: 3700, high: 4700 },
  13: { low: 2600, medium: 4200, high: 5400 },
  14: { low: 2900, medium: 4900, high: 6200 },
  15: { low: 3300, medium: 5400, high: 7800 },
  16: { low: 3800, medium: 6100, high: 9800 },
  17: { low: 4500, medium: 7200, high: 11700 },
  18: { low: 5000, medium: 8700, high: 14200 },
  19: { low: 5500, medium: 10700, high: 17200 },
  20: { low: 6400, medium: 13200, high: 22000 },
};
```

## 4. Таблица XP по ПО / CR

```js
const XP_BY_CR = {
  "0": 10,
  "1/8": 25,
  "1/4": 50,
  "1/2": 100,
  "1": 200,
  "2": 450,
  "3": 700,
  "4": 1100,
  "5": 1800,
  "6": 2300,
  "7": 2900,
  "8": 3900,
  "9": 5000,
  "10": 5900,
  "11": 7200,
  "12": 8400,
  "13": 10000,
  "14": 11500,
  "15": 13000,
  "16": 15000,
  "17": 18000,
  "18": 20000,
  "19": 22000,
  "20": 25000,
  "21": 33000,
  "22": 41000,
  "23": 50000,
  "24": 62000,
  "25": 75000,
  "26": 90000,
  "27": 105000,
  "28": 120000,
  "29": 135000,
  "30": 155000,
};
```

## 5. Формула бюджета сложности

Бюджет сложности — это сумма XP для каждого персонажа.

```js
function encounterBudgetForLevels(levels, difficulty) {
  return levels.reduce((sum, level) => {
    const row = XP_BY_LEVEL[level];
    if (!row) return sum;
    return sum + row[difficulty];
  }, 0);
}
```

Пример:

```text
5 персонажей 3 уровня
Средняя сложность = 225 * 5 = 1125 XP
```

Если уровни разные, считать каждого персонажа отдельно:

```text
2 персонажа 3 уровня и 1 персонаж 4 уровня
Средняя сложность = 225 + 225 + 375 = 825 XP
```

## 6. Средний уровень группы

Средний уровень нужен для предупреждений.

```js
const averageLevel = Math.round((levels.reduce((a, b) => a + b, 0) / levels.length) * 10) / 10;
```

Минимальный и максимальный уровень нужны для предупреждения о разбросе:

```js
const minLevel = Math.min(...levels);
const maxLevel = Math.max(...levels);
```

## 7. Конвертация ПО / CR в число

Нужно для сравнения CR со средним уровнем группы.

```js
function crToNumber(cr) {
  if (String(cr).includes("/")) {
    const [left, right] = String(cr).split("/").map(Number);
    return left / (right || 1);
  }

  return Number(cr) || 0;
}
```

## 8. Подсказка: одинаковые существа

Для каждого CR считать, сколько одинаковых существ помещается в бюджет.

Формула:

```text
count = floor(budget / xpOfCreature)
total = count * xpOfCreature
left = budget - total
```

Код:

```js
function encounterSingleSuggestions(budget, partySize, averageLevel) {
  const suggestions = [];

  for (const [cr, xp] of Object.entries(XP_BY_CR)) {
    const count = xp ? Math.floor(budget / xp) : 0;
    if (count <= 0) continue;

    const notes = [];
    const crValue = crToNumber(cr);

    if (count > partySize * 2) {
      notes.push("много существ");
    }

    if (crValue > averageLevel) {
      notes.push("ПО выше среднего уровня");
    }

    if (cr === "0") {
      notes.push("ПО 0 лучше использовать осторожно");
    }

    suggestions.push({
      cr,
      xp,
      count,
      total: count * xp,
      left: budget - count * xp,
      notes,
    });
  }

  return suggestions.reverse().slice(0, 14);
}
```

Особенности:

- Варианты с `count <= 0` не показывать.
- Список разворачивается, чтобы сначала шли более высокие CR.
- Показывать максимум `14` вариантов.

## 9. Подсказка: два сильных существа

Нужно перебрать все пары CR, где сумма XP не превышает бюджет.

Чтобы не дублировать зеркальные пары, второй цикл начинается с текущего индекса первого CR:

```js
function encounterPairSuggestions(budget) {
  const suggestions = [];
  const crItems = Object.entries(XP_BY_CR);

  for (let i = 0; i < crItems.length; i += 1) {
    const [leftCr, leftXp] = crItems[i];

    for (const [rightCr, rightXp] of crItems.slice(i)) {
      const total = leftXp + rightXp;

      if (total <= budget) {
        suggestions.push({
          leftCr,
          rightCr,
          total,
          left: budget - total,
        });
      }
    }
  }

  return suggestions
    .sort((a, b) => a.left - b.left || b.total - a.total)
    .slice(0, 8);
}
```

Сортировка:

1. Сначала минимальный остаток бюджета.
2. При равном остатке — больший total.
3. Показывать максимум `8` вариантов.

## 10. Подсказка: лидер + миньоны

Нужно выбрать одного лидера и несколько одинаковых миньонов.

Правила:

- XP лидера должен быть меньше бюджета.
- Миньонов должно быть минимум `2`.
- Миньонов не должно быть больше `max(12, partySize * 3)`.
- Общая сумма не должна превышать бюджет.

```js
function encounterBossMinionSuggestions(budget, partySize) {
  const suggestions = [];

  for (const [bossCr, bossXp] of Object.entries(XP_BY_CR)) {
    if (bossXp >= budget) continue;

    for (const [minionCr, minionXp] of Object.entries(XP_BY_CR)) {
      const minionCount = minionXp
        ? Math.floor((budget - bossXp) / minionXp)
        : 0;

      if (minionCount < 2) continue;
      if (minionCount > Math.max(12, partySize * 3)) continue;

      const total = bossXp + minionCount * minionXp;

      suggestions.push({
        bossCr,
        minionCr,
        minionCount,
        total,
        left: budget - total,
      });
    }
  }

  return suggestions
    .sort((a, b) => a.left - b.left || b.total - a.total)
    .slice(0, 8);
}
```

Сортировка такая же:

1. Сначала минимальный остаток бюджета.
2. При равном остатке — больший total.
3. Показывать максимум `8` вариантов.

## 11. Главная функция расчёта

```js
function prepareEncounterBudget(members) {
  const rows = encounterLevelRows(members);
  const levels = rows.map((row) => row.level);

  if (!levels.length) {
    return {
      ok: false,
      message: "В группе нет персонажей с уровнем от 1 до 20.",
      members: [],
      difficulties: [],
    };
  }

  const partySize = levels.length;
  const averageLevel =
    Math.round((levels.reduce((a, b) => a + b, 0) / partySize) * 10) / 10;
  const minLevel = Math.min(...levels);
  const maxLevel = Math.max(...levels);

  const difficulties = ENCOUNTER_DIFFICULTIES.map(([key, label]) => {
    const budget = encounterBudgetForLevels(levels, key);

    return {
      key,
      label,
      budget,
      single: encounterSingleSuggestions(budget, partySize, averageLevel),
      pairs: encounterPairSuggestions(budget),
      bossMinions: encounterBossMinionSuggestions(budget, partySize),
    };
  });

  const warnings = [
    "Если существ больше чем вдвое больше персонажей, бой может стать заметно опаснее из-за количества действий.",
    "Более 2-3 разных статблоков усложняют ведение сцены за столом.",
    "Существо с ПО выше среднего уровня группы может быстро вывести героя из строя одним действием.",
    "Существа с ПО 0 лучше использовать осторожно, особенно если они не дают опыта.",
  ];

  if (maxLevel - minLevel >= 3) {
    warnings.unshift(
      "В группе большой разброс уровней: младшие персонажи могут оказаться под гораздо большим риском."
    );
  }

  return {
    ok: true,
    members: rows,
    count: partySize,
    averageLevel,
    levelSummary: buildLevelSummary(levels),
    difficulties,
    warnings,
  };
}
```

## 12. Сводка уровней

Сводка нужна для UI.

```js
function buildLevelSummary(levels) {
  return [...new Set(levels)]
    .sort((a, b) => a - b)
    .map((level) => `${level} ур. x ${levels.filter((x) => x === level).length}`)
    .join(", ");
}
```

Пример:

```text
3 ур. x 4, 4 ур. x 1
```

## 13. Формат результата

Рекомендуемый JSON:

```js
{
  ok: true,
  members: [
    { name: "Иглат", level: 3 },
    { name: "Корфаэль", level: 3 }
  ],
  count: 2,
  averageLevel: 3,
  levelSummary: "3 ур. x 2",
  difficulties: [
    {
      key: "low",
      label: "Низкая",
      budget: 300,
      single: [],
      pairs: [],
      bossMinions: []
    },
    {
      key: "medium",
      label: "Средняя",
      budget: 450,
      single: [],
      pairs: [],
      bossMinions: []
    },
    {
      key: "high",
      label: "Высокая",
      budget: 800,
      single: [],
      pairs: [],
      bossMinions: []
    }
  ],
  warnings: []
}
```

## 14. UI-рекомендации

Минимально полезный интерфейс должен показывать:

- количество учитываемых персонажей;
- средний уровень;
- сводку уровней;
- карточки бюджетов `Низкая / Средняя / Высокая`;
- табы или секции по сложности;
- внутри каждой сложности:
  - таблицу одинаковых существ;
  - таблицу `лидер + миньоны`;
  - таблицу двух сильных существ;
- список предупреждений.

Для таблицы одинаковых существ:

```text
ПО | XP | Кол-во | Итого | Остаток | Риск
```

Для таблицы `лидер + миньоны`:

```text
Лидер | Миньоны | Итого | Остаток
```

Для таблицы двух сильных существ:

```text
Существо 1 | Существо 2 | Итого | Остаток
```

## 15. Важные ограничения

1. Этот расчёт не использует множители количества монстров из старых редакций правил.
2. Бюджет — это прямой лимит XP сцены.
3. Подсказки не подбирают конкретных монстров, только CR/ПО и количество.
4. Если в сцене много существ, сложность может быть выше ожидаемой из-за экономики действий.
5. Если CR существа выше среднего уровня группы, это нужно помечать как риск.
6. Если в группе большой разброс уровней `3+`, нужно показывать отдельное предупреждение.
7. Если часть игроков отсутствует, их персонажей нужно исключать из расчёта бюджета и сводок.

## 16. Быстрый пример

Вход:

```js
const members = [
  { name: "Иглат", level: 3, isPresent: true },
  { name: "Корфаэль", level: 3, isPresent: true },
  { name: "Серак", level: 3, isPresent: true },
  { name: "Элиас", level: 3, isPresent: true },
  { name: "Ганнибал", level: 3, isPresent: true },
];
```

Расчёт:

```text
Низкая: 150 * 5 = 750 XP
Средняя: 225 * 5 = 1125 XP
Высокая: 400 * 5 = 2000 XP
```

Если один игрок отсутствует:

```js
{ name: "Ганнибал", level: 3, isPresent: false }
```

Тогда:

```text
Низкая: 150 * 4 = 600 XP
Средняя: 225 * 4 = 900 XP
Высокая: 400 * 4 = 1600 XP
```
