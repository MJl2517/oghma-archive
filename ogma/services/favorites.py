FAVORITE_GROUP_FALLBACK = "Основное"
from ogma.services import party as party_service


FAVORITE_ALLOWED_TYPES = {"character", "party_member", "god", "rule", "resource", "audio"}

FAVORITE_CATEGORY_ORDER = ["character", "party_member", "god", "rule", "resource", "audio"]
FAVORITE_CATEGORY_LABELS = {
    "character": "NPC",
    "party_member": "Игроки",
    "god": "Боги",
    "rule": "Правила",
    "resource": "Ссылки",
    "audio": "Музыка",
}
FAVORITE_MISSING_TITLE = "Элемент не найден"


def _favorite_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("type", "")).strip(),
        str(item.get("id", "")).strip(),
        str(item.get("campaign_slug", "")).strip(),
    )


def _load_favorites(deps: dict) -> tuple[dict, dict]:
    settings = deps["load_settings"]()
    favorites = settings.get("favorites", {})
    if not isinstance(favorites, dict):
        favorites = {}
    groups = favorites.get("groups", [])
    if not isinstance(groups, list) or not groups:
        groups = [{"id": "default", "name": FAVORITE_GROUP_FALLBACK, "items": []}]
    favorites["groups"] = groups
    active_group_id = str(favorites.get("active_group_id", "")).strip()
    group_ids = {str(group.get("id", "")).strip() for group in groups if isinstance(group, dict)}
    if not active_group_id or active_group_id not in group_ids:
        active_group_id = str(groups[0].get("id", "default")).strip() or "default"
    favorites["active_group_id"] = active_group_id
    settings["favorites"] = favorites
    return settings, favorites


def _save_favorites(deps: dict, settings: dict, favorites: dict) -> None:
    settings["favorites"] = favorites
    deps["save_settings"](settings)


def _find_group(favorites: dict, group_id: str) -> dict | None:
    return next((group for group in favorites.get("groups", []) if str(group.get("id", "")).strip() == group_id), None)


def _clean_item(form) -> dict | None:
    item_type = str(form.get("type", "")).strip()
    item_id = str(form.get("id", "")).strip()
    campaign_slug = str(form.get("campaign_slug", "")).strip()
    if item_type not in FAVORITE_ALLOWED_TYPES or not item_id:
        return None
    if item_type in {"character", "party_member", "god"} and not campaign_slug:
        return None
    return {"type": item_type, "id": item_id, "campaign_slug": campaign_slug}


def _payload_values(payload, key: str) -> list:
    if isinstance(payload, dict):
        value = payload.get(key, [])
        return value if isinstance(value, list) else []
    if hasattr(payload, "getlist"):
        return payload.getlist(key)
    return []


def _clean_reorder_item(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    return {
        "type": str(item.get("type", "")).strip(),
        "id": str(item.get("id", "")).strip(),
        "campaign_slug": str(item.get("campaign_slug", "")).strip(),
    }


def _resolve_character(deps: dict, item: dict) -> dict | None:
    campaign_slug = item.get("campaign_slug", "")
    character = next((entry for entry in deps["prepare_characters"](campaign_slug) if entry.get("id") == item.get("id")), None)
    if character is None:
        return None
    campaign = deps["get_campaign"](campaign_slug) or {}
    return {
        "title": character.get("name", ""),
        "subtitle": campaign.get("name", "") or "NPC",
        "url": deps["url_for"]("characters_page", campaign=campaign_slug, character=item.get("id", "")),
    }


def _resolve_party_member(deps: dict, item: dict) -> dict | None:
    campaign_slug = item.get("campaign_slug", "")
    member = next((entry for entry in party_service.load_party(deps, campaign_slug) if entry.get("id") == item.get("id")), None)
    if member is None:
        return None
    prepared = party_service.prepare_party_member(member)
    campaign = deps["get_campaign"](campaign_slug) or {}
    details = " · ".join(
        part
        for part in [
            prepared.get("class", ""),
            f"{prepared.get('level')} ур." if prepared.get("level") else "",
            prepared.get("player_name", ""),
        ]
        if part
    )
    return {
        "title": prepared.get("name", ""),
        "subtitle": details or campaign.get("name", "") or "Персонаж игрока",
        "url": deps["url_for"]("party_page", campaign=campaign_slug, member=item.get("id", "")),
    }


def _resolve_god(deps: dict, item: dict) -> dict | None:
    campaign_slug = item.get("campaign_slug", "")
    god = next((entry for entry in deps["prepare_gods"](campaign_slug) if entry.get("id") == item.get("id")), None)
    if god is None:
        return None
    campaign = deps["get_campaign"](campaign_slug) or {}
    return {
        "title": god.get("name", ""),
        "subtitle": " · ".join(part for part in [campaign.get("name", ""), god.get("alignment", "")] if part),
        "url": deps["url_for"]("gods_page", campaign=campaign_slug, god=item.get("id", "")),
    }


def _resolve_rule(deps: dict, item: dict) -> dict | None:
    rule = deps["find_rule"](item.get("id", ""))
    if rule is None:
        return None
    return {
        "title": rule.get("title", ""),
        "subtitle": " · ".join(part for part in [rule.get("tag", ""), rule.get("source", "")] if part),
        "url": deps["url_for"]("rules_page", rule=item.get("id", "")),
    }


def _resolve_resource(deps: dict, item: dict) -> dict | None:
    resource = next((entry for entry in deps["prepare_resources"]() if entry.get("id") == item.get("id")), None)
    if resource is None:
        return None
    return {
        "title": resource.get("title", ""),
        "subtitle": resource.get("category", "") or resource.get("type_label", ""),
        "url": deps["url_for"]("resources_page", resource=item.get("id", "")),
    }


def _resolve_audio(deps: dict, item: dict) -> dict | None:
    track = next((entry for entry in deps["prepare_audio_tracks"]() if entry.get("id") == item.get("id")), None)
    if track is None:
        return None
    return {
        "title": track.get("title", ""),
        "subtitle": track.get("category", "") or ("YouTube" if track.get("source_type") == "youtube" else "Файл"),
        "url": deps["url_for"]("audio_page", track=item.get("id", "")),
    }


def _resolve_item(deps: dict, item: dict) -> dict:
    resolvers = {
        "character": _resolve_character,
        "party_member": _resolve_party_member,
        "god": _resolve_god,
        "rule": _resolve_rule,
        "resource": _resolve_resource,
        "audio": _resolve_audio,
    }
    item_type = item.get("type", "")
    resolved = resolvers.get(item_type, lambda _deps, _item: None)(deps, item)
    missing = resolved is None
    if resolved is None:
        resolved = {"title": FAVORITE_MISSING_TITLE, "subtitle": "Исходный материал удалён", "url": "#"}
    return {
        **item,
        **resolved,
        "category": item_type,
        "category_label": FAVORITE_CATEGORY_LABELS.get(item_type, item_type),
        "missing": missing,
    }


def _categorized_items(items: list[dict]) -> list[dict]:
    groups = []
    for category in FAVORITE_CATEGORY_ORDER:
        category_items = [item for item in items if item.get("category") == category]
        if category_items:
            groups.append(
                {
                    "type": category,
                    "label": FAVORITE_CATEGORY_LABELS.get(category, category),
                    "items": category_items,
                }
            )
    return groups


def favorites_payload(deps: dict) -> dict:
    _settings, favorites = _load_favorites(deps)
    active_group_id = favorites.get("active_group_id", "default")
    groups = []
    all_group_membership: dict[str, list[str]] = {}
    for group in favorites.get("groups", []):
        raw_items = group.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []
        resolved_items = [_resolve_item(deps, item) for item in raw_items if isinstance(item, dict)]
        for item in resolved_items:
            key = "||".join(_favorite_key(item))
            all_group_membership.setdefault(key, []).append(str(group.get("id", "")))
        groups.append(
            {
                "id": str(group.get("id", "")).strip(),
                "name": str(group.get("name", "")).strip() or FAVORITE_GROUP_FALLBACK,
                "items": resolved_items,
                "categories": _categorized_items(resolved_items),
                "count": len(resolved_items),
                "is_active": str(group.get("id", "")).strip() == active_group_id,
            }
        )
    active_group = next((group for group in groups if group["is_active"]), groups[0] if groups else None)
    return {
        "ok": True,
        "active_group_id": active_group["id"] if active_group else "",
        "active_group": active_group,
        "groups": groups,
        "group_count": len(groups),
        "categories": [{"type": key, "label": FAVORITE_CATEGORY_LABELS[key]} for key in FAVORITE_CATEGORY_ORDER],
        "memberships": all_group_membership,
    }


def create_group(deps: dict, form) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    name = str(form.get("name", "")).strip() or "Новая группа"
    group_id = deps["uuid4"]().hex
    favorites["groups"].append({"id": group_id, "name": name, "items": []})
    favorites["active_group_id"] = group_id
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 201


def activate_group(deps: dict, group_id: str) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    if _find_group(favorites, group_id) is None:
        return {"ok": False, "error": "group_not_found"}, 404
    favorites["active_group_id"] = group_id
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 200


def rename_group(deps: dict, form, group_id: str) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    group = _find_group(favorites, group_id)
    if group is None:
        return {"ok": False, "error": "group_not_found"}, 404
    name = str(form.get("name", "")).strip()
    if not name:
        return {"ok": False, "error": "empty_name"}, 400
    group["name"] = name
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 200


def delete_group(deps: dict, group_id: str) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    groups = favorites.get("groups", [])
    if len(groups) <= 1:
        return {"ok": False, "error": "last_group"}, 400
    if _find_group(favorites, group_id) is None:
        return {"ok": False, "error": "group_not_found"}, 404
    favorites["groups"] = [group for group in groups if str(group.get("id", "")).strip() != group_id]
    if favorites.get("active_group_id") == group_id:
        favorites["active_group_id"] = str(favorites["groups"][0].get("id", "")).strip()
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 200


def reorder_groups(deps: dict, payload) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    requested_ids = [str(group_id).strip() for group_id in _payload_values(payload, "group_ids") if str(group_id).strip()]
    if not requested_ids:
        return {"ok": False, "error": "empty_order"}, 400
    groups = [group for group in favorites.get("groups", []) if isinstance(group, dict)]
    groups_by_id = {str(group.get("id", "")).strip(): group for group in groups}
    ordered = []
    seen = set()
    for group_id in requested_ids:
        group = groups_by_id.get(group_id)
        if group is not None and group_id not in seen:
            ordered.append(group)
            seen.add(group_id)
    ordered.extend(group for group in groups if str(group.get("id", "")).strip() not in seen)
    favorites["groups"] = ordered
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 200


def reorder_items(deps: dict, group_id: str, payload) -> tuple[dict, int]:
    settings, favorites = _load_favorites(deps)
    group = _find_group(favorites, group_id)
    if group is None:
        return {"ok": False, "error": "group_not_found"}, 404
    items = group.get("items", [])
    if not isinstance(items, list):
        items = []
    requested_items = [_clean_reorder_item(item) for item in _payload_values(payload, "items")]
    requested_keys = [_favorite_key(item) for item in requested_items if item is not None]
    if not requested_keys:
        return {"ok": False, "error": "empty_order"}, 400
    items_by_key = {_favorite_key(item): item for item in items if isinstance(item, dict)}
    ordered = []
    seen = set()
    for key in requested_keys:
        item = items_by_key.get(key)
        if item is not None and key not in seen:
            ordered.append(item)
            seen.add(key)
    ordered.extend(item for item in items if isinstance(item, dict) and _favorite_key(item) not in seen)
    group["items"] = ordered
    _save_favorites(deps, settings, favorites)
    return favorites_payload(deps), 200


def toggle_item(deps: dict, form) -> tuple[dict, int]:
    clean_item = _clean_item(form)
    if clean_item is None:
        return {"ok": False, "error": "invalid_item"}, 400
    settings, favorites = _load_favorites(deps)
    group_id = str(form.get("group_id", "")).strip() or favorites.get("active_group_id", "")
    group = _find_group(favorites, group_id)
    if group is None:
        return {"ok": False, "error": "group_not_found"}, 404
    items = group.setdefault("items", [])
    if not isinstance(items, list):
        items = []
        group["items"] = items
    key = _favorite_key(clean_item)
    existing_index = next((index for index, item in enumerate(items) if _favorite_key(item) == key), None)
    added = existing_index is None
    if existing_index is None:
        items.append({**clean_item, "added_at": deps["datetime"].now().isoformat(timespec="seconds")})
    else:
        items.pop(existing_index)
    _save_favorites(deps, settings, favorites)
    payload = favorites_payload(deps)
    payload["changed"] = {**clean_item, "group_id": group_id, "added": added}
    return payload, 200
