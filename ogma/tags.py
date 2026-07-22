import re
from pathlib import Path

from ogma.json_store import read_json, write_json


def is_broken_label(value: str) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    if "\ufffd" in normalized:
        return True
    return bool(re.fullmatch(r"[?\s\-–—_]+", normalized))


def normalize_tags(raw_tags) -> list[str]:
    if isinstance(raw_tags, str):
        raw_tags = re.split(r"[,;\n]+", raw_tags)

    tags = []
    seen = set()
    for tag in raw_tags or []:
        normalized = str(tag or "").strip()
        if not normalized or is_broken_label(normalized):
            continue
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            tags.append(normalized)
    return tags


def sort_tags_alphabetically(tags: list[str], required_tags: list[str] | None = None) -> list[str]:
    required_tags = required_tags or []
    required_keys = {tag.casefold() for tag in required_tags}
    regular_tags = [tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys]
    regular_tags.sort(key=lambda tag: tag.casefold())
    return regular_tags + required_tags


def order_tags_custom(tags: list[str], required_tags: list[str] | None = None) -> list[str]:
    required_tags = required_tags or []
    required_keys = {tag.casefold() for tag in required_tags}
    regular_tags = [tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys]
    return regular_tags + required_tags


def load_tag_list(
    path: Path,
    default_tags: list[str],
    required_tags: list[str] | None = None,
    excluded_tags: list[str] | None = None,
) -> list[str]:
    if path.exists():
        tags = normalize_tags(read_json(path, fallback=[]))
    else:
        tags = default_tags[:]

    excluded_keys = {tag.casefold() for tag in excluded_tags or []}
    required_keys = {tag.casefold() for tag in required_tags or []}
    tags = [tag for tag in tags if tag.casefold() not in excluded_keys and tag.casefold() not in required_keys]
    return order_tags_custom(tags, required_tags)


def save_tag_list(
    path: Path,
    tags: list[str],
    required_tags: list[str] | None = None,
    excluded_tags: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    excluded_keys = {tag.casefold() for tag in excluded_tags or []}
    required_keys = {tag.casefold() for tag in required_tags or []}
    normalized = [
        tag
        for tag in normalize_tags(tags)
        if tag.casefold() not in excluded_keys and tag.casefold() not in required_keys
    ]
    write_json(path, order_tags_custom(normalized, required_tags))


def visible_tags(
    configured_tags: list[str],
    items: list[dict],
    item_tags_getter,
    required_tags: list[str] | None = None,
) -> list[str]:
    tags = configured_tags[:]
    known = {tag.casefold() for tag in tags}
    for item in items:
        for tag in item_tags_getter(item):
            if tag.casefold() not in known:
                known.add(tag.casefold())
                tags.append(tag)
    return order_tags_custom(tags, required_tags)


def load_category_list(
    path: Path,
    default_categories: list[str],
    sort: bool = False,
    empty_fallback: list[str] | None = None,
) -> list[str]:
    if path.exists():
        categories = normalize_tags(read_json(path, fallback=[]))
    else:
        categories = default_categories[:]
    if not categories:
        categories = (empty_fallback or default_categories)[:]
    if sort:
        categories.sort(key=lambda category: category.casefold())
    return categories


def save_category_list(path: Path, categories: list[str], fallback_category: str, sort: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_tags(categories) or [fallback_category]
    if sort:
        normalized.sort(key=lambda category: category.casefold())
    write_json(path, normalized)


def append_unique_tag(tags: list[str], tag: str) -> tuple[list[str], bool]:
    clean_tag = str(tag or "").strip()
    if not clean_tag:
        return tags[:], False
    existing_keys = {item.casefold() for item in tags}
    if clean_tag.casefold() in existing_keys:
        return tags[:], False
    return [*tags, clean_tag], True


def delete_tag_from_list(tags: list[str], tag: str) -> list[str]:
    tag_key = str(tag or "").strip().casefold()
    return [item for item in tags if item.casefold() != tag_key]


def remove_tag_from_items(
    items: list[dict],
    tag: str,
    fallback_tags: list[str],
    tags_field: str = "tags",
) -> list[str]:
    tag_key = str(tag or "").strip().casefold()
    moved_ids = []
    for item in items:
        item_tags = item.get(tags_field, [])
        had_tag = any(item_tag.casefold() == tag_key for item_tag in item_tags)
        item[tags_field] = [item_tag for item_tag in item_tags if item_tag.casefold() != tag_key]
        if not item[tags_field]:
            item[tags_field] = fallback_tags[:]
        if had_tag:
            moved_ids.append(item.get("id"))
    return [item_id for item_id in moved_ids if item_id]


def replace_item_field_value(
    items: list[dict],
    field: str,
    value: str,
    fallback_value: str,
    updated_at: str | None = None,
) -> list[str]:
    value_key = str(value or "").strip().casefold()
    moved_ids = []
    for item in items:
        if str(item.get(field, "") or "").casefold() != value_key:
            continue
        item[field] = fallback_value
        if updated_at is not None:
            item["updated_at"] = updated_at
        moved_ids.append(item.get("id"))
    return [item_id for item_id in moved_ids if item_id]


def reorder_existing_tags(
    requested_tags: list[str],
    current_tags: list[str],
    required_tags: list[str] | None = None,
) -> list[str]:
    requested_tags = normalize_tags(requested_tags)
    current_by_key = {tag.casefold(): tag for tag in current_tags}
    required_keys = {tag.casefold() for tag in required_tags or []}
    ordered = []
    seen = set()

    for tag in requested_tags:
        key = tag.casefold()
        if key in required_keys:
            continue
        if key in current_by_key and key not in seen:
            ordered.append(current_by_key[key])
            seen.add(key)

    for tag in current_tags:
        key = tag.casefold()
        if key in required_keys:
            continue
        if key not in seen:
            ordered.append(tag)
            seen.add(key)

    return ordered
