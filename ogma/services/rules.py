import json

from ogma.errors import ValidationError
from ogma.safe_json import load_limited_json_stream
from ogma.safe_urls import ExternalHttpUrl, InternalPath, UnsafeUrl

RULES_EXPORT_SCHEMA = "ogma.rules.export.v1"
RULE_FALLBACK_TITLE = "\u041f\u0440\u0430\u0432\u0438\u043b\u043e"
RULE_NEW_TITLE = "\u041d\u043e\u0432\u043e\u0435 \u043f\u0440\u0430\u0432\u0438\u043b\u043e"
RULE_SOURCE_FALLBACK = "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a"


def _safe_rule_url(raw_value: str, *, reject_invalid: bool = False) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    for parser in (InternalPath, ExternalHttpUrl):
        try:
            return parser.parse(value).value
        except UnsafeUrl:
            continue
    if reject_invalid:
        raise ValidationError("Rule links must use http, https, or a local application path.")
    return ""


def rules_page_context(deps: dict) -> dict:
    rules = [
        {**rule, "book_url": _safe_rule_url(rule.get("book_url", ""))}
        for rule in deps["load_rules"]()
    ]
    tags = deps["load_rule_tags"]()
    sources = deps["load_rule_sources"]()
    return {
        "rules": rules,
        "tags": tags,
        "sources": sources,
        "service_rule_tag": deps["SERVICE_RULE_TAG"],
        "grouped_rules": deps["rules_by_tag"](rules, tags),
        "render_rule_content": deps["render_rule_content"],
    }


def rule_preview(deps: dict, rule_id: str) -> tuple[dict, int]:
    rule = deps["find_rule"](rule_id)
    if rule is None:
        return {"ok": False, "error": "rule_not_found"}, 404
    return {
        "ok": True,
        "rule": {
            "id": rule.get("id", ""),
            "title": rule.get("title", RULE_FALLBACK_TITLE),
            "tag": rule.get("tag", deps["SERVICE_RULE_TAG"]),
            "source": rule.get("source", RULE_SOURCE_FALLBACK),
            "page": rule.get("page", ""),
            "book_url": _safe_rule_url(rule.get("book_url", "")),
            "content": rule.get("content", ""),
            "content_html": str(deps["render_rule_content"](rule.get("content", ""))),
        },
    }, 200


def _rule_response_payload(deps: dict, rule: dict, *, include_content_html: bool = True) -> dict:
    payload = {
        "id": rule.get("id", ""),
        "title": rule.get("title", RULE_FALLBACK_TITLE),
        "tag": rule.get("tag", deps["SERVICE_RULE_TAG"]),
        "source": rule.get("source", RULE_SOURCE_FALLBACK),
        "page": rule.get("page", ""),
        "book_url": _safe_rule_url(rule.get("book_url", "")),
        "content": rule.get("content", ""),
    }
    if include_content_html:
        payload["content_html"] = str(deps["render_rule_content"](rule.get("content", "")))
    return payload


def _form_text(form, key: str) -> str:
    return str(form.get(key, "") or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _clean_rule_for_export(rule: dict) -> dict:
    return {
        "id": str(rule.get("id", "")).strip(),
        "title": str(rule.get("title", RULE_FALLBACK_TITLE)).strip() or RULE_FALLBACK_TITLE,
        "tag": str(rule.get("tag", "")).strip(),
        "source": str(rule.get("source", "")).strip() or RULE_SOURCE_FALLBACK,
        "page": str(rule.get("page", "")).strip(),
        "book_url": str(rule.get("book_url", "")).strip(),
        "content": str(rule.get("content", "")).strip(),
        "created_at": str(rule.get("created_at", "")).strip(),
        "updated_at": str(rule.get("updated_at", "")).strip(),
    }


def _normalize_import_rule(deps: dict, raw_rule: dict, now: str) -> dict | None:
    if not isinstance(raw_rule, dict):
        return None
    title = str(raw_rule.get("title", "")).strip()
    content = str(raw_rule.get("content", "")).strip()
    if not title and not content:
        return None
    return {
        "id": str(raw_rule.get("id", "")).strip() or deps["uuid4"]().hex,
        "title": title or RULE_NEW_TITLE,
        "tag": str(raw_rule.get("tag", "")).strip() or deps["SERVICE_RULE_TAG"],
        "source": str(raw_rule.get("source", "")).strip() or RULE_SOURCE_FALLBACK,
        "book_url": _safe_rule_url(raw_rule.get("book_url", "")),
        "page": str(raw_rule.get("page", "")).strip(),
        "content": content,
        "created_at": str(raw_rule.get("created_at", "")).strip() or now,
        "updated_at": str(raw_rule.get("updated_at", "")).strip() or now,
    }


def _rule_import_key(rule: dict) -> str:
    return f"{str(rule.get('title', '')).strip().casefold()}||{str(rule.get('tag', '')).strip().casefold()}"


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


def export_rules(deps: dict) -> tuple[str, str, int]:
    payload = {
        "schema": RULES_EXPORT_SCHEMA,
        "exported_at": deps["datetime"].now().isoformat(timespec="seconds"),
        "labels": {
            "tags": deps["load_rule_tags"](),
            "sources": deps["load_rule_sources"](),
        },
        "rules": [_clean_rule_for_export(rule) for rule in deps["load_rules"]()],
    }
    filename = "ogma-rules-glossary.json"
    return filename, json.dumps(payload, ensure_ascii=False, indent=2), 200


def _merge_import_payload(
    deps: dict,
    raw_payload: object,
    *,
    replace_existing: bool = False,
) -> tuple[dict, int]:
    if isinstance(raw_payload, list):
        incoming_raw = raw_payload
        labels = {}
    elif isinstance(raw_payload, dict):
        incoming_raw = raw_payload.get("rules", [])
        labels = raw_payload.get("labels", {})
    else:
        return {"ok": False, "error": "invalid_payload"}, 400

    if not isinstance(incoming_raw, list):
        return {"ok": False, "error": "invalid_rules"}, 400

    now = deps["datetime"].now().isoformat(timespec="seconds")
    imported_rules = [_normalize_import_rule(deps, item, now) for item in incoming_raw]
    imported_rules = [rule for rule in imported_rules if rule is not None]
    if not imported_rules:
        return {"ok": False, "error": "empty_import"}, 400

    existing_rules = deps["load_rules"]()
    removed = len(existing_rules) if replace_existing else 0
    rules = [] if replace_existing else existing_rules
    by_id = {str(rule.get("id", "")).strip(): index for index, rule in enumerate(rules) if str(rule.get("id", "")).strip()}
    by_title_tag = {_rule_import_key(rule): index for index, rule in enumerate(rules) if _rule_import_key(rule).strip("|")}

    created = 0
    updated = 0
    for rule in imported_rules:
        match_index = by_id.get(rule["id"])
        if match_index is None:
            match_index = by_title_tag.get(_rule_import_key(rule))

        if match_index is None:
            created += 1
            rules.append(rule)
            new_index = len(rules) - 1
            by_id[rule["id"]] = new_index
            by_title_tag[_rule_import_key(rule)] = new_index
            continue

        previous = rules[match_index]
        rule["created_at"] = previous.get("created_at") or rule.get("created_at") or now
        rule["updated_at"] = now
        rules[match_index] = rule
        by_id[rule["id"]] = match_index
        by_title_tag[_rule_import_key(rule)] = match_index
        updated += 1

    imported_tags = labels.get("tags", []) if isinstance(labels, dict) else []
    imported_sources = labels.get("sources", []) if isinstance(labels, dict) else []
    existing_tags = [deps["SERVICE_RULE_TAG"]] if replace_existing else deps["load_rule_tags"]()
    existing_sources = [] if replace_existing else deps["load_rule_sources"]()
    deps["save_rule_tags"](_merge_unique_labels(existing_tags, imported_tags, [rule["tag"] for rule in imported_rules]))
    deps["save_rule_sources"](_merge_unique_labels(existing_sources, imported_sources, [rule["source"] for rule in imported_rules]))
    deps["save_rules"](rules)
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total": len(imported_rules),
        "replaced": replace_existing,
        "removed": removed,
    }, 200


def import_rules(deps: dict, files) -> tuple[dict, int]:
    upload = files.get("rules_file")
    if upload is None or not getattr(upload, "filename", ""):
        return {"ok": False, "error": "missing_file"}, 400

    try:
        raw_payload = load_limited_json_stream(upload.stream)
    except (OSError, TypeError, ValueError):
        return {"ok": False, "error": "invalid_json"}, 400
    return _merge_import_payload(deps, raw_payload)


def glossary_catalog(deps: dict, *, force: bool = False) -> dict:
    return deps["glossary_catalog_manager"].catalog(force=force)


def install_glossary_packs(deps: dict, request_payload: object) -> tuple[dict, int]:
    if not isinstance(request_payload, dict):
        raise ValidationError("Некорректный запрос установки глоссария.")
    downloads = deps["glossary_catalog_manager"].download_packs(request_payload.get("packs"))

    combined_payload = {
        "schema": RULES_EXPORT_SCHEMA,
        "labels": {"tags": [], "sources": []},
        "rules": [],
    }
    for download in downloads:
        pack_payload = download["payload"]
        labels = pack_payload.get("labels", {})
        if isinstance(labels, dict):
            combined_payload["labels"]["tags"] = _merge_unique_labels(
                combined_payload["labels"]["tags"],
                labels.get("tags", []),
            )
            combined_payload["labels"]["sources"] = _merge_unique_labels(
                combined_payload["labels"]["sources"],
                labels.get("sources", []),
            )
        combined_payload["rules"].extend(pack_payload.get("rules", []))

    result, status = _merge_import_payload(
        deps,
        combined_payload,
        replace_existing=request_payload.get("replace") is True,
    )
    if status != 200 or not result.get("ok"):
        raise ValidationError("В выбранных наборах нет правил, которые можно установить.")

    entries = [download["entry"] for download in downloads]
    deps["glossary_catalog_manager"].record_installed(entries)
    result["packs"] = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "version": entry["version"],
        }
        for entry in entries
    ]
    return result, status


def add_rule(deps: dict, form) -> dict:
    tags = deps["load_rule_tags"]()
    sources = deps["load_rule_sources"]()
    tag = form.get("tag", "").strip() or (tags[0] if tags else deps["SERVICE_RULE_TAG"])
    source = form.get("source", "").strip() or (sources[0] if sources else RULE_SOURCE_FALLBACK)
    if tag.casefold() not in {item.casefold() for item in tags}:
        tags.append(tag)
        deps["save_rule_tags"](tags)
    if source.casefold() not in {item.casefold() for item in sources}:
        sources.append(source)
        deps["save_rule_sources"](sources)

    now = deps["datetime"].now().isoformat(timespec="seconds")
    rule = {
        "id": deps["uuid4"]().hex,
        "title": form.get("title", "").strip() or RULE_NEW_TITLE,
        "tag": tag,
        "source": source,
        "book_url": _safe_rule_url(form.get("book_url", ""), reject_invalid=True),
        "page": form.get("page", "").strip(),
        "content": _form_text(form, "content"),
        "created_at": now,
        "updated_at": now,
    }
    if "save_rule_item" in deps:
        deps["save_rule_item"](rule)
    else:
        rules = deps["load_rules"]()
        rules.append(rule)
        deps["save_rules"](rules)
    return {"ok": True, "rule": _rule_response_payload(deps, rule)}


def update_rule(deps: dict, form, rule_id: str) -> tuple[dict, int]:
    tags = deps["load_rule_tags"]()
    sources = deps["load_rule_sources"]()
    rule = deps["find_rule"](rule_id)
    if rule is None:
        return {"ok": False, "error": "rule_not_found"}, 404

    updated_rule = dict(rule)
    old_content = str(updated_rule.get("content", "") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    new_content = _form_text(form, "content")
    updated_rule["title"] = form.get("title", "").strip() or updated_rule.get("title", RULE_FALLBACK_TITLE)
    updated_rule["tag"] = form.get("tag", "").strip() or updated_rule.get("tag", deps["SERVICE_RULE_TAG"])
    updated_rule["source"] = form.get("source", "").strip() or updated_rule.get("source", RULE_SOURCE_FALLBACK)
    updated_rule["book_url"] = _safe_rule_url(
        form.get("book_url", ""),
        reject_invalid=True,
    )
    updated_rule["page"] = form.get("page", "").strip()
    updated_rule["content"] = new_content
    content_changed = old_content != new_content
    updated_rule["updated_at"] = deps["datetime"].now().isoformat(timespec="seconds")
    if updated_rule["tag"].casefold() not in {item.casefold() for item in tags}:
        tags.append(updated_rule["tag"])
        deps["save_rule_tags"](tags)
    if updated_rule["source"].casefold() not in {item.casefold() for item in sources}:
        sources.append(updated_rule["source"])
        deps["save_rule_sources"](sources)
    if "save_rule_item" in deps:
        deps["save_rule_item"](updated_rule)
    else:
        rules = deps["load_rules"]()
        for index, item in enumerate(rules):
            if item.get("id") == rule_id:
                rules[index] = updated_rule
                break
        deps["save_rules"](rules)
    return {
        "ok": True,
        "rule": _rule_response_payload(deps, updated_rule, include_content_html=content_changed),
    }, 200


def delete_rule(deps: dict, rule_id: str) -> tuple[dict, int]:
    if "delete_rule_item" in deps:
        deleted = deps["delete_rule_item"](rule_id)
    else:
        rules = deps["load_rules"]()
        kept_rules = [rule for rule in rules if rule.get("id") != rule_id]
        deleted = len(kept_rules) != len(rules)
        if deleted:
            deps["save_rules"](kept_rules)
    if not deleted:
        return {"ok": False, "error": "rule_not_found"}, 404
    return {"ok": True, "rule_id": rule_id}, 200


def add_rule_tag(deps: dict, form) -> dict:
    tag = form.get("tag", "").strip()
    tags, created = deps["append_unique_tag"](deps["load_rule_tags"](), tag)
    if created:
        deps["save_rule_tags"](tags)
    return {"ok": True, "tag": tag, "tags": deps["load_rule_tags"](), "created": created}


def delete_rule_tag(deps: dict, form) -> tuple[dict, int]:
    tag = form.get("tag", "").strip()
    if not tag or tag.casefold() == deps["SERVICE_RULE_TAG"].casefold():
        return {"ok": False, "error": "service_tag", "tag": tag, "fallback": deps["SERVICE_RULE_TAG"]}, 400

    tags = deps["delete_tag_from_list"](deps["load_rule_tags"](), tag)
    updated_at = deps["datetime"].now().isoformat(timespec="seconds")
    if "replace_rule_field_value" in deps:
        moved_rule_ids = deps["replace_rule_field_value"]("tag", tag, deps["SERVICE_RULE_TAG"], updated_at)
    else:
        rules = deps["load_rules"]()
        moved_rule_ids = deps["replace_item_field_value"](
            rules,
            "tag",
            tag,
            deps["SERVICE_RULE_TAG"],
            updated_at,
        )
        deps["save_rules"](rules)
    deps["save_rule_tags"](tags)
    return {
        "ok": True,
        "tag": tag,
        "fallback": deps["SERVICE_RULE_TAG"],
        "moved_rule_ids": moved_rule_ids,
        "tags": deps["load_rule_tags"](),
    }, 200


def _rename_label(labels: list[str], old_label: str, new_label: str) -> tuple[list[str], str]:
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


def rename_rule_tag(deps: dict, form) -> tuple[dict, int]:
    old_tag = form.get("tag", "").strip()
    new_tag = form.get("new_tag", "").strip()
    service_tag = deps["SERVICE_RULE_TAG"]
    if not old_tag or old_tag.casefold() == service_tag.casefold():
        return {"ok": False, "error": "service_tag", "tag": old_tag}, 400
    if not new_tag or new_tag.casefold() == service_tag.casefold():
        return {"ok": False, "error": "invalid_tag", "tag": new_tag}, 400

    tags = deps["load_rule_tags"]()
    renamed_tags, canonical_new_tag = _rename_label(tags, old_tag, new_tag)
    if old_tag.casefold() == canonical_new_tag.casefold():
        return {"ok": True, "tag": old_tag, "new_tag": canonical_new_tag, "moved_rule_ids": [], "tags": tags}, 200

    updated_at = deps["datetime"].now().isoformat(timespec="seconds")
    if "replace_rule_field_value" in deps:
        moved_rule_ids = deps["replace_rule_field_value"]("tag", old_tag, canonical_new_tag, updated_at)
    else:
        rules = deps["load_rules"]()
        moved_rule_ids = deps["replace_item_field_value"](
            rules,
            "tag",
            old_tag,
            canonical_new_tag,
            updated_at,
        )
        deps["save_rules"](rules)
    deps["save_rule_tags"](renamed_tags)
    return {
        "ok": True,
        "tag": old_tag,
        "new_tag": canonical_new_tag,
        "moved_rule_ids": moved_rule_ids,
        "tags": deps["load_rule_tags"](),
    }, 200


def reorder_rule_tags(deps: dict, payload: dict) -> dict:
    ordered = deps["reorder_existing_tags"](
        payload.get("tags", []),
        deps["load_rule_tags"](),
        [deps["SERVICE_RULE_TAG"]],
    )
    deps["save_rule_tags"](ordered)
    return {"ok": True, "tags": deps["load_rule_tags"]()}


def add_rule_source(deps: dict, form) -> dict:
    source = form.get("source", "").strip()
    sources, created = deps["append_unique_tag"](deps["load_rule_sources"](), source)
    if created:
        deps["save_rule_sources"](sources)
    return {"ok": True, "source": source, "sources": sources, "created": created}


def delete_rule_source(deps: dict, form) -> dict:
    source = form.get("source", "").strip()
    sources = deps["delete_tag_from_list"](deps["load_rule_sources"](), source)
    fallback = sources[0] if sources else RULE_SOURCE_FALLBACK
    updated_at = deps["datetime"].now().isoformat(timespec="seconds")
    if "replace_rule_field_value" in deps:
        moved_rule_ids = deps["replace_rule_field_value"]("source", source, fallback, updated_at)
    else:
        rules = deps["load_rules"]()
        moved_rule_ids = deps["replace_item_field_value"](
            rules,
            "source",
            source,
            fallback,
            updated_at,
        )
        deps["save_rules"](rules)
    deps["save_rule_sources"](sources)
    return {
        "ok": True,
        "source": source,
        "fallback": fallback,
        "moved_rule_ids": moved_rule_ids,
        "sources": deps["load_rule_sources"](),
    }


def rename_rule_source(deps: dict, form) -> tuple[dict, int]:
    old_source = form.get("source", "").strip()
    new_source = form.get("new_source", "").strip()
    if not old_source or not new_source:
        return {"ok": False, "error": "empty_source"}, 400

    sources = deps["load_rule_sources"]()
    renamed_sources, canonical_new_source = _rename_label(sources, old_source, new_source)
    if old_source.casefold() == canonical_new_source.casefold():
        return {"ok": True, "source": old_source, "new_source": canonical_new_source, "moved_rule_ids": [], "sources": sources}, 200

    updated_at = deps["datetime"].now().isoformat(timespec="seconds")
    if "replace_rule_field_value" in deps:
        moved_rule_ids = deps["replace_rule_field_value"]("source", old_source, canonical_new_source, updated_at)
    else:
        rules = deps["load_rules"]()
        moved_rule_ids = deps["replace_item_field_value"](
            rules,
            "source",
            old_source,
            canonical_new_source,
            updated_at,
        )
        deps["save_rules"](rules)
    deps["save_rule_sources"](renamed_sources)
    return {
        "ok": True,
        "source": old_source,
        "new_source": canonical_new_source,
        "moved_rule_ids": moved_rule_ids,
        "sources": deps["load_rule_sources"](),
    }, 200


def reorder_rule_sources(deps: dict, payload: dict) -> dict:
    ordered = deps["reorder_existing_tags"](payload.get("sources", []), deps["load_rule_sources"]())
    deps["save_rule_sources"](ordered)
    return {"ok": True, "sources": ordered}
