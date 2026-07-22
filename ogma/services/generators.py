from __future__ import annotations

import json
import random
import re


GENERATORS_EXPORT_SCHEMA = "ogma.generators.export.v1"
GENERATOR_FALLBACK_TITLE = "Генератор"
GENERATOR_FALLBACK_CATEGORY = "Прочее"
GENERATOR_UNSORTED_TAG = "Неотсортированные"
GENERATOR_SORT_OPTIONS = {
    "title": "Название",
    "category": "Категория",
    "updated": "Обновлено",
    "created": "Создано",
}


class GeneratorValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def split_expression(expression: str) -> list[str]:
    compact = re.sub(r"\s+", "", str(expression or "").lower())
    if not compact:
        raise GeneratorValidationError(["Укажите формулу кубов."])
    parts = re.findall(r"[+-]?[^+-]+", compact)
    if not parts or "".join(parts) != compact:
        raise GeneratorValidationError(["Формула должна состоять из кубов и чисел, например 1d8 или 2d6+1."])
    return parts


def parse_expression(expression: str) -> list[dict]:
    parsed = []
    errors = []
    for part in split_expression(expression):
        sign = -1 if part.startswith("-") else 1
        clean = re.sub(r"^[+-]", "", part)
        dice_match = re.fullmatch(r"(\d*)d(\d+)", clean)
        if dice_match:
            count = int(dice_match.group(1) or 1)
            sides = int(dice_match.group(2))
            if count < 1 or count > 100:
                errors.append("Количество кубов должно быть от 1 до 100.")
            if sides < 2 or sides > 1000:
                errors.append("Количество граней должно быть от 2 до 1000.")
            parsed.append({"type": "dice", "sign": sign, "count": count, "sides": sides})
            continue
        if re.fullmatch(r"\d+", clean):
            parsed.append({"type": "number", "sign": sign, "value": int(clean)})
            continue
        errors.append(f"Не удалось разобрать часть формулы: {part}.")
    if errors:
        raise GeneratorValidationError(errors)
    if not any(part["type"] == "dice" for part in parsed):
        raise GeneratorValidationError(["Формула должна содержать хотя бы один куб."])
    return parsed


def expression_bounds(parts: list[dict]) -> tuple[int, int]:
    minimum = 0
    maximum = 0
    for part in parts:
        if part["type"] == "number":
            value = part["sign"] * part["value"]
            minimum += value
            maximum += value
            continue
        low = part["count"]
        high = part["count"] * part["sides"]
        if part["sign"] > 0:
            minimum += low
            maximum += high
        else:
            minimum -= high
            maximum -= low
    return minimum, maximum


def normalize_expression(expression: str) -> str:
    parts = parse_expression(expression)
    formatted = []
    for index, part in enumerate(parts):
        prefix = "-" if part["sign"] < 0 else ("+" if index else "")
        if part["type"] == "dice":
            value = f"{part['count']}d{part['sides']}"
        else:
            value = str(part["value"])
        formatted.append(prefix + value)
    return "".join(formatted)


def roll_expression(expression: str) -> dict:
    parts = parse_expression(expression)
    total = 0
    details = []
    for part in parts:
        if part["type"] == "number":
            value = part["sign"] * part["value"]
            total += value
            details.append(f"{'+' if value >= 0 else ''}{value}")
            continue
        rolls = [random.randint(1, part["sides"]) for _ in range(part["count"])]
        subtotal = sum(rolls) * part["sign"]
        total += subtotal
        prefix = "-" if part["sign"] < 0 else ""
        details.append(f"{prefix}[{', '.join(str(roll) for roll in rolls)}]")
    return {"total": total, "details": " ".join(details)}


def parse_row_range(raw_range: str) -> tuple[int, int]:
    value = str(raw_range or "").strip()
    if not value:
        raise ValueError
    match = re.fullmatch(r"(-?\d+)(?:\s*[-–—]\s*(-?\d+))?", value)
    if not match:
        raise ValueError
    range_min = int(match.group(1))
    range_max = int(match.group(2) if match.group(2) is not None else match.group(1))
    return range_min, range_max


def ranges_from_form(deps: dict, form) -> list[dict]:
    ranges = form.getlist("row_range")
    mins = form.getlist("row_min")
    maxes = form.getlist("row_max")
    results = form.getlist("row_result")
    row_ids = form.getlist("row_id")
    rows = []
    errors = []
    for index, result in enumerate(results):
        result_markdown = str(result or "").strip()
        raw_range = str(ranges[index] if index < len(ranges) else "").strip()
        raw_min = str(mins[index] if index < len(mins) else "").strip()
        raw_max = str(maxes[index] if index < len(maxes) else "").strip()
        row_id = str(row_ids[index] if index < len(row_ids) else "").strip() or deps["uuid4"]().hex
        if not raw_range and not raw_min and not raw_max and not result_markdown:
            continue
        try:
            if raw_range:
                range_min, range_max = parse_row_range(raw_range)
            else:
                range_min = int(raw_min)
                range_max = int(raw_max)
        except ValueError:
            errors.append(f"Строка {index + 1}: диапазон должен быть числом или записью 1-4.")
            continue
        if range_min > range_max:
            errors.append(f"Строка {index + 1}: начало диапазона больше конца.")
        if not result_markdown:
            errors.append(f"Строка {index + 1}: результат не должен быть пустым.")
        rows.append({"id": row_id, "min": range_min, "max": range_max, "result_markdown": result_markdown})
    if errors:
        raise GeneratorValidationError(errors)
    return rows


def validate_rows(rows: list[dict], bounds: tuple[int, int]) -> list[dict]:
    errors = []
    if not rows:
        raise GeneratorValidationError(["Добавьте хотя бы одну строку таблицы."])
    minimum, maximum = bounds
    normalized = sorted(rows, key=lambda row: (row["min"], row["max"]))
    expected = minimum
    for row in normalized:
        if row["min"] < minimum or row["max"] > maximum:
            errors.append(f"Диапазон {row['min']}-{row['max']} выходит за пределы формулы {minimum}-{maximum}.")
        if row["min"] < expected:
            errors.append(f"Диапазон {row['min']}-{row['max']} пересекается с предыдущим.")
        if row["min"] > expected:
            errors.append(f"Не покрыто значение {expected}.")
        expected = max(expected, row["max"] + 1)
    if expected <= maximum:
        errors.append(f"Не покрыто значение {expected}.")
    if errors:
        raise GeneratorValidationError(errors)
    return normalized


def normalize_generator_item_tags(deps: dict, raw_tags) -> list[str]:
    tags = deps["normalize_tags"](raw_tags)
    non_service = [tag for tag in tags if tag.casefold() != deps["UNSORTED_GENERATOR_TAG"].casefold()]
    return deps["sort_tags_alphabetically"](non_service) or [deps["UNSORTED_GENERATOR_TAG"]]


def generator_from_form(deps: dict, form, existing: dict | None = None) -> dict:
    now = deps["datetime"].now().isoformat(timespec="seconds")
    dice_expression = normalize_expression(form.get("dice_expression", existing.get("dice_expression", "1d20") if existing else "1d20"))
    rows = validate_rows(ranges_from_form(deps, form), expression_bounds(parse_expression(dice_expression)))
    category = deps["normalize_generator_category"](form.get("category", existing.get("category", "") if existing else ""))
    tags = normalize_generator_item_tags(deps, form.get("tags", existing.get("tags", "") if existing else ""))
    return {
        "id": existing.get("id") if existing else deps["uuid4"]().hex,
        "title": form.get("title", "").strip() or (existing.get("title") if existing else GENERATOR_FALLBACK_TITLE),
        "description": form.get("description", "").strip(),
        "dice_expression": dice_expression,
        "category": category,
        "tags": tags,
        "rows": rows,
        "created_at": existing.get("created_at", now) if existing else now,
        "updated_at": now,
    }


def ensure_taxonomy(deps: dict, generator: dict) -> None:
    tags = deps["load_generator_tags"]()
    categories = deps["load_generator_categories"]()
    for tag in generator.get("tags", []):
        if tag.casefold() not in {item.casefold() for item in tags}:
            tags.append(tag)
    category = generator.get("category", GENERATOR_FALLBACK_CATEGORY)
    if category.casefold() not in {item.casefold() for item in categories}:
        categories.append(category)
    deps["save_generator_tags"](tags)
    deps["save_generator_categories"](categories)


def _clean_generator_for_export(generator: dict) -> dict:
    return {
        "id": str(generator.get("id", "")).strip(),
        "title": str(generator.get("title", GENERATOR_FALLBACK_TITLE)).strip() or GENERATOR_FALLBACK_TITLE,
        "description": str(generator.get("description", "")).strip(),
        "dice_expression": str(generator.get("dice_expression", "1d20")).strip() or "1d20",
        "category": str(generator.get("category", GENERATOR_FALLBACK_CATEGORY)).strip() or GENERATOR_FALLBACK_CATEGORY,
        "tags": [str(tag).strip() for tag in generator.get("tags", []) if str(tag).strip()],
        "rows": [
            {
                "id": str(row.get("id", "")).strip(),
                "min": int(row.get("min", row.get("range_min", 0))),
                "max": int(row.get("max", row.get("range_max", 0))),
                "result_markdown": str(row.get("result_markdown") or row.get("result") or "").strip(),
            }
            for row in generator.get("rows", [])
            if isinstance(row, dict)
        ],
        "created_at": str(generator.get("created_at", "")).strip(),
        "updated_at": str(generator.get("updated_at", "")).strip(),
    }


def _normalize_import_generator(deps: dict, raw_generator: dict, now: str) -> dict | None:
    if not isinstance(raw_generator, dict):
        return None
    title = str(raw_generator.get("title", "")).strip()
    dice_expression = normalize_expression(str(raw_generator.get("dice_expression", "1d20")).strip() or "1d20")
    rows = []
    for row in raw_generator.get("rows", []):
        if not isinstance(row, dict):
            continue
        result_markdown = str(row.get("result_markdown") or row.get("result") or "").strip()
        if not result_markdown:
            raise GeneratorValidationError(["Результат строки не должен быть пустым."])
        rows.append(
            {
                "id": str(row.get("id", "")).strip() or deps["uuid4"]().hex,
                "min": int(row.get("min", row.get("range_min", 0))),
                "max": int(row.get("max", row.get("range_max", 0))),
                "result_markdown": result_markdown,
            }
        )
    rows = validate_rows(rows, expression_bounds(parse_expression(dice_expression)))
    return {
        "id": str(raw_generator.get("id", "")).strip() or deps["uuid4"]().hex,
        "title": title or GENERATOR_FALLBACK_TITLE,
        "description": str(raw_generator.get("description", "")).strip(),
        "dice_expression": dice_expression,
        "category": deps["normalize_generator_category"](raw_generator.get("category", GENERATOR_FALLBACK_CATEGORY)),
        "tags": normalize_generator_item_tags(deps, raw_generator.get("tags", [])),
        "rows": rows,
        "created_at": str(raw_generator.get("created_at", "")).strip() or now,
        "updated_at": str(raw_generator.get("updated_at", "")).strip() or now,
    }


def _generator_import_key(generator: dict) -> str:
    return f"{str(generator.get('title', '')).strip().casefold()}||{str(generator.get('category', '')).strip().casefold()}"


def _merge_unique_labels(existing: list[str], *incoming_groups) -> list[str]:
    merged = list(existing)
    known = {str(item).casefold() for item in merged}
    for group in incoming_groups:
        if not isinstance(group, (list, tuple, set)):
            continue
        for value in group:
            clean = str(value or "").strip()
            key = clean.casefold()
            if clean and key not in known:
                merged.append(clean)
                known.add(key)
    return merged


def generators_page_context(deps: dict, query: dict) -> dict:
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    selected_category = query.get("category", "").strip()
    search = query.get("q", "").strip()
    sort = query.get("sort", "title").strip()
    if sort not in GENERATOR_SORT_OPTIONS:
        sort = "title"
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_GENERATORS_PER_PAGE"], type=int)
    if per_page not in deps["GENERATORS_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_GENERATORS_PER_PAGE"]

    all_generators = deps["prepare_generators"]()
    generators = all_generators[:]
    if selected_category:
        generators = [item for item in generators if item.get("category", "").casefold() == selected_category.casefold()]
    for tag in selected_tags:
        generators = [item for item in generators if any(item_tag.casefold() == tag.casefold() for item_tag in item.get("tags", []))]
    for tag in excluded_tags:
        generators = [item for item in generators if all(item_tag.casefold() != tag.casefold() for item_tag in item.get("tags", []))]
    if search:
        query_text = search.casefold()
        generators = [
            item
            for item in generators
            if query_text in " ".join(
                [
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("category", ""),
                    item.get("dice_expression", ""),
                    " ".join(item.get("tags", [])),
                    " ".join(row.get("result_markdown", "") for row in item.get("rows", [])),
                ]
            ).casefold()
        ]

    sorters = {
        "title": lambda item: (item.get("title", "").casefold(), item.get("category", "")),
        "category": lambda item: (item.get("category", "").casefold(), item.get("title", "").casefold()),
        "updated": lambda item: (item.get("updated_at", item.get("created_at", "")), item.get("title", "").casefold()),
        "created": lambda item: (item.get("created_at", ""), item.get("title", "").casefold()),
    }
    generators.sort(key=sorters[sort], reverse=sort in {"updated", "created"})
    filtered_generators_count = len(generators)
    generators, pagination = deps["paginate_items"](generators, page, per_page)
    return {
        "generators": generators,
        "all_generators_count": len(all_generators),
        "filtered_generators_count": filtered_generators_count,
        "pagination": pagination,
        "per_page_options": deps["GENERATORS_PER_PAGE_OPTIONS"],
        "tags": deps["visible_generator_tags"](all_generators),
        "categories": deps["load_generator_categories"](),
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "selected_category": selected_category,
        "search": search,
        "sort": sort,
        "sort_options": GENERATOR_SORT_OPTIONS,
        "required_tags": deps["REQUIRED_GENERATOR_TAGS"],
    }


def generator_edit_modal_context(deps: dict, query: dict, generator_id: str) -> tuple[dict, int]:
    generator = deps["prepare_generator"](deps["load_generator"](generator_id))
    if generator is None:
        return {"ok": False, "error": "generator_not_found"}, 404
    all_generators = deps["prepare_generators"]()
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    sort = query.get("sort", "title").strip()
    if sort not in GENERATOR_SORT_OPTIONS:
        sort = "title"
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_GENERATORS_PER_PAGE"], type=int)
    if per_page not in deps["GENERATORS_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_GENERATORS_PER_PAGE"]
    return {
        "generator": generator,
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "selected_category": query.get("category", "").strip(),
        "search": query.get("q", "").strip(),
        "sort": sort,
        "pagination": {"page": max(page, 1), "per_page": per_page},
        "tags": deps["visible_generator_tags"](all_generators),
        "categories": deps["load_generator_categories"](),
        "required_tags": deps["REQUIRED_GENERATOR_TAGS"],
    }, 200


def create_generator(deps: dict, form) -> dict:
    generators = deps["load_generators"]()
    generator = generator_from_form(deps, form)
    ensure_taxonomy(deps, generator)
    deps["save_generators"]([generator, *generators])
    return {"ok": True, "generator": generator}


def update_generator(deps: dict, form, generator_id: str) -> tuple[dict, int]:
    generators = deps["load_generators"]()
    for index, item in enumerate(generators):
        if item.get("id") != generator_id:
            continue
        generator = generator_from_form(deps, form, item)
        generators[index] = generator
        ensure_taxonomy(deps, generator)
        deps["save_generators"](generators)
        return {"ok": True, "generator": generator}, 200
    return {"ok": False, "error": "generator_not_found"}, 404


def delete_generators(deps: dict, form) -> dict:
    generator_ids = set(form.getlist("generator_ids"))
    if generator_ids:
        deps["save_generators"]([item for item in deps["load_generators"]() if item.get("id") not in generator_ids])
    return {"ok": True}


def export_generators(deps: dict, query: dict) -> tuple[str, str, int]:
    selected_ids = {str(item).strip() for item in query.getlist("id") if str(item).strip()}
    generators = deps["prepare_generators"]()
    if selected_ids:
        generators = [generator for generator in generators if generator.get("id") in selected_ids]
    payload = {
        "schema": GENERATORS_EXPORT_SCHEMA,
        "exported_at": deps["datetime"].now().isoformat(timespec="seconds"),
        "labels": {
            "tags": deps["load_generator_tags"](),
            "categories": deps["load_generator_categories"](),
        },
        "generators": [_clean_generator_for_export(generator) for generator in generators],
    }
    filename = "ogma-generators.json" if not selected_ids else "ogma-generators-selected.json"
    return filename, json.dumps(payload, ensure_ascii=False, indent=2), 200


def import_generators(deps: dict, files) -> tuple[dict, int]:
    upload = files.get("generators_file")
    if upload is None or not getattr(upload, "filename", ""):
        return {"ok": False, "error": "missing_file"}, 400

    try:
        raw_payload = load_limited_json_stream(upload.stream)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"ok": False, "error": "invalid_json"}, 400

    if isinstance(raw_payload, list):
        incoming_raw = raw_payload
        labels = {}
    elif isinstance(raw_payload, dict):
        incoming_raw = raw_payload.get("generators", [])
        labels = raw_payload.get("labels", {})
    else:
        return {"ok": False, "error": "invalid_payload"}, 400

    if not isinstance(incoming_raw, list):
        return {"ok": False, "error": "invalid_generators"}, 400

    now = deps["datetime"].now().isoformat(timespec="seconds")
    imported_generators = []
    errors = []
    for index, item in enumerate(incoming_raw, start=1):
        try:
            generator = _normalize_import_generator(deps, item, now)
        except (TypeError, ValueError, GeneratorValidationError) as error:
            errors.append(f"Генератор {index}: {error}")
            continue
        if generator is not None:
            imported_generators.append(generator)
    if errors:
        return {"ok": False, "error": "invalid_generators", "errors": errors}, 400
    if not imported_generators:
        return {"ok": False, "error": "empty_import"}, 400

    generators = deps["load_generators"]()
    by_id = {str(generator.get("id", "")).strip(): index for index, generator in enumerate(generators) if str(generator.get("id", "")).strip()}
    by_title_category = {_generator_import_key(generator): index for index, generator in enumerate(generators) if _generator_import_key(generator).strip("|")}

    created = 0
    updated = 0
    for generator in imported_generators:
        match_index = by_id.get(generator["id"])
        if match_index is None:
            match_index = by_title_category.get(_generator_import_key(generator))

        if match_index is None:
            created += 1
            generators.insert(0, generator)
            by_id = {str(item.get("id", "")).strip(): index for index, item in enumerate(generators) if str(item.get("id", "")).strip()}
            by_title_category = {_generator_import_key(item): index for index, item in enumerate(generators) if _generator_import_key(item).strip("|")}
            continue

        previous = generators[match_index]
        generator["created_at"] = previous.get("created_at") or generator.get("created_at") or now
        generator["updated_at"] = now
        generators[match_index] = generator
        by_id[generator["id"]] = match_index
        by_title_category[_generator_import_key(generator)] = match_index
        updated += 1

    imported_tags = labels.get("tags", []) if isinstance(labels, dict) else []
    imported_categories = labels.get("categories", []) if isinstance(labels, dict) else []
    deps["save_generator_tags"](_merge_unique_labels(deps["load_generator_tags"](), imported_tags, *[generator["tags"] for generator in imported_generators]))
    deps["save_generator_categories"](_merge_unique_labels(deps["load_generator_categories"](), imported_categories, [generator["category"] for generator in imported_generators]))
    deps["save_generators"](generators)
    return {"ok": True, "created": created, "updated": updated, "total": len(imported_generators)}, 200


def add_generator_tag(deps: dict, form) -> dict:
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_generator_tags"](), tag)
    if created:
        deps["save_generator_tags"](tags)
    return {"ok": True, "tag": tag, "tags": deps["load_generator_tags"](), "created": created}


def delete_generator_tag(deps: dict, form) -> tuple[dict, int]:
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_GENERATOR_TAGS"]}:
        return {"ok": False, "error": "service_tag", "tag": tag}, 400
    tags = deps["delete_tag_from_list"](deps["load_generator_tags"](), tag)
    generators = deps["load_generators"]()
    moved_ids = deps["remove_tag_from_items"](generators, tag, deps["REQUIRED_GENERATOR_TAGS"])
    deps["save_generator_tags"](tags)
    deps["save_generators"](generators)
    return {"ok": True, "tag": tag, "fallback": deps["UNSORTED_GENERATOR_TAG"], "moved_generator_ids": moved_ids}, 200


def _rename_generator_label(labels: list[str], old_label: str, new_label: str) -> tuple[list[str], str]:
    old_key = old_label.casefold()
    new_key = new_label.casefold()
    canonical_new_label = next((label for label in labels if label.casefold() == new_key), new_label)
    renamed_labels = []
    has_new_label = False
    for label in labels:
        label_key = label.casefold()
        if label_key == new_key:
            has_new_label = True
        if label_key == old_key:
            if not has_new_label and all(item.casefold() != new_key for item in renamed_labels):
                renamed_labels.append(canonical_new_label)
                has_new_label = True
            continue
        if label_key != new_key or all(item.casefold() != new_key for item in renamed_labels):
            renamed_labels.append(label)
    if not has_new_label and all(item.casefold() != new_key for item in renamed_labels):
        renamed_labels.append(canonical_new_label)
    return renamed_labels, canonical_new_label


def rename_generator_tag(deps: dict, form) -> tuple[dict, int]:
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_GENERATOR_TAGS"]}
    if not old_tag or old_tag.casefold() in required_keys:
        return {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() in required_keys:
        return {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_generator_tags"]()
    renamed_tags, canonical_new_tag = _rename_generator_label(tags, old_tag, new_tag)
    if old_tag.casefold() == canonical_new_tag.casefold():
        return {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "renamed_generator_ids": [], "tags": tags}, 200

    generators = deps["load_generators"]()
    old_key = old_tag.casefold()
    renamed_generator_ids = []
    for generator in generators:
        raw_tags = generator.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        generator["tags"] = normalize_generator_item_tags(
            deps,
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags],
        )
        generator["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        renamed_generator_ids.append(generator.get("id", ""))

    deps["save_generator_tags"](renamed_tags)
    deps["save_generators"](generators)
    return {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_generator_ids": renamed_generator_ids,
        "tags": deps["load_generator_tags"](),
    }, 200


def add_generator_category(deps: dict, form) -> dict:
    category = form.get("category", "").strip()
    categories, created = deps["append_unique_tag"](deps["load_generator_categories"](), category)
    if created:
        deps["save_generator_categories"](categories)
    return {"ok": True, "category": category, "categories": deps["load_generator_categories"](), "created": created}


def delete_generator_category(deps: dict, form) -> tuple[dict, int]:
    category = form.get("category", "").strip()
    if not category:
        return {"ok": False, "error": "empty_category"}, 400
    kept = deps["delete_tag_from_list"](deps["load_generator_categories"](), category)
    fallback = next((item for item in kept if item.casefold() == GENERATOR_FALLBACK_CATEGORY.casefold()), None) or GENERATOR_FALLBACK_CATEGORY
    if fallback.casefold() not in {item.casefold() for item in kept}:
        kept.append(fallback)
    generators = deps["load_generators"]()
    moved_ids = deps["replace_item_field_value"](
        generators,
        "category",
        category,
        fallback,
        deps["datetime"].now().isoformat(timespec="seconds"),
    )
    deps["save_generator_categories"](kept)
    deps["save_generators"](generators)
    return {"ok": True, "category": category, "fallback": fallback, "moved_generator_ids": moved_ids}, 200


def rename_generator_category(deps: dict, form) -> tuple[dict, int]:
    old_category = form.get("category", "").strip()
    new_category = form.get("new_category", "").strip()
    if not old_category or not new_category:
        return {"ok": False, "error": "empty_category"}, 400

    categories = deps["load_generator_categories"]()
    renamed_categories, canonical_new_category = _rename_generator_label(categories, old_category, new_category)
    if old_category.casefold() == canonical_new_category.casefold():
        return {"ok": True, "category": old_category, "new_category": canonical_new_category, "moved_generator_ids": [], "categories": categories}, 200

    generators = deps["load_generators"]()
    moved_generator_ids = deps["replace_item_field_value"](
        generators,
        "category",
        old_category,
        canonical_new_category,
        deps["datetime"].now().isoformat(timespec="seconds"),
    )
    deps["save_generator_categories"](renamed_categories)
    deps["save_generators"](generators)
    return {
        "ok": True,
        "category": old_category,
        "new_category": canonical_new_category,
        "categories": deps["load_generator_categories"](),
        "moved_generator_ids": moved_generator_ids,
    }, 200


def roll_generator(deps: dict, generator_id: str) -> tuple[dict, int]:
    generator = deps["prepare_generator"](deps["load_generator"](generator_id))
    if generator is None:
        return {"ok": False, "error": "generator_not_found"}, 404
    roll = roll_expression(generator.get("dice_expression", "1d20"))
    result_row = next((row for row in generator.get("rows", []) if row["min"] <= roll["total"] <= row["max"]), None)
    if result_row is None:
        return {"ok": False, "error": "row_not_found", "total": roll["total"], "details": roll["details"]}, 422
    return {
        "ok": True,
        "generator_id": generator_id,
        "formula": generator.get("dice_expression", "1d20"),
        "total": roll["total"],
        "details": roll["details"],
        "row_id": result_row.get("id", ""),
        "range": {"min": result_row.get("min"), "max": result_row.get("max")},
        "result_markdown": result_row.get("result_markdown", ""),
        "result_html": str(deps["render_text_content"](result_row.get("result_markdown", ""))),
    }, 200
from ogma.safe_json import load_limited_json_stream
