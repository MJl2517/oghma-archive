MAPS_TEMPLATE_TEXT = {
    "media_title": "\u041a\u0430\u0440\u0442\u044b",
    "media_title_lower": "\u043a\u0430\u0440\u0442",
    "media_title_accusative": "\u043a\u0430\u0440\u0442\u044b",
    "media_kicker": "\u041e\u0431\u0449\u0438\u0435 \u043a\u0430\u0440\u0442\u044b",
    "media_hero_text": (
        "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0439\u0442\u0435 \u043a\u0430\u0440\u0442\u044b "
        "\u043f\u0430\u0447\u043a\u043e\u0439, \u0444\u0438\u043b\u044c\u0442\u0440\u0443\u0439\u0442\u0435 "
        "\u043f\u043e \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u0438\u043c \u0442\u0435\u0433\u0430\u043c "
        "\u043e\u0434\u043d\u043e\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u0438 \u043a\u043b\u0438\u043a\u043e\u043c "
        "\u043a\u043e\u043f\u0438\u0440\u0443\u0439\u0442\u0435 \u043f\u0443\u0442\u044c \u043a \u0444\u0430\u0439\u043b\u0443 "
        "\u0434\u043b\u044f Foundry VTT. \u041d\u043e\u0432\u044b\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f "
        "\u043f\u043e\u043f\u0430\u0434\u0430\u044e\u0442 \u0432 \u0442\u0435\u0433 "
        "\u201c\u041d\u0435\u043e\u0442\u0441\u043e\u0440\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0435\u201d."
    ),
    "upload_strong": "\u041f\u0435\u0440\u0435\u0442\u0430\u0449\u0438\u0442\u0435 \u043a\u0430\u0440\u0442\u044b \u0441\u044e\u0434\u0430",
    "upload_button": "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043a\u0430\u0440\u0442\u044b",
    "delete_all_text": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u0441\u0435 \u043a\u0430\u0440\u0442\u044b",
    "empty_title": "\u041a\u0430\u0440\u0442 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.",
    "empty_filtered_title": "\u041d\u0435\u0442 \u043a\u0430\u0440\u0442 \u0441 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u043c\u0438 \u0442\u0435\u0433\u0430\u043c\u0438.",
}


def maps_page_context(deps: dict, query: dict, is_fetch: bool) -> tuple[str, dict]:
    campaign_slug = str(query.get("campaign", "")).strip()
    if campaign_slug:
        return "redirect_without_campaign", {"campaign_slug": campaign_slug}

    scope = "shared"
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    search = str(query.get("q", "")).strip()
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_MAPS_PER_PAGE"], type=int)
    if per_page not in deps["MAPS_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_MAPS_PER_PAGE"]

    all_maps = deps["prepare_maps"](scope, "")
    filtered_maps = deps["filter_maps_by_tags"](all_maps, selected_tags, excluded_tags)
    filtered_maps = deps["filter_media_by_search"](filtered_maps, search)
    maps, pagination = deps["paginate_items"](filtered_maps, page, per_page)
    template = "_maps_dynamic.html" if is_fetch else "maps.html"
    context = {
        "campaign": None,
        "maps": maps,
        "tags": deps["visible_map_tags"](scope, all_maps, ""),
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "search": search,
        "pagination": pagination,
        "per_page_options": deps["MAPS_PER_PAGE_OPTIONS"],
        "all_maps_count": len(all_maps),
        "required_tags": deps["REQUIRED_MAP_TAGS"],
        "scope": scope,
        "campaign_slug": "",
        "page_endpoint": "maps_page",
        "upload_endpoint": "upload_maps",
        "delete_endpoint": "delete_maps",
        "delete_all_endpoint": "delete_all_maps_route",
        "add_tag_endpoint": "add_map_tag",
        "delete_tag_endpoint": "delete_map_tag",
        "rename_tag_endpoint": "rename_map_tag",
        "update_endpoint": "update_map",
        "copy_image_endpoint": "copy_map_image",
        "upload_field_name": "maps",
        "upload_input_id": "map-upload",
        **MAPS_TEMPLATE_TEXT,
    }
    return template, context


def upload_maps(deps: dict, form, files) -> tuple[str, str]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    deps["save_uploaded_maps"](
        files.getlist("maps"),
        scope,
        campaign_slug,
        form.get("batch_tags", ""),
        form.get("single_title", "").strip(),
    )
    return scope, campaign_slug


def delete_maps(deps: dict, form) -> tuple[str, str]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    map_ids = {map_id for map_id in form.getlist("map_ids") if map_id}
    if map_ids:
        deps["delete_maps_by_ids"](scope, campaign_slug, map_ids)
    return scope, campaign_slug


def delete_all_maps(deps: dict, form) -> tuple[str, str]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    deps["delete_all_maps"](scope, campaign_slug)
    return scope, campaign_slug


def copy_map_image_data(deps: dict, form, map_id: str):
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return None, "\u041a\u0430\u043c\u043f\u0435\u0439\u043d \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", 404
    map_item = deps["find_map_by_id"](scope, campaign_slug, map_id)
    if map_item is None:
        return None, "\u041a\u0430\u0440\u0442\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430.", 404
    image_path = deps["maps_directory"](scope, campaign_slug) / map_item["filename"]
    image_url = deps["map_url"](map_item, scope, campaign_slug)
    return (image_path, image_url), "", 200


def add_map_tag(deps: dict, form) -> tuple[str, str, dict] | tuple[str, str, None]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, None
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_map_tags"](scope, campaign_slug), tag)
    if created:
        deps["save_map_tags"](scope, tags, campaign_slug)
    payload = {"ok": True, "tag": tag, "tags": deps["load_map_tags"](scope, campaign_slug), "created": created}
    return scope, campaign_slug, payload


def delete_map_tag(deps: dict, form) -> tuple[str, str, dict, int]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_MAP_TAGS"]}:
        return scope, campaign_slug, {"ok": False, "error": "service_tag", "tag": tag, "fallback": deps["UNSORTED_MAP_TAG"]}, 400

    tags = deps["delete_tag_from_list"](deps["load_map_tags"](scope, campaign_slug), tag)
    maps = deps["load_maps"](scope, campaign_slug)
    moved_map_ids = deps["remove_tag_from_items"](maps, tag, deps["REQUIRED_MAP_TAGS"])
    deps["save_map_tags"](scope, tags, campaign_slug)
    deps["save_maps"](scope, maps, campaign_slug)
    return scope, campaign_slug, {
        "ok": True,
        "tag": tag,
        "fallback": deps["UNSORTED_MAP_TAG"],
        "moved_map_ids": moved_map_ids,
        "tags": deps["load_map_tags"](scope, campaign_slug),
    }, 200


def rename_map_tag(deps: dict, form) -> tuple[str, str, dict, int]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_MAP_TAGS"]}
    if not old_tag or old_tag.casefold() in required_keys:
        return scope, campaign_slug, {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() in required_keys:
        return scope, campaign_slug, {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_map_tags"](scope, campaign_slug)
    old_key = old_tag.casefold()
    new_key = new_tag.casefold()
    canonical_new_tag = next((tag for tag in tags if tag.casefold() == new_key), new_tag)
    if old_key == canonical_new_tag.casefold():
        return scope, campaign_slug, {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "renamed_map_ids": [], "tags": tags}, 200

    renamed_tags = []
    has_new_tag = False
    for tag in tags:
        tag_key = tag.casefold()
        if tag_key == new_key:
            has_new_tag = True
        if tag_key == old_key:
            if not has_new_tag and all(item.casefold() != new_key for item in renamed_tags):
                renamed_tags.append(canonical_new_tag)
                has_new_tag = True
            continue
        if tag_key != new_key or all(item.casefold() != new_key for item in renamed_tags):
            renamed_tags.append(tag)
    if not has_new_tag and all(item.casefold() != new_key for item in renamed_tags):
        renamed_tags.append(canonical_new_tag)

    maps = deps["load_maps"](scope, campaign_slug)
    renamed_map_ids = []
    for item in maps:
        raw_tags = item.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        item["tags"] = deps["normalize_map_item_tags"](
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        renamed_map_ids.append(item.get("id", ""))

    deps["save_map_tags"](scope, renamed_tags, campaign_slug)
    deps["save_maps"](scope, maps, campaign_slug)
    return scope, campaign_slug, {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_map_ids": renamed_map_ids,
        "tags": deps["load_map_tags"](scope, campaign_slug),
    }, 200


def update_map(deps: dict, form, map_id: str) -> tuple[str, str, dict, int]:
    scope = form.get("scope", "shared")
    campaign_slug = form.get("campaign_slug", "").strip()
    if scope == "campaign" and deps["get_campaign"](campaign_slug) is None:
        return scope, campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404
    maps = deps["load_maps"](scope, campaign_slug)
    known_tags = deps["load_map_tags"](scope, campaign_slug)
    updated_map = None
    for item in maps:
        if item["id"] != map_id:
            continue
        item["title"] = form.get("title", "").strip() or item["title"]
        item["tags"] = deps["normalize_map_item_tags"](form.get("tags", ""))
        for tag in item["tags"]:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        item["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        updated_map = item
        break
    deps["save_map_tags"](scope, known_tags, campaign_slug)
    deps["save_maps"](scope, maps, campaign_slug)
    if updated_map is None:
        return scope, campaign_slug, {"ok": False, "error": "map_not_found"}, 404
    enriched_map = updated_map.copy()
    enriched_map["url"] = deps["map_url"](updated_map, scope, campaign_slug)
    enriched_map["foundry_path"] = deps["map_foundry_path"](updated_map, scope, campaign_slug)
    return scope, campaign_slug, {"ok": True, "map": enriched_map}, 200
