import json
from uuid import uuid4


GODS_EXPORT_SCHEMA = "ogma.gods.export.v1"


GOD_NOT_FOUND = "Божество не найдено."


def gods_page_context(deps: dict, query: dict) -> tuple[str, dict]:
    campaign_slug = query.get("campaign", "").strip()
    campaign = deps["get_campaign"](campaign_slug) if campaign_slug else None
    if campaign is None:
        return "redirect_index", {}

    selected_domains = deps["normalize_tags"](query.getlist("domain") or query.getlist("tag"))
    excluded_domains = deps["normalize_tags"](query.getlist("exclude_domain") or query.getlist("exclude_tag"))
    selected_alignments = deps["normalize_tags"](query.getlist("alignment"))
    excluded_alignments = deps["normalize_tags"](query.getlist("exclude_alignment"))
    selected_ranks = deps["normalize_tags"](query.getlist("rank"))
    excluded_ranks = deps["normalize_tags"](query.getlist("exclude_rank"))
    selected_pantheons = deps["normalize_tags"](query.getlist("pantheon"))
    excluded_pantheons = deps["normalize_tags"](query.getlist("exclude_pantheon"))
    search = query.get("q", "").strip()
    selected_alignment = selected_alignments[0] if selected_alignments else ""
    open_god_id = query.get("god", "").strip()
    edit_god_id = query.get("edit", "").strip()

    all_gods = deps["prepare_gods"](campaign_slug)
    filtered_gods = deps["filter_gods"](
        all_gods,
        selected_domains,
        excluded_domains,
        search,
        selected_alignments,
        excluded_alignments,
        selected_ranks,
        excluded_ranks,
        selected_pantheons,
        excluded_pantheons,
    )
    alignments = deps["load_god_alignments"](campaign_slug)
    domains = deps["visible_god_domains"](campaign_slug, all_gods)
    ranks = deps["visible_god_ranks"](all_gods)
    pantheons = deps["visible_god_pantheons"](campaign_slug, all_gods)

    active_god = None
    if open_god_id:
        active_god = next((god for god in all_gods if god["id"] == open_god_id), None)
    active_edit_god = None
    if edit_god_id:
        active_edit_god = next((god for god in all_gods if god["id"] == edit_god_id), None)

    return "render", {
        "campaign": campaign,
        "gods": filtered_gods,
        "all_gods": all_gods,
        "god_groups": deps["gods_by_alignment"](filtered_gods, alignments),
        "domains": domains,
        "ranks": ranks,
        "pantheons": pantheons,
        "alignments": alignments,
        "selected_domains": selected_domains,
        "excluded_domains": excluded_domains,
        "selected_alignments": selected_alignments,
        "excluded_alignments": excluded_alignments,
        "selected_ranks": selected_ranks,
        "excluded_ranks": excluded_ranks,
        "selected_pantheons": selected_pantheons,
        "excluded_pantheons": excluded_pantheons,
        "search": search,
        "selected_alignment": selected_alignment,
        "active_god": active_god,
        "active_edit_god": active_edit_god,
        "nav_sections": deps["CAMPAIGN_SECTIONS"],
        "render_note_content": deps["render_note_content"],
    }


def create_god(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    now = deps["datetime"].now().isoformat(timespec="seconds")
    god = deps["normalize_god"](
        {
            "name": form.get("name", "").strip(),
            "alignment": form.get("alignment", "").strip(),
            "domains": form.get("domains", ""),
            "pantheon": form.get("pantheon", "").strip(),
            "rank": form.get("rank", "").strip(),
            "titles": form.get("titles", ""),
            "symbol": form.get("symbol", "").strip(),
            "source": form.get("source", "").strip(),
            "description": form.get("description", "").strip(),
            "created_at": now,
            "updated_at": now,
        },
        campaign_slug,
    )
    gods = deps["load_gods"](campaign_slug)
    gods.append(god)
    _remember_labels(deps, campaign_slug, god)
    deps["save_gods"](campaign_slug, gods)
    return "ok", campaign_slug, {"ok": True, "god": god}, 200


def update_god(deps: dict, form, god_id: str) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    gods = deps["load_gods"](campaign_slug)
    updated_god = None
    for index, item in enumerate(gods):
        if item.get("id") != god_id:
            continue
        updated_god = deps["normalize_god"](
            {
                **item,
                "name": form.get("name", "").strip() or item.get("name", ""),
                "alignment": form.get("alignment", "").strip(),
                "domains": form.get("domains", ""),
                "pantheon": form.get("pantheon", "").strip(),
                "rank": form.get("rank", "").strip(),
                "titles": form.get("titles", ""),
                "symbol": form.get("symbol", "").strip(),
                "source": form.get("source", "").strip(),
                "description": form.get("description", "").strip(),
                "updated_at": deps["datetime"].now().isoformat(timespec="seconds"),
            },
            campaign_slug,
        )
        gods[index] = updated_god
        break

    if updated_god is None:
        return "not_found", campaign_slug, {"ok": False, "error": "god_not_found"}, 404
    _remember_labels(deps, campaign_slug, updated_god)
    deps["save_gods"](campaign_slug, gods)
    return "ok", campaign_slug, {"ok": True, "god": updated_god}, 200


def delete_gods(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    god_ids = {god_id for god_id in form.getlist("god_ids") if god_id}
    if god_ids:
        deps["save_gods"](campaign_slug, [god for god in deps["load_gods"](campaign_slug) if god.get("id") not in god_ids])
    return "ok", campaign_slug


def delete_all_gods(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    deps["save_gods"](campaign_slug, [])
    return "ok", campaign_slug


def export_gods(deps: dict, query: dict) -> tuple[str, str, str, str, int]:
    campaign_slug = query.get("campaign", "").strip()
    campaign = deps["get_campaign"](campaign_slug) if campaign_slug else None
    if campaign is None:
        return "not_found", campaign_slug, "", "", 404

    payload = {
        "schema": GODS_EXPORT_SCHEMA,
        "exported_at": deps["datetime"].now().isoformat(timespec="seconds"),
        "source_campaign": {
            "slug": campaign.get("slug", campaign_slug),
            "name": campaign.get("name", ""),
        },
        "labels": {
            "alignments": deps["load_god_alignments"](campaign_slug),
            "domains": deps["load_god_domains"](campaign_slug),
            "ranks": deps["load_god_ranks"](campaign_slug),
            "pantheons": deps["load_god_pantheons"](campaign_slug),
        },
        "gods": deps["prepare_gods"](campaign_slug),
    }
    filename = f"ogma-gods-{campaign_slug or 'campaign'}.json"
    return "ok", campaign_slug, filename, json.dumps(payload, ensure_ascii=False, indent=2), 200


def _merge_import_payload(
    deps: dict,
    campaign_slug: str,
    raw_payload: object,
    *,
    preserve_ids: bool = False,
    replace_existing: bool = False,
) -> tuple[dict, int]:
    if isinstance(raw_payload, list):
        incoming_raw = raw_payload
        labels = {}
    elif isinstance(raw_payload, dict):
        incoming_raw = raw_payload.get("gods", [])
        labels = raw_payload.get("labels", {})
    else:
        return {"ok": False, "error": "invalid_payload"}, 400

    if not isinstance(incoming_raw, list):
        return {"ok": False, "error": "invalid_gods"}, 400

    imported_gods = [deps["normalize_god"](item, campaign_slug) for item in incoming_raw if isinstance(item, dict)]
    if not imported_gods:
        return {"ok": False, "error": "empty_import"}, 400

    existing_gods = deps["load_gods"](campaign_slug)
    removed = len(existing_gods) if replace_existing else 0
    gods = [] if replace_existing else existing_gods
    normalized_existing = [deps["normalize_god"](item, campaign_slug) for item in gods]
    by_id = {god.get("id"): index for index, god in enumerate(normalized_existing) if god.get("id")}
    by_name = {_god_import_name_key(god): index for index, god in enumerate(normalized_existing) if _god_import_name_key(god)}

    created = 0
    updated = 0
    now = deps["datetime"].now().isoformat(timespec="seconds")
    for god in imported_gods:
        match_index = by_id.get(god.get("id"))
        matched_by_id = match_index is not None
        if match_index is None:
            match_index = by_name.get(_god_import_name_key(god))
        if match_index is None:
            created += 1
            if not preserve_ids or not god.get("id") or god.get("id") in by_id:
                god["id"] = uuid4().hex
            gods.append(god)
            normalized_existing.append(god)
            new_index = len(normalized_existing) - 1
            by_id[god.get("id")] = new_index
            by_name[_god_import_name_key(god)] = new_index
            continue

        previous = normalized_existing[match_index]
        if not matched_by_id:
            god["id"] = previous.get("id") or god.get("id")
        god["created_at"] = previous.get("created_at") or god.get("created_at") or now
        god["updated_at"] = now
        gods[match_index] = god
        normalized_existing[match_index] = god
        by_id[god.get("id")] = match_index
        by_name[_god_import_name_key(god)] = match_index
        updated += 1

    _merge_imported_labels(
        deps,
        campaign_slug,
        labels,
        imported_gods,
        replace_existing=replace_existing,
    )
    deps["save_gods"](campaign_slug, gods)
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total": len(imported_gods),
        "replaced": replace_existing,
        "removed": removed,
    }, 200


def import_gods(deps: dict, form, files) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    upload = files.get("gods_file")
    if upload is None or not getattr(upload, "filename", ""):
        return "ok", campaign_slug, {"ok": False, "error": "missing_file"}, 400

    try:
        raw_payload = load_limited_json_stream(upload.stream)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return "ok", campaign_slug, {"ok": False, "error": "invalid_json"}, 400
    payload, status = _merge_import_payload(deps, campaign_slug, raw_payload)
    return "ok", campaign_slug, payload, status


def god_catalog(deps: dict, campaign_slug: str, *, force: bool = False) -> tuple[str, dict, int]:
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", {"ok": False, "error": "campaign_not_found"}, 404
    return "ok", deps["god_catalog_manager"].catalog(campaign_slug, force=force), 200


def install_god_packs(deps: dict, request_payload: object) -> tuple[str, str, dict, int]:
    if not isinstance(request_payload, dict):
        return "ok", "", {"ok": False, "error": "invalid_payload"}, 400
    campaign_slug = str(request_payload.get("campaign_slug", "")).strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {"ok": False, "error": "campaign_not_found"}, 404

    downloads = deps["god_catalog_manager"].download_packs(request_payload.get("packs"))
    combined_payload = {
        "schema": GODS_EXPORT_SCHEMA,
        "labels": {"alignments": [], "domains": [], "ranks": [], "pantheons": []},
        "gods": [],
    }
    for download in downloads:
        pack_payload = download["payload"]
        labels = pack_payload.get("labels", {})
        if isinstance(labels, dict):
            for key in combined_payload["labels"]:
                values = labels.get(key, [])
                if isinstance(values, list):
                    combined_payload["labels"][key].extend(values)
        combined_payload["gods"].extend(pack_payload.get("gods", []))

    result, status = _merge_import_payload(
        deps,
        campaign_slug,
        combined_payload,
        preserve_ids=True,
        replace_existing=request_payload.get("replace") is True,
    )
    if status != 200 or not result.get("ok"):
        return "ok", campaign_slug, {"ok": False, "error": "empty_import"}, 400

    entries = [download["entry"] for download in downloads]
    deps["god_catalog_manager"].record_installed(campaign_slug, entries)
    result["packs"] = [
        {"id": entry["id"], "title": entry["title"], "version": entry["version"]}
        for entry in entries
    ]
    return "ok", campaign_slug, result, status


def add_god_domain(deps: dict, form) -> tuple[str, str, dict]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}
    domain = form.get("domain", "").strip()
    domains, created = deps["append_unique_tag"](deps["load_god_domains"](campaign_slug), domain)
    if created:
        deps["save_god_domains"](campaign_slug, domains)
    return "ok", campaign_slug, {"ok": True, "domain": domain, "domains": deps["load_god_domains"](campaign_slug), "created": created}


def delete_god_domain(deps: dict, form) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    domain = form.get("domain", "").strip()
    deps["save_god_domains"](campaign_slug, deps["delete_tag_from_list"](deps["load_god_domains"](campaign_slug), domain))
    gods = deps["load_gods"](campaign_slug)
    for god in gods:
        god["domains"] = [item for item in deps["normalize_god_domains"](god.get("domains", [])) if item.casefold() != domain.casefold()]
    deps["save_gods"](campaign_slug, gods)
    return "ok", campaign_slug


def _category_config(deps: dict, category: str) -> dict | None:
    configs = {
        "alignment": {
            "load": deps["load_god_alignments"],
            "save": deps["save_god_alignments"],
            "field": "alignment",
            "fallback": deps["FALLBACK_GOD_ALIGNMENT"],
            "required": [deps["FALLBACK_GOD_ALIGNMENT"]],
        },
        "domain": {
            "load": deps["load_god_domains"],
            "save": deps["save_god_domains"],
            "field": "domains",
            "fallback": "",
            "required": [],
        },
        "rank": {
            "load": deps["load_god_ranks"],
            "save": deps["save_god_ranks"],
            "field": "rank",
            "fallback": "",
            "required": [],
        },
        "pantheon": {
            "load": deps["load_god_pantheons"],
            "save": deps["save_god_pantheons"],
            "field": "pantheons",
            "fallback": "",
            "required": [],
        },
    }
    return configs.get(category)


def add_god_filter_value(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    category = form.get("category", "").strip()
    config = _category_config(deps, category)
    if config is None:
        return "ok", campaign_slug, {"ok": False, "error": "unknown_category"}, 400
    value = form.get("value", "").strip()
    values, created = deps["append_unique_tag"](config["load"](campaign_slug), value)
    if created:
        config["save"](campaign_slug, values)
    return "ok", campaign_slug, {"ok": True, "category": category, "value": value, "created": created, "values": config["load"](campaign_slug)}, 200


def delete_god_filter_value(deps: dict, form) -> tuple[str, str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}, 404
    category = form.get("category", "").strip()
    config = _category_config(deps, category)
    if config is None:
        return "ok", campaign_slug, {"ok": False, "error": "unknown_category"}, 400
    value = form.get("value", "").strip()
    if value.casefold() in {item.casefold() for item in config["required"]}:
        return "ok", campaign_slug, {"ok": False, "error": "required_value"}, 400
    config["save"](campaign_slug, deps["delete_tag_from_list"](config["load"](campaign_slug), value))
    gods = deps["load_gods"](campaign_slug)
    value_key = value.casefold()
    for god in gods:
        if category == "domain":
            god["domains"] = [item for item in deps["normalize_god_domains"](god.get("domains", [])) if item.casefold() != value_key]
        elif category == "pantheon":
            god["pantheons"] = [item for item in deps["normalize_tags"](god.get("pantheons", []) or [god.get("pantheon", "")]) if item.casefold() != value_key]
            god["pantheon"] = god["pantheons"][0] if god["pantheons"] else ""
        elif category == "rank" and str(god.get("rank", "")).casefold() == value_key:
            god["rank"] = ""
        elif category == "alignment" and str(god.get("alignment", "")).casefold() == value_key:
            god["alignment"] = config["fallback"]
    deps["save_gods"](campaign_slug, gods)
    return "ok", campaign_slug, {"ok": True, "category": category, "value": value}, 200


def reorder_god_filter_values(deps: dict, payload: dict, form) -> tuple[dict, int]:
    campaign_slug = str(payload.get("campaign_slug", form.get("campaign_slug", ""))).strip()
    if deps["get_campaign"](campaign_slug) is None:
        return {"ok": False, "error": "campaign_not_found"}, 404
    category = str(payload.get("category", form.get("category", ""))).strip()
    config = _category_config(deps, category)
    if config is None:
        return {"ok": False, "error": "unknown_category"}, 400
    requested_values = deps["normalize_tags"](payload.get("values", []))
    current_values = config["load"](campaign_slug) or requested_values
    ordered = deps["reorder_existing_tags"](
        requested_values,
        current_values,
        config["required"],
    )
    config["save"](campaign_slug, ordered)
    return {"ok": True, "category": category, "values": config["load"](campaign_slug)}, 200


def _remember_labels(deps: dict, campaign_slug: str, god: dict) -> None:
    domains = deps["load_god_domains"](campaign_slug)
    for domain in god.get("domains", []):
        if domain.casefold() not in {item.casefold() for item in domains}:
            domains.append(domain)
    deps["save_god_domains"](campaign_slug, domains)

    alignments = deps["load_god_alignments"](campaign_slug)
    alignment = god.get("alignment", "").strip()
    if alignment and alignment.casefold() not in {item.casefold() for item in alignments}:
        alignments.append(alignment)
    deps["save_god_alignments"](campaign_slug, alignments)

    ranks = deps["load_god_ranks"](campaign_slug)
    rank = god.get("rank", "").strip()
    if rank and rank.casefold() not in {item.casefold() for item in ranks}:
        ranks.append(rank)
    deps["save_god_ranks"](campaign_slug, ranks)

    pantheons = deps["load_god_pantheons"](campaign_slug)
    for pantheon in deps["normalize_tags"](god.get("pantheons", []) or [god.get("pantheon", "")]):
        if pantheon.casefold() not in {item.casefold() for item in pantheons}:
            pantheons.append(pantheon)
    deps["save_god_pantheons"](campaign_slug, pantheons)


def _god_import_name_key(god: dict) -> str:
    name = str(god.get("name", "")).strip().casefold()
    english_name = str(god.get("english_name", "")).strip().casefold()
    pantheons = sorted(
        {
            str(value).strip().casefold()
            for value in (god.get("pantheons", []) or [god.get("pantheon", "")])
            if str(value).strip()
        }
    )
    return "||".join([item for item in [name, english_name] if item] + pantheons)


def _merge_imported_labels(
    deps: dict,
    campaign_slug: str,
    labels: dict,
    gods: list[dict],
    *,
    replace_existing: bool = False,
) -> None:
    if not isinstance(labels, dict):
        labels = {}

    _save_merged_labels(
        deps,
        campaign_slug,
        deps["load_god_alignments"],
        deps["save_god_alignments"],
        labels.get("alignments", []),
        [god.get("alignment", "") for god in gods],
        existing_values=[deps["FALLBACK_GOD_ALIGNMENT"]] if replace_existing else None,
    )
    _save_merged_labels(
        deps,
        campaign_slug,
        deps["load_god_domains"],
        deps["save_god_domains"],
        labels.get("domains", []),
        [domain for god in gods for domain in god.get("domains", [])],
        existing_values=[] if replace_existing else None,
    )
    _save_merged_labels(
        deps,
        campaign_slug,
        deps["load_god_ranks"],
        deps["save_god_ranks"],
        labels.get("ranks", []),
        [god.get("rank", "") for god in gods],
        existing_values=[] if replace_existing else None,
    )
    _save_merged_labels(
        deps,
        campaign_slug,
        deps["load_god_pantheons"],
        deps["save_god_pantheons"],
        labels.get("pantheons", []),
        [pantheon for god in gods for pantheon in (god.get("pantheons", []) or [god.get("pantheon", "")])],
        existing_values=[] if replace_existing else None,
    )


def _save_merged_labels(
    deps: dict,
    campaign_slug: str,
    load_func,
    save_func,
    imported_values,
    god_values,
    *,
    existing_values=None,
) -> None:
    merged = deps["normalize_tags"](
        load_func(campaign_slug) if existing_values is None else existing_values
    )
    known = {item.casefold() for item in merged}
    imported_list = imported_values if isinstance(imported_values, (list, tuple, set)) else [imported_values]
    god_list = god_values if isinstance(god_values, (list, tuple, set)) else [god_values]
    for value in deps["normalize_tags"]([*(imported_list or []), *(god_list or [])]):
        if value.casefold() not in known:
            merged.append(value)
            known.add(value.casefold())
    save_func(campaign_slug, merged)
from ogma.safe_json import load_limited_json_stream
