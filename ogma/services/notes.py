NOTE_MATERIAL_NOT_FOUND = "\u041c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d."
NOTE_TYPE_SESSION = "\u0421\u0435\u0441\u0441\u0438\u044f"
NOTE_STATUS_PLANNED = "\u0412 \u043f\u043b\u0430\u043d\u0430\u0445"
NOTE_TITLE_FALLBACK = "\u0417\u0430\u043f\u0438\u0441\u044c"


def notes_page_context(deps: dict, query: dict) -> tuple[str, dict]:
    campaign_slug = query.get("campaign", "").strip()
    campaign = deps["get_campaign"](campaign_slug) if campaign_slug else None
    if campaign is None:
        return "redirect_index", {}

    selected_tags = deps["normalize_tags"](query.getlist("tag"))
    excluded_tags = deps["normalize_tags"](query.getlist("exclude_tag"))
    search = query.get("q", "").strip()
    note_type = query.get("type", "").strip()
    status = query.get("status", "").strip()
    sort = query.get("sort", "session").strip()
    reference_filter = query.get("ref", "").strip()
    date_from = query.get("date_from", "").strip()
    date_to = query.get("date_to", "").strip()
    open_note_id = query.get("note", "").strip()
    skip_reference_options = query.get("_skip_reference_options") == "1"

    all_notes = deps["prepare_notes"](campaign_slug)
    reference_options = deps["build_note_reference_options"](campaign_slug)
    reference_lookup = {
        (item.get("type", ""), item.get("id", "")): item
        for item in reference_options
    }
    for note in all_notes:
        note["references"] = [
            {
                "type": reference["type"],
                "id": reference["id"],
                "label": authoritative["label"],
                "url": authoritative["url"],
            }
            for reference in note.get("references", [])
            if (
                authoritative := reference_lookup.get(
                    (reference.get("type", ""), reference.get("id", ""))
                )
            )
        ]
    filtered_notes = deps["sort_notes"](
        deps["filter_notes"](
            all_notes,
            selected_tags,
            excluded_tags,
            search,
            note_type if note_type in deps["NOTE_TYPES"] else "",
            status if status in deps["NOTE_STATUSES"] else "",
            reference_filter,
            date_from,
            date_to,
        ),
        sort,
    )
    active_note = None
    if open_note_id:
        active_note = next((note for note in all_notes if note["id"] == open_note_id), None)
    if active_note is None and filtered_notes:
        active_note = filtered_notes[0]
    backlinks_by_note = {
        note["id"]: deps["note_backlinks"](campaign_slug, note, all_notes)
        for note in all_notes
    }
    session_calendar_events = [
        {
            "id": note.get("id", ""),
            "title": note.get("title", ""),
            "session_number": note.get("session_number", 0),
            "status": note.get("status", ""),
            "world_date": note.get("world_date", ""),
        }
        for note in all_notes
        if note.get("status") in deps["NOTE_STATUSES"] and note.get("world_date")
    ]

    return "render", {
        "campaign": campaign,
        "notes": filtered_notes,
        "all_notes": all_notes,
        "session_stats": deps["build_session_stats"](all_notes),
        "active_note": active_note,
        "backlinks": deps["note_backlinks"](campaign_slug, active_note, all_notes) if active_note else [],
        "backlinks_by_note": backlinks_by_note,
        "tags": deps["visible_note_tags"](campaign_slug, all_notes),
        "selected_tags": selected_tags,
        "excluded_tags": excluded_tags,
        "search": search,
        "selected_type": note_type,
        "selected_status": status,
        "selected_sort": sort if sort in deps["NOTE_SORT_OPTIONS"] else "session",
        "reference_filter": reference_filter,
        "date_from": date_from,
        "date_to": date_to,
        "note_types": deps["NOTE_TYPES"],
        "note_statuses": deps["NOTE_STATUSES"],
        "note_sort_options": deps["NOTE_SORT_OPTIONS"],
        "required_tags": deps["REQUIRED_NOTE_TAGS"],
        "reference_options": [] if skip_reference_options else reference_options,
        "session_calendar_events": session_calendar_events,
        "empty_note": {"references": []},
        "render_note_content": deps["render_note_content"],
        "nav_sections": deps["CAMPAIGN_SECTIONS"],
    }


def material_preview(deps: dict, query: dict) -> tuple[dict, int]:
    campaign_slug = query.get("campaign", "").strip()
    material_type = query.get("type", "").strip()
    material_id = query.get("id", "").strip()
    payload = deps["material_preview_payload"](campaign_slug, material_type, material_id)
    if payload is None:
        return {"error": NOTE_MATERIAL_NOT_FOUND}, 404
    return payload, 200


def create_note(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    now = deps["datetime"].now().isoformat(timespec="seconds")
    existing_notes = deps["prepare_notes"](campaign_slug)
    session_number = max(note.get("session_number", 0) for note in existing_notes) + 1 if existing_notes else 0
    note = deps["normalize_note"](
        {
            "title": form.get("title", "").strip(),
            "planned_body": form.get("planned_body", "").strip(),
            "happened_body": form.get("happened_body", "").strip(),
            "type": NOTE_TYPE_SESSION,
            "status": form.get("status", NOTE_STATUS_PLANNED).strip(),
            "session_number": session_number,
            "prep_hours": form.get("prep_hours", "").strip(),
            "play_hours": form.get("play_hours", "").strip(),
            "tags": form.get("tags", ""),
            "world_date": form.get("world_date", "").strip(),
            "references": form.get("references_json", "[]"),
            "created_at": now,
            "updated_at": now,
        }
    )
    notes = deps["load_notes"](campaign_slug)
    notes.append(note)
    known_tags = deps["load_note_tags"](campaign_slug)
    for tag in note["tags"]:
        if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
            known_tags.append(tag)
    deps["save_note_tags"](campaign_slug, known_tags)
    deps["save_notes"](campaign_slug, notes)
    return "ok", campaign_slug, {"ok": True, "note": note}, 200


def update_note(deps: dict, form, note_id: str) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    notes = deps["load_notes"](campaign_slug)
    known_tags = deps["load_note_tags"](campaign_slug)
    updated_note = None
    for index, item in enumerate(notes):
        if item.get("id") != note_id:
            continue
        updated_note = deps["normalize_note"](
            {
                **item,
                "title": form.get("title", "").strip() or item.get("title", NOTE_TITLE_FALLBACK),
                "planned_body": form.get("planned_body", "").strip(),
                "happened_body": form.get("happened_body", "").strip(),
                "type": NOTE_TYPE_SESSION,
                "status": form.get("status", NOTE_STATUS_PLANNED).strip(),
                "session_number": item.get("session_number", 0),
                "prep_hours": form.get("prep_hours", "").strip(),
                "play_hours": form.get("play_hours", "").strip(),
                "tags": form.get("tags", ""),
                "world_date": form.get("world_date", "").strip(),
                "references": form.get("references_json", "[]"),
                "updated_at": deps["datetime"].now().isoformat(timespec="seconds"),
            }
        )
        notes[index] = updated_note
        break

    if updated_note is None:
        return "not_found", campaign_slug, {"ok": False, "error": "note_not_found"}, 404
    for tag in updated_note["tags"]:
        if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
            known_tags.append(tag)
    deps["save_note_tags"](campaign_slug, known_tags)
    deps["save_notes"](campaign_slug, notes)
    return "ok", campaign_slug, {"ok": True, "note": updated_note}, 200


def delete_notes(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    note_ids = {note_id for note_id in form.getlist("note_ids") if note_id}
    if note_ids:
        deps["save_notes"](campaign_slug, [note for note in deps["load_notes"](campaign_slug) if note.get("id") not in note_ids])
    return "ok", campaign_slug


def delete_all_notes(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    deps["save_notes"](campaign_slug, [])
    return "ok", campaign_slug


def add_note_tag(deps: dict, form) -> tuple[str, str, dict]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_note_tags"](campaign_slug), tag)
    if created:
        deps["save_note_tags"](campaign_slug, tags)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": tag,
        "tags": deps["load_note_tags"](campaign_slug),
        "created": created,
    }


def delete_note_tag(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() in {item.casefold() for item in deps["REQUIRED_NOTE_TAGS"]}:
        return "error", campaign_slug, {
            "ok": False,
            "error": "service_tag",
            "tag": tag,
            "fallback": deps["UNSORTED_NOTE_TAG"],
        }, 400

    tags = deps["delete_tag_from_list"](deps["load_note_tags"](campaign_slug), tag)
    notes = deps["load_notes"](campaign_slug)
    for item in notes:
        item["tags"] = deps["normalize_note_item_tags"](item.get("tags", []))
    moved_note_ids = deps["remove_tag_from_items"](notes, tag, deps["REQUIRED_NOTE_TAGS"])
    deps["save_note_tags"](campaign_slug, tags)
    deps["save_notes"](campaign_slug, notes)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": tag,
        "fallback": deps["UNSORTED_NOTE_TAG"],
        "moved_note_ids": moved_note_ids,
        "tags": deps["load_note_tags"](campaign_slug),
    }, 200


def rename_note_tag(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404

    old_tag = form.get("old_tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    required_keys = {item.casefold() for item in deps["REQUIRED_NOTE_TAGS"]}
    if not old_tag or not new_tag or old_tag.casefold() in required_keys or new_tag.casefold() in required_keys:
        return "error", campaign_slug, {"ok": False, "error": "invalid_tag"}, 400

    old_key = old_tag.casefold()
    new_key = new_tag.casefold()
    tags = deps["load_note_tags"](campaign_slug)
    if not any(tag.casefold() == old_key for tag in tags):
        return "error", campaign_slug, {"ok": False, "error": "tag_not_found", "tag": old_tag}, 404
    canonical_new_tag = next((tag for tag in tags if tag.casefold() == new_key), new_tag)
    if old_key == new_key:
        return "ok", campaign_slug, {
            "ok": True,
            "tag": old_tag,
            "new_tag": canonical_new_tag,
            "renamed_note_ids": [],
            "tags": tags,
        }, 200

    renamed_tags = []
    has_new_tag = any(tag.casefold() == new_key for tag in tags)
    for tag in tags:
        tag_key = tag.casefold()
        if tag_key == old_key:
            if not has_new_tag and all(item.casefold() != new_key for item in renamed_tags):
                renamed_tags.append(canonical_new_tag)
            continue
        if tag_key != new_key or all(item.casefold() != new_key for item in renamed_tags):
            renamed_tags.append(tag)
    if not has_new_tag and all(item.casefold() != new_key for item in renamed_tags):
        renamed_tags.append(canonical_new_tag)

    notes = deps["load_notes"](campaign_slug)
    renamed_note_ids = []
    for item in notes:
        raw_tags = item.get("tags", [])
        if not any(str(tag).casefold() == old_key for tag in raw_tags):
            continue
        item["tags"] = deps["normalize_note_item_tags"](
            [canonical_new_tag if str(tag).casefold() == old_key else tag for tag in raw_tags]
        )
        renamed_note_ids.append(item.get("id", ""))

    deps["save_note_tags"](campaign_slug, renamed_tags)
    deps["save_notes"](campaign_slug, notes)
    return "ok", campaign_slug, {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "renamed_note_ids": [item for item in renamed_note_ids if item],
        "tags": deps["load_note_tags"](campaign_slug),
    }, 200


def reorder_note_tags(deps: dict, form, payload: dict) -> tuple[dict, int]:
    campaign_slug = payload.get("campaign_slug", form.get("campaign_slug", "")).strip()
    if deps["get_campaign"](campaign_slug) is None:
        return {"ok": False, "error": "campaign_not_found"}, 404
    ordered = deps["reorder_existing_tags"](payload.get("tags", []), deps["load_note_tags"](campaign_slug), deps["REQUIRED_NOTE_TAGS"])
    deps["save_note_tags"](campaign_slug, ordered)
    return {"ok": True, "tags": deps["load_note_tags"](campaign_slug)}, 200
