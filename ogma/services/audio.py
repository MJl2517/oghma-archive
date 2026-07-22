AUDIO_TITLE_FALLBACK = "YouTube \u0442\u0440\u0435\u043a"
AUDIO_ITEM_FALLBACK = "\u0422\u0440\u0435\u043a"
YOUTUBE_TITLE_REQUIRED = "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0442\u0440\u0435\u043a\u0430. \u0423\u043a\u0430\u0436\u0438\u0442\u0435 \u0435\u0433\u043e \u0432\u0440\u0443\u0447\u043d\u0443\u044e."


def audio_page_context(deps: dict, query: dict) -> dict:
    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    selected_category = query.get("category", "").strip()
    search = query.get("q", "").strip()
    open_track_id = query.get("track", "").strip()
    page = query.get("page", 1, type=int)
    per_page = query.get("per_page", deps["DEFAULT_AUDIO_PER_PAGE"], type=int)
    if per_page not in deps["AUDIO_PER_PAGE_OPTIONS"]:
        per_page = deps["DEFAULT_AUDIO_PER_PAGE"]
    tracks = deps["prepare_audio_tracks"]()
    categories = deps["load_audio_categories"]()

    if selected_category:
        tracks = [item for item in tracks if item.get("category", "").casefold() == selected_category.casefold()]
    for tag in selected_tags:
        tracks = [item for item in tracks if any(item_tag.casefold() == tag.casefold() for item_tag in item.get("tags", []))]
    for tag in excluded_tags:
        tracks = [item for item in tracks if all(item_tag.casefold() != tag.casefold() for item_tag in item.get("tags", []))]
    if len(search) >= 3:
        query_text = search.casefold()
        tracks = [
            item
            for item in tracks
            if query_text
            in " ".join([item.get("title", ""), item.get("url", ""), item.get("category", ""), " ".join(item.get("tags", []))]).casefold()
        ]

    tracks.sort(key=lambda item: (item.get("category", ""), item.get("title", "").casefold()))
    filtered_tracks_count = len(tracks)
    if open_track_id:
        for index, track in enumerate(tracks):
            if track.get("id") == open_track_id:
                page = index // per_page + 1
                break
    tracks, pagination = deps["paginate_items"](tracks, page, per_page)
    all_tracks = deps["prepare_audio_tracks"]()
    return {
        "tracks": tracks,
        "all_tracks_count": len(all_tracks),
        "filtered_tracks_count": filtered_tracks_count,
        "pagination": pagination,
        "per_page_options": deps["AUDIO_PER_PAGE_OPTIONS"],
        "tags": deps["visible_audio_tags"](all_tracks),
        "categories": categories,
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "selected_category": selected_category,
        "open_track_id": open_track_id,
        "search": search,
        "required_tags": deps["REQUIRED_AUDIO_TAGS"],
        "nav_sections": deps["GLOBAL_SECTIONS"],
    }


def upload_audio(deps: dict, form, files) -> None:
    deps["save_uploaded_audio"](
        files.getlist("audio"),
        form.get("category", deps["DEFAULT_AUDIO_CATEGORIES"][0]),
        form.get("batch_tags", ""),
    )


def create_audio_link(deps: dict, form) -> tuple[dict, int]:
    url = form.get("url", "").strip()
    if not deps["is_youtube_url"](url):
        return {"ok": False, "error": "youtube_url_required", "field": "url"}, 400
    tracks = deps["load_audio_tracks"]()
    tags = deps["normalize_audio_item_tags"](form.get("tags", "") or form.get("batch_tags", ""))
    category = deps["normalize_audio_category"](form.get("category", deps["DEFAULT_AUDIO_CATEGORIES"][0]))
    metadata = deps["fetch_youtube_metadata"](url)
    title = form.get("title", "").strip()
    if not title:
        title = str(metadata.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "youtube_title_required", "field": "title", "message": YOUTUBE_TITLE_REQUIRED}, 422
    thumbnail_filename = deps["save_youtube_thumbnail"](url, str(metadata.get("thumbnail_url") or ""))
    tracks.append(
        {
            "id": deps["uuid4"]().hex,
            "source_type": "youtube",
            "url": url,
            "title": title,
            "category": category,
            "tags": tags,
            "thumbnail_filename": thumbnail_filename,
            "created_at": deps["datetime"].now().isoformat(timespec="seconds"),
        }
    )
    known_tags = deps["load_audio_tags"]()
    for tag in tags:
        if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
            known_tags.append(tag)
    categories = deps["load_audio_categories"]()
    if category.casefold() not in {item.casefold() for item in categories}:
        categories.append(category)
    deps["save_audio_tags"](known_tags)
    deps["save_audio_categories"](categories)
    deps["save_audio_tracks"](tracks)
    return {"ok": True}, 200


def delete_audio(deps: dict, form) -> None:
    track_ids = {track_id for track_id in form.getlist("track_ids") if track_id}
    if track_ids:
        deps["delete_audio_by_ids"](track_ids)


def add_audio_tag(deps: dict, form) -> dict:
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_audio_tags"](), tag)
    if created:
        deps["save_audio_tags"](tags)
    return {"ok": True, "tag": tag, "tags": deps["load_audio_tags"](), "created": created}


def delete_audio_tag(deps: dict, form) -> tuple[dict, int]:
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_AUDIO_TAGS"]}:
        return {"ok": False, "error": "service_tag", "tag": tag, "fallback": deps["UNSORTED_AUDIO_TAG"]}, 400
    tags = deps["delete_tag_from_list"](deps["load_audio_tags"](), tag)
    tracks = deps["load_audio_tracks"]()
    moved_track_ids = deps["remove_tag_from_items"](tracks, tag, deps["REQUIRED_AUDIO_TAGS"])
    deps["save_audio_tags"](tags)
    deps["save_audio_tracks"](tracks)
    return {
        "ok": True,
        "tag": tag,
        "fallback": deps["UNSORTED_AUDIO_TAG"],
        "moved_track_ids": moved_track_ids,
        "tags": deps["load_audio_tags"](),
    }, 200


def rename_audio_tag(deps: dict, form) -> tuple[dict, int]:
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_AUDIO_TAGS"]}
    if not old_tag or old_tag.casefold() in required_keys:
        return {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() in required_keys:
        return {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_audio_tags"]()
    old_key = old_tag.casefold()
    new_key = new_tag.casefold()
    canonical_new_tag = next((tag for tag in tags if tag.casefold() == new_key), new_tag)
    if old_key == canonical_new_tag.casefold():
        return {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "renamed_track_ids": [], "tags": tags}, 200

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

    tracks = deps["load_audio_tracks"]()
    renamed_track_ids = []
    for track in tracks:
        raw_tags = track.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        track["tags"] = deps["normalize_audio_item_tags"](
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        renamed_track_ids.append(track.get("id", ""))

    deps["save_audio_tags"](renamed_tags)
    deps["save_audio_tracks"](tracks)
    return {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_track_ids": renamed_track_ids,
        "tags": deps["load_audio_tags"](),
    }, 200


def add_audio_category(deps: dict, form) -> dict:
    category = form.get("category", "").strip()
    categories, created = deps["append_unique_tag"](deps["load_audio_categories"](), category)
    if created:
        deps["save_audio_categories"](categories)
    return {"ok": True, "category": category, "categories": deps["load_audio_categories"](), "created": created}


def delete_audio_category(deps: dict, form) -> tuple[dict, int]:
    category = form.get("category", "").strip()
    if not category:
        return {"ok": False, "error": "empty_category"}, 400
    categories = deps["load_audio_categories"]()
    remaining = deps["delete_tag_from_list"](categories, category)
    fallback = remaining[0] if remaining else deps["DEFAULT_AUDIO_CATEGORIES"][-1]
    if not remaining:
        remaining = [fallback]
    tracks = deps["load_audio_tracks"]()
    moved_track_ids = deps["replace_item_field_value"](tracks, "category", category, fallback)
    deps["save_audio_categories"](remaining)
    deps["save_audio_tracks"](tracks)
    return {
        "ok": True,
        "category": category,
        "fallback": fallback,
        "categories": deps["load_audio_categories"](),
        "moved_track_ids": moved_track_ids,
    }, 200


def rename_audio_category(deps: dict, form) -> tuple[dict, int]:
    old_category = form.get("category", "").strip()
    new_category = form.get("new_category", "").strip()
    if not old_category or not new_category:
        return {"ok": False, "error": "empty_category"}, 400

    categories = deps["load_audio_categories"]()
    old_key = old_category.casefold()
    new_key = new_category.casefold()
    canonical_new_category = next((category for category in categories if category.casefold() == new_key), new_category)
    if old_key == canonical_new_category.casefold():
        return {"ok": True, "category": old_category, "new_category": canonical_new_category, "moved_track_ids": [], "categories": categories}, 200

    renamed_categories = []
    has_new_category = False
    for category in categories:
        category_key = category.casefold()
        if category_key == new_key:
            has_new_category = True
        if category_key == old_key:
            if not has_new_category and all(item.casefold() != new_key for item in renamed_categories):
                renamed_categories.append(canonical_new_category)
                has_new_category = True
            continue
        if category_key != new_key or all(item.casefold() != new_key for item in renamed_categories):
            renamed_categories.append(category)
    if not has_new_category and all(item.casefold() != new_key for item in renamed_categories):
        renamed_categories.append(canonical_new_category)
    if not renamed_categories:
        renamed_categories = [deps["DEFAULT_AUDIO_CATEGORIES"][-1]]

    tracks = deps["load_audio_tracks"]()
    moved_track_ids = deps["replace_item_field_value"](tracks, "category", old_category, canonical_new_category)
    deps["save_audio_categories"](renamed_categories)
    deps["save_audio_tracks"](tracks)
    return {
        "ok": True,
        "category": old_category,
        "new_category": canonical_new_category,
        "categories": deps["load_audio_categories"](),
        "moved_track_ids": moved_track_ids,
    }, 200


def reorder_audio_categories(deps: dict, payload: dict) -> dict:
    ordered = deps["reorder_existing_tags"](payload.get("categories", []), deps["load_audio_categories"]())
    deps["save_audio_categories"](ordered)
    return {"ok": True, "categories": deps["load_audio_categories"]()}


def update_audio(deps: dict, form, track_id: str) -> None:
    tracks = deps["load_audio_tracks"]()
    known_tags = deps["load_audio_tags"]()
    known_categories = deps["load_audio_categories"]()
    for item in tracks:
        if item.get("id") != track_id:
            continue
        item["title"] = form.get("title", "").strip() or item.get("title", AUDIO_ITEM_FALLBACK)
        item["category"] = deps["normalize_audio_category"](form.get("category", item.get("category", "")))
        item["tags"] = deps["normalize_audio_item_tags"](form.get("tags", ""))
        if item["category"].casefold() not in {category.casefold() for category in known_categories}:
            known_categories.append(item["category"])
        for tag in item["tags"]:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        if item.get("source_type") == "youtube":
            url = form.get("url", "").strip()
            if deps["is_youtube_url"](url):
                if url != item.get("url", ""):
                    old_thumbnail = item.get("thumbnail_filename", "")
                    if old_thumbnail:
                        deps["delete_audio_thumbnail"](old_thumbnail)
                    metadata = deps["fetch_youtube_metadata"](url)
                    item["thumbnail_filename"] = deps["save_youtube_thumbnail"](url, str(metadata.get("thumbnail_url") or ""))
                item["url"] = url
        item["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
        break
    deps["save_audio_tags"](known_tags)
    deps["save_audio_categories"](known_categories)
    deps["save_audio_tracks"](tracks)
