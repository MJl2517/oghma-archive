# Импорт персонажей из Long Story Short JSON

Инструкция для агента, который должен реализовать импорт персонажа из Long Story Short в другом проекте.

## Цель

Из LSS JSON нужно получить минимум для формы:

- Имя
- Уровень
- КД
- Хиты
- Инициатива
- Пассивное восприятие
- Заметки

Дополнительно желательно уметь доставать характеристики, навыки, языки, инструменты и текстовые заметки, чтобы проект можно было расширять.

## 1. Принять оба формата LSS

Long Story Short может экспортировать данные двумя способами:

```js
payload
payload.data
```

Иногда `payload.data` может быть строкой JSON. Поэтому логика должна быть такой:

```js
function getLssRaw(payload) {
  let raw = payload?.data ?? payload;

  if (typeof raw === "string") {
    raw = JSON.parse(raw);
  }

  if (!raw || typeof raw !== "object") {
    throw new Error("Long Story Short JSON не содержит данных персонажа");
  }

  return raw;
}
```

## 2. Общие helper-функции

В LSS большинство значений лежит как объект с полем `value`:

```json
{
  "name": { "value": "Фалько" }
}
```

Используй безопасные helper-функции:

```js
function fieldValue(container, key, fallback = "") {
  const value = container?.[key];

  if (value && typeof value === "object" && "value" in value) {
    return value.value ?? fallback;
  }

  return value ?? fallback;
}

function pathValue(obj, path, fallback = "") {
  let current = obj;

  for (const key of path) {
    if (!current || typeof current !== "object") return fallback;
    current = current[key];
  }

  return current ?? fallback;
}
```

## 3. Основные секции LSS

Обычно структура такая:

```js
raw.name
raw.info
raw.stats
raw.saves
raw.skills
raw.vitality
raw.text
raw.resources
raw.coins
raw.weaponsList
raw.proficiency
```

Безопасно получать так:

```js
const info = raw.info ?? {};
const stats = raw.stats ?? {};
const skills = raw.skills ?? {};
const vitality = raw.vitality ?? {};
const text = raw.text ?? {};
```

## 4. Основные поля

### Имя

```js
const name = pathValue(raw, ["name", "value"], "Без имени");
```

### Уровень

```js
const level = Number(fieldValue(info, "level", 1)) || 1;
```

### КД

```js
const ac = Number(fieldValue(vitality, "ac", 10)) || 10;
```

### Хиты

Для простой формы лучше брать максимальные хиты, если поле называется просто `Хиты`.

```js
const hp =
  Number(fieldValue(vitality, "hp-max", 0)) ||
  Number(fieldValue(vitality, "hp-current", 0)) ||
  0;
```

Если проект различает текущие и максимальные:

```js
const hpCurrent = Number(fieldValue(vitality, "hp-current", 0)) || 0;
const hpMax = Number(fieldValue(vitality, "hp-max", 0)) || 0;
const hpTemp = Number(fieldValue(vitality, "hp-temp", 0)) || 0;
```

## 5. Характеристики

Ключи характеристик:

```js
const ABILITIES = {
  str: "Сила",
  dex: "Ловкость",
  con: "Телосложение",
  int: "Интеллект",
  wis: "Мудрость",
  cha: "Харизма",
};
```

В LSS значение обычно:

```json
{
  "stats": {
    "dex": { "score": 14 }
  }
}
```

Важно: модификаторы лучше пересчитывать от `score`, а не доверять сохранённым значениям.

```js
function abilityModifier(score) {
  return Math.floor((Number(score || 10) - 10) / 2);
}

function normalizeStats(stats) {
  const result = {};

  for (const key of Object.keys(ABILITIES)) {
    const stat = stats?.[key] ?? {};
    const score = Number(stat.score ?? 10) || 10;
    const modifier = abilityModifier(score);

    result[key] = {
      key,
      label: ABILITIES[key],
      score,
      modifier,
    };
  }

  return result;
}
```

## 6. Инициатива

Если отдельного поля инициативы нет, считать от Ловкости.

```js
const normalizedStats = normalizeStats(stats);
const initiative = normalizedStats.dex.modifier;
```

Если нужно строкой с плюсом:

```js
function signed(n) {
  const number = Number(n) || 0;
  return number >= 0 ? `+${number}` : String(number);
}
```

## 7. Бонус мастерства

Если `raw.proficiency` есть, используй его. Иначе считай по уровню.

```js
function proficiencyBonus(level) {
  const lvl = Number(level) || 1;
  return Math.ceil(lvl / 4) + 1;
}

const proficiency = Number(raw.proficiency) || proficiencyBonus(level);
```

## 8. Навыки

Ключи навыков LSS обычно английские:

```js
const SKILL_LABELS = {
  acrobatics: "Акробатика",
  "animal handling": "Уход за животными",
  arcana: "Магия",
  athletics: "Атлетика",
  deception: "Обман",
  history: "История",
  insight: "Проницательность",
  intimidation: "Запугивание",
  investigation: "Анализ",
  medicine: "Медицина",
  nature: "Природа",
  perception: "Внимательность",
  performance: "Выступление",
  persuasion: "Убеждение",
  religion: "Религия",
  "sleight of hand": "Ловкость рук",
  stealth: "Скрытность",
  survival: "Выживание",
};
```

У навыка обычно есть:

```js
skill.baseStat
skill.isProf
skill.proficient
skill.prof
```

Владение может быть:

- `false` / `0` — нет владения
- `true` / `1` — владение
- `2` — экспертиза/компетенция

```js
function proficiencyMultiplier(item) {
  for (const key of ["isProf", "proficient", "prof"]) {
    if (key in item) {
      const value = item[key];

      if (typeof value === "boolean") {
        return value ? 1 : 0;
      }

      return Number(value) || 0;
    }
  }

  return 0;
}

function prepareSkills(rawSkills, normalizedStats, proficiency) {
  const result = {};

  for (const [key, skill] of Object.entries(rawSkills ?? {})) {
    const base = skill.baseStat;
    const statMod = normalizedStats?.[base]?.modifier ?? 0;
    const profMultiplier = proficiencyMultiplier(skill);
    const value = statMod + Math.floor(proficiency * profMultiplier);

    result[key] = {
      key,
      label: SKILL_LABELS[key] ?? key,
      baseStat: base,
      value,
      passive: value + 10,
      isProficient: profMultiplier > 0,
      isExpert: profMultiplier >= 2,
    };
  }

  return result;
}
```

## 9. Пассивное восприятие

Для поля `Пасс. восприятие`:

```js
const preparedSkills = prepareSkills(raw.skills, normalizedStats, proficiency);

const passivePerception =
  preparedSkills.perception?.passive ??
  preparedSkills["perception"]?.passive ??
  10 + normalizedStats.wis.modifier;
```

## 10. Языки и инструменты

LSS часто хранит это в текстовом блоке `text.prof`.

Пример пользовательского текста:

```text
Языки: общий, дварфийский

Инструменты: каменщика

Оружие: Кинжалы, дротики

Доспехи: нет
```

Нужно распарсить строки вида `Название: значения`.

```js
function cleanDisplayName(value) {
  return String(value ?? "")
    .replace(/\[[^\]]+\]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function splitValues(value) {
  return String(value || "")
    .replace(/\s+(и|and)\s+/gi, ",")
    .split(/[,;]+/)
    .map((x) => cleanDisplayName(x))
    .filter(Boolean);
}

function unique(items) {
  const seen = new Set();
  const out = [];

  for (const item of items) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }

  return out;
}

function parseProficiencies(body) {
  const result = {
    languages: [],
    tools: [],
    weapons: [],
    armor: [],
  };

  const fieldMap = {
    языки: "languages",
    язык: "languages",
    languages: "languages",

    инструменты: "tools",
    инструмент: "tools",
    tools: "tools",

    оружие: "weapons",
    оружия: "weapons",
    weapons: "weapons",

    доспехи: "armor",
    доспех: "armor",
    броня: "armor",
    armor: "armor",
  };

  for (const line of String(body || "").split(/\r?\n/)) {
    const match = line.match(/^\s*([^:：]+)\s*[:：]\s*(.+?)\s*$/);
    if (!match) continue;

    const label = cleanDisplayName(match[1]).toLowerCase();
    const key = fieldMap[label];
    if (!key) continue;

    result[key].push(...splitValues(match[2]));
  }

  return {
    languages: unique(result.languages),
    tools: unique(result.tools),
    weapons: unique(result.weapons),
    armor: unique(result.armor),
  };
}
```

## 11. Текстовые блоки и заметки

LSS текстовые поля могут быть обычной строкой или TipTap/ProseMirror-документом:

```json
{
  "type": "doc",
  "content": [
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "..." }]
    }
  ]
}
```

Нужен рекурсивный extractor:

```js
function tiptapToText(node) {
  if (!node) return "";

  if (typeof node === "string") return node;

  if (Array.isArray(node)) {
    return node.map(tiptapToText).filter(Boolean).join("\n");
  }

  if (typeof node !== "object") return "";

  if (node.type === "text") {
    return node.text || "";
  }

  const content = Array.isArray(node.content)
    ? node.content.map(tiptapToText).filter(Boolean)
    : [];

  if (node.type === "paragraph" || node.type === "heading") {
    return content.join("").trim();
  }

  return content.join("\n").trim();
}

function readTextSection(section) {
  return tiptapToText(
    section?.value?.data ??
    section?.data ??
    section?.value ??
    ""
  ).trim();
}
```

Обход всех текстовых секций:

```js
function prepareTextSections(text) {
  const result = {};

  for (const [key, section] of Object.entries(text ?? {})) {
    const body = readTextSection(section);
    if (body) result[key] = body;
  }

  return result;
}
```

Важные ключи LSS, которые стоит использовать в заметках:

```js
const IMPORTANT_TEXT_KEYS = [
  "background",
  "notes-1",
  "personality",
  "trait",
  "ideals",
  "ideal",
  "bonds",
  "bond",
  "flaws",
  "flaw",
  "prof",
];
```

Для поля `Заметки` можно собрать так:

```js
function buildNotes(textSections) {
  return [
    textSections["background"] && `Предыстория:\n${textSections["background"]}`,
    textSections["personality"] && `Черты характера:\n${textSections["personality"]}`,
    textSections["trait"] && `Черты характера:\n${textSections["trait"]}`,
    textSections["ideals"] && `Идеалы:\n${textSections["ideals"]}`,
    textSections["ideal"] && `Идеалы:\n${textSections["ideal"]}`,
    textSections["bonds"] && `Привязанности:\n${textSections["bonds"]}`,
    textSections["bond"] && `Привязанности:\n${textSections["bond"]}`,
    textSections["flaws"] && `Слабости:\n${textSections["flaws"]}`,
    textSections["flaw"] && `Слабости:\n${textSections["flaw"]}`,
    textSections["notes-1"] && `Заметки:\n${textSections["notes-1"]}`,
  ].filter(Boolean).join("\n\n");
}
```

## 12. Итоговый mapper под форму

Минимальная функция:

```js
function importPlayerFromLss(payload) {
  const raw = getLssRaw(payload);

  const info = raw.info ?? {};
  const vitality = raw.vitality ?? {};
  const stats = normalizeStats(raw.stats ?? {});
  const level = Number(fieldValue(info, "level", 1)) || 1;
  const proficiency = Number(raw.proficiency) || proficiencyBonus(level);
  const skills = prepareSkills(raw.skills ?? {}, stats, proficiency);
  const textSections = prepareTextSections(raw.text ?? {});
  const notes = buildNotes(textSections);

  return {
    name: pathValue(raw, ["name", "value"], "Без имени"),
    level,
    ac: Number(fieldValue(vitality, "ac", 10)) || 10,
    hp:
      Number(fieldValue(vitality, "hp-max", 0)) ||
      Number(fieldValue(vitality, "hp-current", 0)) ||
      0,
    initiative: stats.dex.modifier,
    passivePerception:
      skills.perception?.passive ??
      10 + stats.wis.modifier,
    activeInCombat: true,
    notes,
  };
}
```

## 13. Расширенный mapper

Если нужно больше данных:

```js
function importFullPlayerFromLss(payload) {
  const raw = getLssRaw(payload);
  const info = raw.info ?? {};
  const vitality = raw.vitality ?? {};
  const stats = normalizeStats(raw.stats ?? {});
  const level = Number(fieldValue(info, "level", 1)) || 1;
  const proficiency = Number(raw.proficiency) || proficiencyBonus(level);
  const skills = prepareSkills(raw.skills ?? {}, stats, proficiency);
  const textSections = prepareTextSections(raw.text ?? {});
  const parsedProf = parseProficiencies(textSections.prof || "");

  return {
    name: pathValue(raw, ["name", "value"], "Без имени"),
    level,
    ac: Number(fieldValue(vitality, "ac", 10)) || 10,
    hp:
      Number(fieldValue(vitality, "hp-max", 0)) ||
      Number(fieldValue(vitality, "hp-current", 0)) ||
      0,
    initiative: stats.dex.modifier,
    passivePerception:
      skills.perception?.passive ??
      10 + stats.wis.modifier,
    activeInCombat: true,
    notes: buildNotes(textSections),

    race: fieldValue(info, "race"),
    className: fieldValue(info, "charClass"),
    subclass: fieldValue(info, "charSubclass"),
    background: fieldValue(info, "background"),
    alignment: fieldValue(info, "alignment"),
    stats,
    skills,
    passiveSkills: Object.values(skills).map((skill) => ({
      ...skill,
      passive: skill.value + 10,
    })),
    languages: parsedProf.languages,
    tools: parsedProf.tools,
    weapons: parsedProf.weapons,
    armor: parsedProf.armor,
  };
}
```

## 14. Основные правила надёжности

1. Не доверять сохранённым модификаторам характеристик. Считать от `score`.
2. Не доверять сохранённым значениям навыков. Считать по формуле: `мод характеристики + бонус мастерства × владение`.
3. Пассивный навык всегда считать как `значение навыка + 10`.
4. Все поля читать через fallback. LSS JSON может отличаться по версии.
5. `payload.data` может быть объектом или строкой JSON.
6. Текстовые поля могут быть строкой или TipTap-документом.
7. Из названий предметов и владений желательно удалять английский перевод в квадратных скобках: `[Bless]`, `[Bane]`.
8. Для формы на скриншоте достаточно `importPlayerFromLss`, но лучше сразу сохранить расширенные данные, чтобы потом не переписывать импорт.
