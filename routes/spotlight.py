from flask import jsonify, request, url_for

from ogma.services import party as party_service

def register_spotlight_routes(bp, views: dict) -> None:
    def _escape_preview(value) -> str:
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;")
        )

    def _plain_join(items) -> str:
        return ", ".join(str(item) for item in (items or []) if item)

    def _field(label: str, value, markdown: bool = False) -> dict:
        text = str(value or "").strip()
        payload = {"label": label, "value": text or "Не указано"}
        if markdown and text:
            payload["value_html"] = str(views["render_note_content"](text))
        return payload

    def _preview_payload(kind: str, item_id: str, campaign_slug: str) -> dict | None:
        campaigns = views["get_campaigns"]()
        campaign = next((item for item in campaigns if item.get("slug") == campaign_slug), None)
        campaign_name = campaign.get("name", campaign_slug) if campaign else campaign_slug

        if kind == "rules":
            rule = views["find_rule"](item_id)
            if rule is None:
                return None
            meta = [
                f'<span class="rule-source-badge">{_escape_preview(rule.get("source", ""))}</span>' if rule.get("source") else "",
                f'<span>стр. {_escape_preview(rule.get("page", ""))}</span>' if rule.get("page") else "",
                f'<a href="{_escape_preview(rule.get("book_url", ""))}" target="_blank" rel="noreferrer">Открыть оригинал</a>' if rule.get("book_url") else "",
            ]
            return {
                "ok": True,
                "kicker": rule.get("tag") or "Правило",
                "title": rule.get("title") or "Правило",
                "meta_html": " ".join(part for part in meta if part),
                "content_html": str(views["render_rule_content"](rule.get("content", ""))) or "<p>Текста пока нет.</p>",
                "page_url": url_for("rules_page", rule=item_id),
            }

        if kind == "characters":
            if not campaign_slug:
                return None
            character = next((item for item in views["prepare_characters"](campaign_slug) if item.get("id") == item_id), None)
            if character is None:
                return None
            return {
                "ok": True,
                "kicker": "Персонаж",
                "title": character.get("name", "Персонаж"),
                "meta": f"Персонаж · {campaign_name}",
                "image_url": character.get("url", ""),
                "tags": character.get("tags", []),
                "fields": [
                    _field("Возраст", character.get("age")),
                    _field("Пол", character.get("gender")),
                    _field("Раса", character.get("race")),
                    _field("Заметки", character.get("notes") or "Заметок пока нет.", markdown=True),
                ],
                "page_url": url_for("characters_page", campaign=campaign_slug, q=character.get("name", ""), character=item_id),
            }

        if kind == "party_members":
            if not campaign_slug:
                return None
            raw_member = next((item for item in party_service.load_party(views, campaign_slug) if item.get("id") == item_id), None)
            if raw_member is None:
                return None
            member = party_service.prepare_party_member(raw_member)
            fields = [
                _field("Игрок", member.get("player_name")),
                _field("Класс", " ".join(part for part in [member.get("class"), member.get("subclass")] if part)),
                _field("Раса", member.get("race")),
                _field("Кратко", member.get("summary"), markdown=True),
                _field("Заметки мастера", member.get("dm_notes"), markdown=True),
            ]
            for section in member.get("important_text_sections", [])[:3]:
                if isinstance(section, dict):
                    fields.append(_field(section.get("title") or "Раздел", section.get("body"), markdown=True))
            return {
                "ok": True,
                "kicker": "Персонаж группы",
                "title": member.get("name") or "Персонаж группы",
                "meta": f"Персонаж группы · {campaign_name}",
                "fields": fields,
                "page_url": url_for("party_page", campaign=campaign_slug, member=item_id),
            }

        if kind == "notes":
            if not campaign_slug:
                return None
            note = next((item for item in views["prepare_notes"](campaign_slug) if item.get("id") == item_id), None)
            if note is None:
                return None
            body = note.get("body") or note.get("content") or note.get("happened_body") or note.get("planned_body") or ""
            return {
                "ok": True,
                "kicker": "Заметка",
                "title": note.get("title") or "Заметка",
                "meta": f"Заметка · {campaign_name}",
                "tags": note.get("tags", []),
                "content_html": str(views["render_note_content"](body)) if body else "<p>Текста пока нет.</p>",
                "page_url": url_for("notes_page", campaign=campaign_slug, q=note.get("title", ""), note=item_id),
            }

        if kind == "gods":
            if not campaign_slug:
                return None
            god = next((item for item in views["prepare_gods"](campaign_slug) if item.get("id") == item_id), None)
            if god is None:
                return None
            return {
                "ok": True,
                "kicker": "Божество",
                "title": god.get("name") or "Божество",
                "meta": " · ".join(part for part in [campaign_name, god.get("rank"), god.get("alignment")] if part),
                "image_url": (god.get("images") or [""])[0],
                "tags": god.get("domains", []),
                "fields": [
                    _field("Пантеон", _plain_join(god.get("pantheons")) or god.get("pantheon")),
                    _field("Титулы", _plain_join(god.get("titles"))),
                    _field("Символ", god.get("symbol")),
                    _field("Источник", god.get("source")),
                ],
                "content_html": str(views["render_note_content"](god.get("description", ""))) if god.get("description") else "<p>Описание пока не добавлено.</p>",
                "page_url": url_for("gods_page", campaign=campaign_slug, q=god.get("name", ""), god=item_id),
            }

        if kind == "maps":
            maps = views["prepare_maps"]("campaign", campaign_slug) if campaign_slug else views["prepare_maps"]("shared")
            map_item = next((item for item in maps if item.get("id") == item_id), None)
            if map_item is None:
                return None
            return {
                "ok": True,
                "kicker": "Карта",
                "title": map_item.get("title") or "Карта",
                "meta": f"Карта · {campaign_name}" if campaign_slug else "Карта",
                "image_url": map_item.get("url", ""),
                "tags": map_item.get("tags", []),
                "fields": [_field("Теги", _plain_join(map_item.get("tags")) or "Без тегов")],
                "page_url": url_for("maps_page", campaign=campaign_slug, q=map_item.get("title", "")) if campaign_slug else url_for("maps_page", q=map_item.get("title", "")),
            }

        if kind == "scenes":
            scene = next((item for item in views["prepare_scenes"]() if item.get("id") == item_id), None)
            if scene is None:
                return None
            return {
                "ok": True,
                "kicker": "Сцена",
                "title": scene.get("title") or "Сцена",
                "meta": "Сцена",
                "image_url": scene.get("url", ""),
                "tags": scene.get("tags", []),
                "fields": [_field("Теги", _plain_join(scene.get("tags")) or "Без тегов")],
                "page_url": url_for("scenes_page", q=scene.get("title", "")),
            }

        if kind == "generators":
            generator = next((item for item in views["prepare_generators"]() if item.get("id") == item_id), None)
            if generator is None:
                return None
            rows_text = "\n".join(
                f"{row.get('min')}–{row.get('max')}: {row.get('result_markdown', '')}"
                if row.get("min") != row.get("max")
                else f"{row.get('min')}: {row.get('result_markdown', '')}"
                for row in generator.get("rows", [])[:10]
            )
            return {
                "ok": True,
                "kicker": "Генератор",
                "title": generator.get("title") or "Генератор",
                "meta": " · ".join(part for part in [generator.get("category"), generator.get("dice_expression")] if part),
                "tags": generator.get("tags", []),
                "fields": [
                    _field("Формула", generator.get("dice_expression")),
                    _field("Описание", generator.get("description"), markdown=True),
                    _field("Примеры строк", rows_text, markdown=True),
                ],
                "page_url": url_for("generators_page", q=generator.get("title", "")),
            }

        if kind == "campaigns":
            target = campaign or next((item for item in campaigns if item.get("slug") == item_id), None)
            if target is None:
                return None
            return {
                "ok": True,
                "kicker": "Кампейн",
                "title": target.get("name") or "Кампейн",
                "meta": "Кампейн",
                "image_url": target.get("cover_url", ""),
                "content_html": str(views["render_note_content"](target.get("description", ""))) if target.get("description") else "<p>Описание пока не добавлено.</p>",
                "page_url": url_for("campaign_detail", slug=target.get("slug", "")),
            }

        if kind == "audio":
            track = next((item for item in views["prepare_audio_tracks"]() if item.get("id") == item_id), None)
            if track is None:
                return None
            return {
                "ok": True,
                "kicker": "Аудио",
                "title": track.get("title") or "Аудио",
                "meta": " · ".join(part for part in [track.get("category"), track.get("source_type")] if part),
                "tags": track.get("tags", []),
                "fields": [
                    _field("Категория", track.get("category")),
                    _field("Источник", track.get("source_type")),
                    _field("Описание", track.get("description"), markdown=True),
                ],
                "page_url": url_for("audio_page", q=track.get("title", "")),
            }

        if kind == "resources":
            resource = next((item for item in views["prepare_resources"]() if item.get("id") == item_id), None)
            if resource is None:
                return None
            return {
                "ok": True,
                "kicker": "Ресурс",
                "title": resource.get("title") or "Ресурс",
                "meta": " · ".join(part for part in [resource.get("category"), resource.get("source_type")] if part),
                "tags": resource.get("tags", []),
                "fields": [
                    _field("Категория", resource.get("category")),
                    _field("Источник", resource.get("source_type")),
                    _field("Описание", resource.get("description"), markdown=True),
                ],
                "page_url": url_for("resources_page", q=resource.get("title", "")),
            }

        return None

    def _spotlight_kind_priority(kind: str) -> int:
        priorities = {
            "rules": 0,
            "party_members": 1,
            "characters": 2,
            "notes": 3,
            "generators": 4,
            "campaigns": 5,
            "resources": 6,
            "audio": 7,
            "gods": 8,
            "maps": 9,
            "scenes": 10,
        }
        return priorities.get(kind, 20)

    def _spotlight_title_rank(title: str, query: str) -> int:
        title_key = str(title or "").casefold()
        query_key = str(query or "").casefold()
        if not query_key:
            return 3
        if title_key == query_key:
            return 0
        if title_key.startswith(query_key):
            return 1
        if query_key in title_key:
            return 2
        return 3

    def _sort_spotlight_items(items: list[dict], query: str) -> list[dict]:
        return sorted(
            items,
            key=lambda item: (
                _spotlight_kind_priority(item.get("kind", "")),
                _spotlight_title_rank(item.get("title", ""), query),
                len(str(item.get("title", ""))),
                str(item.get("title", "")).casefold(),
            ),
        )

    def _fallback_party_members(query: str, campaign_mode: str, allowed_campaigns: list[str], limit: int = 20) -> list[dict]:
        needle = query.strip().casefold()
        if len(needle) < 3:
            return []
        items = []
        for campaign in views["get_campaigns"]():
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            if campaign_mode == "selected" and slug not in allowed_campaigns:
                continue
            for raw_member in party_service.load_party(views, slug):
                member = party_service.prepare_party_member(raw_member)
                title = str(member.get("name", ""))
                haystack = " ".join(
                    str(part)
                    for part in [
                        title,
                        member.get("id", ""),
                        member.get("source_id", ""),
                        member.get("source_filename", ""),
                        member.get("player_name", ""),
                        member.get("class", ""),
                        member.get("subclass", ""),
                        member.get("race", ""),
                        member.get("background", ""),
                        member.get("alignment", ""),
                        member.get("summary", ""),
                        member.get("dm_notes", ""),
                        " ".join(
                            section.get("body", "")
                            for section in member.get("important_text_sections", [])
                            if isinstance(section, dict)
                        ),
                    ]
                    if part
                ).casefold()
                if needle not in haystack:
                    continue
                items.append(
                    {
                        "kind": "party_members",
                        "item_id": member.get("id", ""),
                        "title": title or f"Персонаж группы {member.get('id', '')}",
                        "description": "",
                        "description_html": "",
                        "campaign_slug": slug,
                        "campaign_name": campaign.get("name", slug),
                        "url": url_for("party_page", campaign=slug, member=member.get("id", "")),
                    }
                )
                if len(items) >= limit:
                    return items
        return items

    def _fallback_notes(query: str, campaign_mode: str, allowed_campaigns: list[str], limit: int = 20) -> list[dict]:
        needle = query.strip().casefold()
        if len(needle) < 3:
            return []
        campaigns = views["get_campaigns"]()
        items = []
        for campaign in campaigns:
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            if campaign_mode == "selected" and slug not in allowed_campaigns:
                continue
            for note in views["prepare_notes"](slug):
                title = str(note.get("title", ""))
                body = str(note.get("content", "")) or str(note.get("body", ""))
                haystack = f"{title} {body}".casefold()
                if needle not in haystack:
                    continue
                items.append(
                    {
                        "kind": "notes",
                        "item_id": note.get("id", ""),
                        "title": title or f"Заметка {note.get('id', '')}",
                        "description": "",
                        "description_html": "",
                        "campaign_slug": slug,
                        "campaign_name": campaign.get("name", slug),
                        "url": url_for("notes_page", campaign=slug, q=title, note=note.get("id", "")),
                    }
                )
                if len(items) >= limit:
                    return items
        return items

    def _fallback_gods(query: str, campaign_mode: str, allowed_campaigns: list[str], limit: int = 20) -> list[dict]:
        needle = query.strip().casefold()
        if len(needle) < 3:
            return []
        items = []
        for campaign in views["get_campaigns"]():
            slug = str(campaign.get("slug", "")).strip()
            if not slug:
                continue
            if campaign_mode == "selected" and slug not in allowed_campaigns:
                continue
            for god in views["prepare_gods"](slug):
                title = str(god.get("name", ""))
                body = " ".join(
                    str(part)
                    for part in [
                        god.get("alignment", ""),
                        god.get("pantheon", ""),
                        god.get("symbol", ""),
                        god.get("source", ""),
                        " ".join(god.get("domains", []) or []),
                        god.get("description", ""),
                    ]
                    if part
                )
                if needle not in f"{title} {body}".casefold():
                    continue
                items.append(
                    {
                        "kind": "gods",
                        "item_id": god.get("id", ""),
                        "title": title or f"Божество {god.get('id', '')}",
                        "description": "",
                        "description_html": "",
                        "campaign_slug": slug,
                        "campaign_name": campaign.get("name", slug),
                        "url": url_for("gods_page", campaign=slug, q=title, god=god.get("id", "")),
                    }
                )
                if len(items) >= limit:
                    return items
        return items

    def spotlight_search():
        query = str(request.args.get("q", "")).strip()
        if len(query) < 3:
            return jsonify({"ok": True, "items": []})

        settings = views["load_settings"]()
        spotlight_settings = settings.get("spotlight", {}) if isinstance(settings, dict) else {}
        allowed_materials = spotlight_settings.get("materials", views["SPOTLIGHT_MATERIAL_OPTIONS"])
        if not isinstance(allowed_materials, list):
            allowed_materials = views["SPOTLIGHT_MATERIAL_OPTIONS"]

        campaign_mode = str(spotlight_settings.get("campaign_mode", "all")).strip().lower()
        allowed_campaigns = spotlight_settings.get("campaigns", [])
        if not isinstance(allowed_campaigns, list):
            allowed_campaigns = []

        entity_map = {
            "rules": "rules",
            "campaigns": "campaigns",
            "characters": "characters",
            "party_members": "party",
            "notes": "notes",
            "gods": "gods",
            "maps": "maps",
            "scenes": "scenes",
            "audio": "audio",
            "resources": "resources",
            "generators": "generators",
        }
        entity_types = [key for key, material in entity_map.items() if material in allowed_materials]
        # Keep notes searchable even if historical settings were saved before notes
        # existed in spotlight material options.
        if "notes" not in entity_types:
            entity_types.append("notes")
        if "gods" not in entity_types:
            entity_types.append("gods")
        if not entity_types:
            return jsonify({"ok": True, "items": []})

        campaigns = views["get_campaigns"]()
        campaign_names = {str(campaign.get("slug", "")): campaign.get("name", "") for campaign in campaigns}

        rows = views["storage"].search(query, entity_types=entity_types, limit=80)
        items = []
        for row in rows:
            entity_type = row.get("entity_type", "")
            item_id = row.get("item_id", "")
            campaign_slug = row.get("campaign_slug", "")
            title = row.get("title", "")
            campaign_name = campaign_names.get(campaign_slug, "")
            if campaign_mode == "selected" and campaign_slug and campaign_slug not in allowed_campaigns:
                continue
            if entity_type == "rules":
                items.append(
                    {
                        "kind": "rules",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": "",
                        "campaign_name": "",
                        "rule_id": item_id,
                        "url": url_for("rules_page", rule=item_id),
                    }
                )
            elif entity_type == "campaigns":
                items.append(
                    {
                        "kind": "campaigns",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": campaign_slug,
                        "campaign_name": campaign_name,
                        "url": url_for("campaign_detail", slug=campaign_slug or item_id),
                    }
                )
            elif entity_type == "maps":
                url = url_for("maps_page", q=title, campaign=campaign_slug) if campaign_slug else url_for("maps_page", q=title)
                items.append(
                    {
                        "kind": "maps",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": campaign_slug,
                        "campaign_name": campaign_name,
                        "url": url,
                    }
                )
            elif entity_type == "scenes":
                items.append(
                    {
                        "kind": "scenes",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": "",
                        "campaign_name": "",
                        "url": url_for("scenes_page", q=title),
                    }
                )
            elif entity_type == "audio":
                items.append(
                    {
                        "kind": "audio",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": "",
                        "campaign_name": "",
                        "url": url_for("audio_page", q=title),
                    }
                )
            elif entity_type == "resources":
                items.append(
                    {
                        "kind": "resources",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": "",
                        "campaign_name": "",
                        "url": url_for("resources_page", q=title),
                    }
                )
            elif entity_type == "generators":
                items.append(
                    {
                        "kind": "generators",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": "",
                        "campaign_name": "",
                        "url": url_for("generators_page", q=title),
                    }
                )
            elif entity_type == "characters":
                if not campaign_slug:
                    continue
                items.append(
                    {
                        "kind": "characters",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": campaign_slug,
                        "campaign_name": campaign_name,
                        "url": url_for("characters_page", campaign=campaign_slug, q=title, character=item_id),
                    }
                )
            elif entity_type == "notes":
                if not campaign_slug:
                    continue
                items.append(
                    {
                        "kind": "notes",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": campaign_slug,
                        "campaign_name": campaign_name,
                        "url": url_for("notes_page", campaign=campaign_slug, q=title, note=item_id),
                    }
                )
            elif entity_type == "gods":
                if not campaign_slug:
                    continue
                items.append(
                    {
                        "kind": "gods",
                        "item_id": item_id,
                        "title": title,
                        "description": "",
                        "description_html": "",
                        "campaign_slug": campaign_slug,
                        "campaign_name": campaign_name,
                        "url": url_for("gods_page", campaign=campaign_slug, q=title, god=item_id),
                    }
                )

        # Hard fallbacks for collections that live outside the SQLite FTS table.
        if "party_members" in entity_types:
            items.extend(_fallback_party_members(query, campaign_mode, allowed_campaigns, limit=20))
        if "notes" in entity_types and not any(item.get("kind") == "notes" for item in items):
            items.extend(_fallback_notes(query, campaign_mode, allowed_campaigns, limit=20))
        if "gods" in entity_types and not any(item.get("kind") == "gods" for item in items):
            items.extend(_fallback_gods(query, campaign_mode, allowed_campaigns, limit=20))
        return jsonify({"ok": True, "items": _sort_spotlight_items(items, query)})

    def spotlight_preview():
        kind = str(request.args.get("kind", "")).strip()
        item_id = str(request.args.get("id", "")).strip()
        campaign_slug = str(request.args.get("campaign", "")).strip()
        payload = _preview_payload(kind, item_id, campaign_slug)
        if payload is None:
            return jsonify({"ok": False, "error": "spotlight_preview_not_found"}), 404
        return jsonify(payload)

    bp.add_url_rule("/spotlight/search", endpoint="spotlight_search", view_func=spotlight_search, methods=["GET"])
    bp.add_url_rule("/spotlight/preview", endpoint="spotlight_preview", view_func=spotlight_preview, methods=["GET"])
