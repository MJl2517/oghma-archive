CHARACTER_CAMPAIGN_NOT_FOUND = "\u041a\u0430\u043c\u043f\u0435\u0439\u043d \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d."
CHARACTER_NOT_FOUND = "NPC \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d."
CHARACTER_IMAGE_NOT_FOUND = "\u0424\u0430\u0439\u043b \u0430\u0440\u0442\u0430 NPC \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d."
CHARACTER_NAME_FALLBACK = "\u0411\u0435\u0437 \u0438\u043c\u0435\u043d\u0438"
CHARACTER_GENDER_FALLBACK = "\u0418\u043d\u043e\u0435"
CHARACTER_ATTITUDE_FALLBACK = "\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e"


def characters_page_context(deps: dict, query: dict) -> tuple[str, dict]:
    campaign_slug = query.get("campaign", "").strip()
    campaign = deps["get_campaign"](campaign_slug) if campaign_slug else None
    if campaign is None:
        return "redirect_index", {}

    selected_groups = deps["normalize_tags"](query.getlist("tag") or query.getlist("group"))
    excluded_groups = deps["normalize_tags"](query.getlist("exclude_tag") or query.getlist("exclude_group"))
    search = query.get("q", "").strip()
    open_character_id = query.get("character", "").strip()
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_MAPS_PER_PAGE"], type=int)
    if per_page not in deps["MAPS_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_MAPS_PER_PAGE"]
    all_characters = deps["prepare_characters"](campaign_slug)
    filtered_characters = deps["filter_characters"](all_characters, selected_groups, search, excluded_groups)
    if open_character_id:
        for index, character in enumerate(filtered_characters):
            if character.get("id") == open_character_id:
                page = index // per_page + 1
                break
    characters, pagination = deps["paginate_items"](filtered_characters, page, per_page)
    visible_tags = deps["visible_character_tags"](campaign_slug, all_characters)
    return "render", {
        "campaign": campaign,
        "characters": characters,
        "all_characters": characters,
        "groups": visible_tags,
        "selected_groups": selected_groups,
        "excluded_groups": excluded_groups,
        "tags": visible_tags,
        "selected_tags": selected_groups,
        "excluded_tags": excluded_groups,
        "search": search,
        "pagination": pagination,
        "per_page_options": deps["MAPS_PER_PAGE_OPTIONS"],
        "all_characters_count": len(all_characters),
        "filtered_characters_count": len(filtered_characters),
        "open_character_id": open_character_id,
        "required_groups": deps["REQUIRED_CHARACTER_TAGS"],
        "required_tags": deps["REQUIRED_CHARACTER_TAGS"],
        "genders": deps["CHARACTER_GENDERS"],
        "nav_sections": deps["CAMPAIGN_SECTIONS"],
    }


def upload_characters(deps: dict, form, files) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    batch_groups = form.get("batch_tags", "") or form.get("batch_groups", "")
    single_title = form.get("single_title", "").strip()
    deps["save_uploaded_characters"](files.getlist("characters"), campaign_slug, batch_groups, single_title)
    return "redirect", campaign_slug


def delete_characters(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    character_ids = {character_id for character_id in form.getlist("character_ids") if character_id}
    if character_ids:
        deps["delete_characters_by_ids"](campaign_slug, character_ids)
    return "redirect", campaign_slug


def delete_all_characters(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    deps["delete_all_characters"](campaign_slug)
    return "redirect", campaign_slug


def add_character_group(deps: dict, form) -> tuple[str, str, dict]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}
    group = (form.get("tag") or form.get("group", "")).strip()
    groups, created = deps["append_unique_tag"](deps["load_character_tags"](campaign_slug), group)
    if created:
        deps["save_character_tags"](campaign_slug, groups)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": group,
        "tags": deps["load_character_tags"](campaign_slug),
        "created": created,
    }


def delete_character_group(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    group = (form.get("tag") or form.get("group", "")).strip()
    if not group or group.casefold() in {item.casefold() for item in deps["REQUIRED_CHARACTER_TAGS"]}:
        return "error", campaign_slug, {
            "ok": False,
            "error": "service_tag",
            "tag": group,
            "fallback": deps["UNSORTED_CHARACTER_TAG"],
        }, 400

    groups = deps["delete_tag_from_list"](deps["load_character_tags"](campaign_slug), group)
    characters = deps["load_characters"](campaign_slug)
    moved_character_ids = []
    for item in characters:
        had_tag = any(tag.casefold() == group.casefold() for tag in deps["character_tags"](item))
        item["tags"] = [tag for tag in deps["character_tags"](item) if tag.casefold() != group.casefold()]
        if not item["tags"]:
            item["tags"] = deps["REQUIRED_CHARACTER_TAGS"][:]
        if had_tag:
            moved_character_ids.append(item.get("id"))
        item.pop("groups", None)
        item.pop("category", None)
    deps["save_character_tags"](campaign_slug, groups)
    deps["save_characters"](campaign_slug, characters)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": group,
        "fallback": deps["UNSORTED_CHARACTER_TAG"],
        "moved_character_ids": [character_id for character_id in moved_character_ids if character_id],
        "tags": deps["load_character_tags"](campaign_slug),
    }, 200


def rename_character_group(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404

    old_group = (form.get("old_tag") or form.get("old_group", "")).strip()
    new_group = (form.get("new_tag") or form.get("new_group", "")).strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_CHARACTER_TAGS"]}
    if not old_group or not new_group or old_group.casefold() in required_keys or new_group.casefold() in required_keys:
        return "error", campaign_slug, {"ok": False, "error": "invalid_tag"}, 400

    old_key = old_group.casefold()
    new_key = new_group.casefold()
    groups = deps["load_character_tags"](campaign_slug)
    if not any(group.casefold() == old_key for group in groups):
        return "error", campaign_slug, {"ok": False, "error": "tag_not_found", "tag": old_group}, 404

    canonical_new_group = next((group for group in groups if group.casefold() == new_key), new_group)
    if old_key == new_key:
        return "ok", campaign_slug, {
            "ok": True,
            "tag": old_group,
            "new_tag": canonical_new_group,
            "renamed_character_ids": [],
            "tags": groups,
        }, 200

    renamed_groups = []
    has_new_group = any(group.casefold() == new_key for group in groups)
    for group in groups:
        group_key = group.casefold()
        if group_key == old_key:
            if not has_new_group and all(item.casefold() != new_key for item in renamed_groups):
                renamed_groups.append(canonical_new_group)
            continue
        if group_key != new_key or all(item.casefold() != new_key for item in renamed_groups):
            renamed_groups.append(group)
    if not has_new_group and all(item.casefold() != new_key for item in renamed_groups):
        renamed_groups.append(canonical_new_group)

    characters = deps["load_characters"](campaign_slug)
    renamed_character_ids = []
    for item in characters:
        raw_tags = deps["character_tags"](item)
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        item["tags"] = deps["normalize_character_item_tags"](
            [canonical_new_group if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        item.pop("groups", None)
        item.pop("category", None)
        renamed_character_ids.append(item.get("id", ""))

    deps["save_character_tags"](campaign_slug, renamed_groups)
    deps["save_characters"](campaign_slug, characters)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": old_group,
        "new_tag": canonical_new_group,
        "renamed_character_ids": [item for item in renamed_character_ids if item],
        "tags": deps["load_character_tags"](campaign_slug),
    }, 200


def reorder_character_groups(deps: dict, form, payload: dict) -> tuple[dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if not campaign_slug:
        campaign_slug = payload.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return {"ok": False, "error": "campaign_not_found"}, 404
    ordered = deps["reorder_existing_tags"](
        payload.get("tags", []),
        deps["load_character_tags"](campaign_slug),
        deps["REQUIRED_CHARACTER_TAGS"],
    )
    deps["save_character_tags"](campaign_slug, ordered)
    return {"ok": True, "tags": deps["load_character_tags"](campaign_slug)}, 200


def copy_character_image_data(deps: dict, form, character_id: str):
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "error", {"ok": False, "error": CHARACTER_CAMPAIGN_NOT_FOUND}, 404
    character = deps["find_character_by_id"](campaign_slug, character_id)
    if character is None:
        return "error", {"ok": False, "error": CHARACTER_NOT_FOUND}, 404
    image_path = deps["characters_directory"](campaign_slug) / character["filename"]
    return "copy", {
        "image_path": image_path,
        "missing_message": CHARACTER_IMAGE_NOT_FOUND,
        "clipboard_image_url": deps["character_url"](character, campaign_slug),
    }, 200


def update_character(deps: dict, form, character_id: str) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    characters = deps["load_characters"](campaign_slug)
    known_groups = deps["load_character_tags"](campaign_slug)
    gender = form.get("gender", "").strip()
    updated_character = None
    for item in characters:
        if item["id"] != character_id:
            continue
        item["name"] = form.get("name", "").strip() or item.get("name") or CHARACTER_NAME_FALLBACK
        item["age"] = form.get("age", "").strip()
        item["gender"] = gender if gender in deps["CHARACTER_GENDERS"] else CHARACTER_GENDER_FALLBACK
        item["race"] = form.get("race", "").strip()
        item["notes"] = form.get("notes", "").strip()
        item["tags"] = deps["normalize_character_item_tags"](form.get("tags", ""))
        item.pop("category", None)
        item.pop("groups", None)
        for tag in item["tags"]:
            if tag.casefold() not in {known_group.casefold() for known_group in known_groups}:
                known_groups.append(tag)
        item["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        updated_character = item
        break
    if updated_character is None:
        return "not_found", campaign_slug, {"ok": False, "error": "character_not_found"}, 404

    deps["save_character_tags"](campaign_slug, known_groups)
    deps["save_characters"](campaign_slug, characters)
    prepared = {
        **updated_character,
        "tags": deps["character_tags"](updated_character),
        "foundry_path": deps["character_foundry_path"](updated_character, campaign_slug),
        "url": deps["character_url"](updated_character, campaign_slug),
    }
    return "ok", campaign_slug, {
        "ok": True,
        "character": prepared,
        "tags": deps["load_character_tags"](campaign_slug),
    }, 200


def character_image_directory(deps: dict, campaign_slug: str):
    if deps["get_campaign"](campaign_slug) is None:
        return None
    return deps["characters_directory"](campaign_slug)
