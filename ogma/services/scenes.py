SCENES_TEMPLATE_TEXT = {
    "media_title": "\u0420\u0430\u0437\u0434\u0430\u0442",
    "media_title_lower": "\u0440\u0430\u0437\u0434\u0430\u0442\u0430",
    "media_title_accusative": "\u0440\u0430\u0437\u0434\u0430\u0442",
    "media_kicker": "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b \u0434\u043b\u044f \u0438\u0433\u0440\u043e\u043a\u043e\u0432",
    "media_hero_text": (
        "\u0417\u0430\u0433\u0440\u0443\u0436\u0430\u0439\u0442\u0435 \u0430\u0440\u0442\u044b, "
        "\u043f\u043e\u0440\u0442\u0440\u0435\u0442\u044b, handouts, \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438 "
        "\u0438 \u043b\u044e\u0431\u044b\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f, "
        "\u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u043d\u0443\u0436\u043d\u043e \u0431\u044b\u0441\u0442\u0440\u043e "
        "\u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0438\u043b\u0438 \u0432\u044b\u0434\u0430\u0442\u044c "
        "\u0438\u0433\u0440\u043e\u043a\u0430\u043c."
    ),
    "upload_strong": "\u041f\u0435\u0440\u0435\u0442\u0430\u0449\u0438\u0442\u0435 \u0440\u0430\u0437\u0434\u0430\u0442 \u0441\u044e\u0434\u0430",
    "upload_button": "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0440\u0430\u0437\u0434\u0430\u0442",
    "delete_all_text": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u0435\u0441\u044c \u0440\u0430\u0437\u0434\u0430\u0442",
    "empty_title": "\u0420\u0430\u0437\u0434\u0430\u0442\u0430 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.",
    "empty_filtered_title": "\u041d\u0435\u0442 \u0440\u0430\u0437\u0434\u0430\u0442\u0430 \u0441 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u043c\u0438 \u0442\u0435\u0433\u0430\u043c\u0438.",
}


def scenes_page_context(deps: dict, query: dict, is_fetch: bool) -> tuple[str, dict]:
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    search = str(query.get("q", "")).strip()
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_MAPS_PER_PAGE"], type=int)
    if per_page not in deps["MAPS_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_MAPS_PER_PAGE"]
    all_scenes = deps["prepare_scenes"]()
    filtered_scenes = deps["filter_maps_by_tags"](all_scenes, selected_tags, excluded_tags)
    filtered_scenes = deps["filter_media_by_search"](filtered_scenes, search)
    scenes, pagination = deps["paginate_items"](filtered_scenes, page, per_page)
    template = "_maps_dynamic.html" if is_fetch else "maps.html"
    return template, {
        "campaign": None,
        "maps": scenes,
        "tags": deps["visible_scene_tags"](all_scenes),
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "search": search,
        "pagination": pagination,
        "per_page_options": deps["MAPS_PER_PAGE_OPTIONS"],
        "all_maps_count": len(all_scenes),
        "required_tags": deps["REQUIRED_SCENE_TAGS"],
        "scope": "shared",
        "campaign_slug": "",
        "page_endpoint": "scenes_page",
        "upload_endpoint": "upload_scenes",
        "delete_endpoint": "delete_scenes",
        "delete_all_endpoint": "delete_all_scenes_route",
        "add_tag_endpoint": "add_scene_tag",
        "delete_tag_endpoint": "delete_scene_tag",
        "rename_tag_endpoint": "rename_scene_tag",
        "reorder_tag_endpoint": "reorder_scene_tags",
        "update_endpoint": "update_scene",
        "copy_image_endpoint": "copy_scene_image",
        "upload_field_name": "scenes",
        "upload_input_id": "scene-upload",
        **SCENES_TEMPLATE_TEXT,
    }


def upload_scenes(deps: dict, form, files) -> None:
    deps["save_uploaded_scenes"](
        files.getlist("scenes"),
        form.get("batch_tags", ""),
        form.get("single_title", "").strip(),
    )
    if deps["load_settings"]()["foundry"]["enabled"]:
        deps["ensure_foundry_junctions"]()


def delete_scenes(deps: dict, form) -> None:
    scene_ids = {scene_id for scene_id in form.getlist("map_ids") if scene_id}
    if scene_ids:
        deps["delete_scenes_by_ids"](scene_ids)


def copy_scene_image_data(deps: dict, map_id: str):
    scene = deps["find_scene_by_id"](map_id)
    if scene is None:
        return None, "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", 404
    image_path = deps["scenes_directory"]() / scene["filename"]
    return (image_path, deps["scene_url"](scene)), "", 200


def add_scene_tag(deps: dict, form) -> dict:
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_scene_tags"](), tag)
    if created:
        deps["save_scene_tags"](tags)
    return {"ok": True, "tag": tag, "tags": deps["load_scene_tags"](), "created": created}


def delete_scene_tag(deps: dict, form) -> tuple[dict, int]:
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_SCENE_TAGS"]}:
        return {"ok": False, "error": "service_tag", "tag": tag, "fallback": deps["UNSORTED_SCENE_TAG"]}, 400
    tags = deps["delete_tag_from_list"](deps["load_scene_tags"](), tag)
    scenes = deps["load_scenes"]()
    moved_scene_ids = deps["remove_tag_from_items"](scenes, tag, deps["REQUIRED_SCENE_TAGS"])
    deps["save_scene_tags"](tags)
    deps["save_scenes"](scenes)
    return {
        "ok": True,
        "tag": tag,
        "fallback": deps["UNSORTED_SCENE_TAG"],
        "moved_map_ids": moved_scene_ids,
        "tags": deps["load_scene_tags"](),
    }, 200


def reorder_scene_tags(deps: dict, payload: dict) -> dict:
    ordered = deps["reorder_existing_tags"](
        payload.get("tags", []),
        deps["load_scene_tags"](),
        deps["REQUIRED_SCENE_TAGS"],
    )
    deps["save_scene_tags"](ordered)
    return {"ok": True, "tags": deps["load_scene_tags"]()}


def rename_scene_tag(deps: dict, form) -> tuple[dict, int]:
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_SCENE_TAGS"]}
    if not old_tag or old_tag.casefold() in required_keys:
        return {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() in required_keys:
        return {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_scene_tags"]()
    old_key = old_tag.casefold()
    new_key = new_tag.casefold()
    if not any(tag.casefold() == old_key for tag in tags):
        return {"ok": False, "error": "tag_not_found", "tag": old_tag}, 404

    canonical_new_tag = next((tag for tag in tags if tag.casefold() == new_key), new_tag)
    if old_key == canonical_new_tag.casefold():
        return {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "renamed_map_ids": [], "tags": tags}, 200

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

    scenes = deps["load_scenes"]()
    renamed_scene_ids = []
    for item in scenes:
        raw_tags = item.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        item["tags"] = deps["normalize_scene_item_tags"](
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        renamed_scene_ids.append(item.get("id", ""))

    deps["save_scene_tags"](renamed_tags)
    deps["save_scenes"](scenes)
    return {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_map_ids": [item for item in renamed_scene_ids if item],
        "tags": deps["load_scene_tags"](),
    }, 200


def update_scene(deps: dict, form, map_id: str) -> tuple[dict, int]:
    scenes = deps["load_scenes"]()
    known_tags = deps["load_scene_tags"]()
    updated_scene = None
    for item in scenes:
        if item["id"] != map_id:
            continue
        item["title"] = form.get("title", "").strip() or item["title"]
        item["tags"] = deps["normalize_scene_item_tags"](form.get("tags", ""))
        for tag in item["tags"]:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        item["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        updated_scene = item
        break
    deps["save_scene_tags"](known_tags)
    deps["save_scenes"](scenes)
    if updated_scene is None:
        return {"ok": False, "error": "scene_not_found"}, 404
    enriched_scene = updated_scene.copy()
    enriched_scene["url"] = deps["scene_url"](updated_scene)
    enriched_scene["foundry_path"] = deps["scene_foundry_path"](updated_scene)
    return {"ok": True, "map": enriched_scene}, 200
