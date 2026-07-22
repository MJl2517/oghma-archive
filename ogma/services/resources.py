import os
from pathlib import Path
import subprocess

from ogma.errors import ValidationError
from ogma.safe_urls import ExternalHttpUrl, UnsafeUrl

RESOURCE_FALLBACK_TITLE = "\u0420\u0435\u0441\u0443\u0440\u0441"
RESOURCE_FALLBACK_OTHER = "\u041f\u0440\u043e\u0447\u0435\u0435"
RESOURCE_FALLBACK_BOOKS = "\u041a\u043d\u0438\u0433\u0438"
RESOURCE_PICK_FILE_TITLE = "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0444\u0430\u0439\u043b \u0440\u0435\u0441\u0443\u0440\u0441\u0430"
SAFE_OPEN_EXTENSIONS = {
    ".aac", ".avif", ".bmp", ".csv", ".doc", ".docx", ".epub", ".flac",
    ".gif", ".jpeg", ".jpg", ".json", ".m4a", ".md", ".mp3", ".oga",
    ".ogg", ".opus", ".pdf", ".png", ".rtf", ".txt", ".wav", ".webm",
    ".webp", ".xls", ".xlsx",
}


def resources_page_context(deps: dict, query: dict) -> dict:
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    selected_category = query.get("category", "").strip()
    selected_type = deps["normalize_resource_type"](query.get("type", "")) if query.get("type") else ""
    search = query.get("q", "").strip()
    open_resource_id = query.get("resource", "").strip()
    sort = query.get("sort", "title").strip()
    if sort not in deps["RESOURCE_SORT_OPTIONS"]:
        sort = "title"
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_RESOURCES_PER_PAGE"], type=int)
    if per_page not in deps["RESOURCES_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_RESOURCES_PER_PAGE"]

    all_resources = deps["prepare_resources"]()
    resources = all_resources[:]
    categories = deps["load_resource_categories"]()

    if selected_category:
        resources = [item for item in resources if item.get("category", "").casefold() == selected_category.casefold()]
    if selected_type:
        resources = [item for item in resources if item.get("source_type") == selected_type]
    for tag in selected_tags:
        resources = [item for item in resources if any(item_tag.casefold() == tag.casefold() for item_tag in item.get("tags", []))]
    for tag in excluded_tags:
        resources = [item for item in resources if all(item_tag.casefold() != tag.casefold() for item_tag in item.get("tags", []))]
    if search:
        query_text = search.casefold()
        resources = [
            item
            for item in resources
            if query_text
            in " ".join(
                [
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("category", ""),
                    item.get("target", ""),
                    item.get("path", ""),
                    item.get("url", ""),
                    " ".join(item.get("tags", [])),
                ]
            ).casefold()
        ]

    sorters = {
        "title": lambda item: (item.get("title", "").casefold(), item.get("category", "")),
        "category": lambda item: (item.get("category", "").casefold(), item.get("title", "").casefold()),
        "type": lambda item: (item.get("source_type", ""), item.get("title", "").casefold()),
        "updated": lambda item: (item.get("updated_at", item.get("created_at", "")), item.get("title", "").casefold()),
        "created": lambda item: (item.get("created_at", ""), item.get("title", "").casefold()),
    }
    reverse = sort in {"updated", "created"}
    resources.sort(key=sorters[sort], reverse=reverse)
    filtered_resources_count = len(resources)
    if open_resource_id:
        for index, resource in enumerate(resources):
            if resource.get("id") == open_resource_id:
                page = index // per_page + 1
                break
    resources, pagination = deps["paginate_items"](resources, page, per_page)

    return {
        "resources": resources,
        "all_resources_count": len(all_resources),
        "filtered_resources_count": filtered_resources_count,
        "pagination": pagination,
        "per_page_options": deps["RESOURCES_PER_PAGE_OPTIONS"],
        "tags": deps["visible_resource_tags"](all_resources),
        "categories": categories,
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "selected_category": selected_category,
        "selected_type": selected_type,
        "open_resource_id": open_resource_id,
        "search": search,
        "sort": sort,
        "sort_options": deps["RESOURCE_SORT_OPTIONS"],
        "required_tags": deps["REQUIRED_RESOURCE_TAGS"],
        "nav_sections": deps["GLOBAL_SECTIONS"],
    }


def create_resource(deps: dict, form) -> None:
    resources = deps["load_resources"]()
    source_type = deps["normalize_resource_type"](form.get("source_type", "web"))
    target = form.get("path" if source_type == "local" else "url", "").strip()
    selected_path = None
    if source_type == "web":
        try:
            target = ExternalHttpUrl.parse(target).value
        except UnsafeUrl as exc:
            raise ValidationError("Only a valid http or https resource URL is allowed.") from exc
    else:
        selected_path = deps["resolve_file_capability"](
            form.get("file_capability", "")
        )
        target = selected_path.name
    title = form.get("title", "").strip() or target.rstrip("/\\").rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or RESOURCE_FALLBACK_TITLE
    category = deps["normalize_resource_category"](form.get("category", deps["DEFAULT_RESOURCE_CATEGORIES"][0]))
    tags = deps["normalize_resource_item_tags"](form.get("tags", ""))
    now = deps["datetime"].now().isoformat(timespec="seconds")
    resource = {
        "id": deps["uuid4"]().hex,
        "source_type": source_type,
        "title": title,
        "description": form.get("description", "").strip(),
        "category": category,
        "tags": tags,
        "created_at": now,
        "updated_at": now,
    }
    if source_type == "local":
        resource["path"] = str(selected_path)
    else:
        resource["url"] = target
    resources.append(resource)

    known_tags = deps["load_resource_tags"]()
    for tag in tags:
        if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
            known_tags.append(tag)
    categories = deps["load_resource_categories"]()
    if category.casefold() not in {item.casefold() for item in categories}:
        categories.append(category)
    deps["save_resource_tags"](known_tags)
    deps["save_resource_categories"](categories)
    deps["save_resources"](resources)


def delete_resources(deps: dict, form) -> None:
    resource_ids = set(form.getlist("resource_ids"))
    if resource_ids:
        resources = [item for item in deps["load_resources"]() if item.get("id") not in resource_ids]
        deps["save_resources"](resources)


def open_resource(deps: dict, resource_id: str) -> tuple[dict, int]:
    resource = next((item for item in deps["load_resources"]() if item.get("id") == resource_id), None)
    if resource is None or deps["normalize_resource_type"](resource.get("source_type")) != "local":
        return {"ok": False, "error": "resource_not_found"}, 404

    raw_path = str(resource.get("path", "")).strip()
    if not raw_path:
        return {"ok": False, "error": "file_not_found"}, 404

    try:
        target = Path(raw_path).resolve(strict=True)
    except OSError:
        return {"ok": False, "error": "file_not_found"}, 404
    if not target.is_file() or target.suffix.casefold() not in SAFE_OPEN_EXTENSIONS:
        return {"ok": False, "error": "file_type_blocked"}, 415

    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
    except OSError:
        return {"ok": False, "error": "open_failed"}, 503
    return {"ok": True}, 200


def resource_file_path(deps: dict, resource_id: str) -> tuple[Path | None, str, int]:
    resource = next((item for item in deps["load_resources"]() if item.get("id") == resource_id), None)
    if resource is None or deps["normalize_resource_type"](resource.get("source_type")) != "local":
        return None, "resource_not_found", 404

    raw_path = str(resource.get("path", "")).strip()
    if not raw_path:
        return None, "file_not_found", 404

    try:
        target = Path(raw_path).resolve(strict=True)
    except OSError:
        return None, "file_not_found", 404
    if not target.is_file():
        return None, "file_not_found", 404
    return target, "", 200


def add_resource_tag(deps: dict, form) -> dict:
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_resource_tags"](), tag)
    if created:
        deps["save_resource_tags"](tags)
    return {"ok": True, "tag": tag, "tags": deps["load_resource_tags"](), "created": created}


def delete_resource_tag(deps: dict, form) -> tuple[dict, int]:
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_RESOURCE_TAGS"]}:
        return {"ok": False, "error": "service_tag", "tag": tag}, 400

    tags = deps["delete_tag_from_list"](deps["load_resource_tags"](), tag)
    resources = deps["load_resources"]()
    moved_resource_ids = deps["remove_tag_from_items"](resources, tag, deps["REQUIRED_RESOURCE_TAGS"])
    deps["save_resource_tags"](tags)
    deps["save_resources"](resources)
    return {
        "ok": True,
        "tag": tag,
        "fallback": deps["UNSORTED_RESOURCE_TAG"],
        "moved_resource_ids": moved_resource_ids,
        "tags": deps["load_resource_tags"](),
    }, 200


def _rename_resource_label(labels: list[str], old_label: str, new_label: str) -> tuple[list[str], str]:
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


def rename_resource_tag(deps: dict, form) -> tuple[dict, int]:
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_RESOURCE_TAGS"]}
    if not old_tag or old_tag.casefold() in required_keys:
        return {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() in required_keys:
        return {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_resource_tags"]()
    renamed_tags, canonical_new_tag = _rename_resource_label(tags, old_tag, new_tag)
    if old_tag.casefold() == canonical_new_tag.casefold():
        return {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "renamed_resource_ids": [], "tags": tags}, 200

    resources = deps["load_resources"]()
    old_key = old_tag.casefold()
    renamed_resource_ids = []
    for resource in resources:
        raw_tags = resource.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        resource["tags"] = deps["normalize_resource_item_tags"](
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        resource["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        renamed_resource_ids.append(resource.get("id", ""))

    deps["save_resource_tags"](renamed_tags)
    deps["save_resources"](resources)
    return {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_resource_ids": renamed_resource_ids,
        "tags": deps["load_resource_tags"](),
    }, 200


def add_resource_category(deps: dict, form) -> dict:
    category = form.get("category", "").strip()
    categories, created = deps["append_unique_tag"](deps["load_resource_categories"](), category)
    if created:
        deps["save_resource_categories"](categories)
    return {"ok": True, "category": category, "categories": deps["load_resource_categories"](), "created": created}


def delete_resource_category(deps: dict, form) -> tuple[dict, int]:
    category = form.get("category", "").strip()
    if not category:
        return {"ok": False, "error": "empty_category"}, 400

    categories = deps["load_resource_categories"]()
    kept_categories = deps["delete_tag_from_list"](categories, category)
    fallback = next((item for item in kept_categories if item.casefold() == RESOURCE_FALLBACK_OTHER.casefold()), None)
    fallback = fallback or (
        kept_categories[0]
        if kept_categories
        else (RESOURCE_FALLBACK_BOOKS if category.casefold() == RESOURCE_FALLBACK_OTHER.casefold() else RESOURCE_FALLBACK_OTHER)
    )
    if fallback.casefold() not in {item.casefold() for item in kept_categories}:
        kept_categories.append(fallback)

    resources = deps["load_resources"]()
    moved_resource_ids = deps["replace_item_field_value"](
        resources,
        "category",
        category,
        fallback,
        deps["datetime"].now().isoformat(timespec="seconds"),
    )
    deps["save_resource_categories"](kept_categories)
    deps["save_resources"](resources)
    return {
        "ok": True,
        "category": category,
        "fallback": fallback,
        "categories": deps["load_resource_categories"](),
        "moved_resource_ids": moved_resource_ids,
    }, 200


def rename_resource_category(deps: dict, form) -> tuple[dict, int]:
    old_category = form.get("category", "").strip()
    new_category = form.get("new_category", "").strip()
    if not old_category or not new_category:
        return {"ok": False, "error": "empty_category"}, 400

    categories = deps["load_resource_categories"]()
    renamed_categories, canonical_new_category = _rename_resource_label(categories, old_category, new_category)
    if old_category.casefold() == canonical_new_category.casefold():
        return {"ok": True, "category": old_category, "new_category": canonical_new_category, "moved_resource_ids": [], "categories": categories}, 200

    resources = deps["load_resources"]()
    moved_resource_ids = deps["replace_item_field_value"](
        resources,
        "category",
        old_category,
        canonical_new_category,
        deps["datetime"].now().isoformat(timespec="seconds"),
    )
    deps["save_resource_categories"](renamed_categories)
    deps["save_resources"](resources)
    return {
        "ok": True,
        "category": old_category,
        "new_category": canonical_new_category,
        "categories": deps["load_resource_categories"](),
        "moved_resource_ids": moved_resource_ids,
    }, 200


def pick_resource_file(deps: dict, form) -> tuple[dict, int]:
    try:
        selected = deps["choose_windows_file"]("", RESOURCE_PICK_FILE_TITLE)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return {"ok": False, "error": "picker_failed"}, 503
    if not selected:
        return {"ok": True, "cancelled": True}, 200
    capability_id, display_name = deps["issue_file_capability"](selected)
    return {
        "ok": True,
        "capability_id": capability_id,
        "display_name": display_name,
    }, 200


def update_resource(deps: dict, form, resource_id: str) -> None:
    resources = deps["load_resources"]()
    known_tags = deps["load_resource_tags"]()
    known_categories = deps["load_resource_categories"]()
    for item in resources:
        if item.get("id") != resource_id:
            continue
        previous_source_type = deps["normalize_resource_type"](item.get("source_type", "web"))
        source_type = deps["normalize_resource_type"](form.get("source_type", item.get("source_type", "web")))
        item["source_type"] = source_type
        item["title"] = form.get("title", "").strip() or item.get("title", RESOURCE_FALLBACK_TITLE)
        item["description"] = form.get("description", "").strip()
        item["category"] = deps["normalize_resource_category"](form.get("category", item.get("category", "")))
        item["tags"] = deps["normalize_resource_item_tags"](form.get("tags", ""))
        if source_type == "local":
            capability_id = form.get("file_capability", "").strip()
            if capability_id:
                item["path"] = str(deps["resolve_file_capability"](capability_id))
            elif previous_source_type != "local" or not str(item.get("path", "")).strip():
                raise ValidationError("Choose a local file with the native picker.")
            item.pop("url", None)
        else:
            try:
                item["url"] = ExternalHttpUrl.parse(form.get("url", "")).value
            except UnsafeUrl as exc:
                raise ValidationError("Only a valid http or https resource URL is allowed.") from exc
            item.pop("path", None)
        if item["category"].casefold() not in {category.casefold() for category in known_categories}:
            known_categories.append(item["category"])
        for tag in item["tags"]:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        item["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        break
    deps["save_resource_tags"](known_tags)
    deps["save_resource_categories"](known_categories)
    deps["save_resources"](resources)
