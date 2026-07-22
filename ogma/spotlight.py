def rule_search_items(rules: list[dict], service_rule_tag: str, summary_func) -> list[dict]:
    return [
        {
            "id": rule.get("id", ""),
            "title": rule.get("title", "Правило"),
            "tag": rule.get("tag", service_rule_tag),
            "source": rule.get("source", "Источник"),
            "summary": summary_func(rule.get("content", "")),
        }
        for rule in rules
    ]


def build_character_search_items(campaigns: list[dict], characters_by_campaign: dict[str, list[dict]], url_builder) -> list[dict]:
    search_items = []
    for campaign in campaigns:
        campaign_slug = campaign.get("slug", "")
        if not campaign_slug:
            continue
        for character in characters_by_campaign.get(campaign_slug, []):
            tags = character.get("tags", [])
            description_parts = [campaign.get("name", campaign_slug)]
            if tags:
                description_parts.append(", ".join(tags))
            terms = [
                "npc",
                "нпс",
                "персонаж",
                "неигровой",
                campaign.get("name", ""),
                campaign_slug,
                character.get("name", ""),
                character.get("race", ""),
                *tags,
            ]
            search_items.append(
                {
                    "id": character.get("id", ""),
                    "title": character.get("name", "NPC"),
                    "description": " · ".join(part for part in description_parts if part),
                    "terms": " ".join(str(term) for term in terms if term),
                    "campaign_slug": campaign_slug,
                    "url": url_builder(campaign_slug, character),
                }
            )
    return sorted(search_items, key=lambda item: item["title"].casefold())


def build_resource_search_items(resources: list[dict], url_builder) -> list[dict]:
    items = []
    for resource in resources:
        tags = resource.get("tags", [])
        terms = [
            "ресурс",
            "ссылка",
            "resource",
            resource.get("title", ""),
            resource.get("category", ""),
            resource.get("source_type", ""),
            *(tags or []),
        ]
        items.append(
            {
                "id": resource.get("id", ""),
                "title": resource.get("title", "Ресурс"),
                "description": resource.get("description", "") or resource.get("category", "Без категории"),
                "terms": " ".join(str(term) for term in terms if term),
                "url": url_builder(resource),
            }
        )
    return sorted(items, key=lambda item: item["title"].casefold())


def build_map_search_items(
    campaigns: list[dict],
    shared_maps: list[dict],
    campaign_maps_by_slug: dict[str, list[dict]],
    url_builder,
) -> list[dict]:
    items = []
    for map_item in shared_maps:
        tags = map_item.get("tags", [])
        terms = [
            "карта",
            "map",
            "shared",
            map_item.get("title", ""),
            *(tags or []),
        ]
        items.append(
            {
                "id": map_item.get("id", ""),
                "title": map_item.get("title", "Карта"),
                "description": " · ".join(tags[:3]) or "Общая карта",
                "terms": " ".join(str(term) for term in terms if term),
                "campaign_slug": "",
                "url": url_builder("", map_item),
            }
        )

    for campaign in campaigns:
        campaign_slug = campaign.get("slug", "")
        if not campaign_slug:
            continue
        for map_item in campaign_maps_by_slug.get(campaign_slug, []):
            tags = map_item.get("tags", [])
            terms = [
                "карта",
                "map",
                "campaign",
                campaign.get("name", ""),
                campaign_slug,
                map_item.get("title", ""),
                *(tags or []),
            ]
            items.append(
                {
                    "id": map_item.get("id", ""),
                    "title": map_item.get("title", "Карта"),
                    "description": f"{campaign.get('name', campaign_slug)} · " + (" · ".join(tags[:2]) or "Карта кампейна"),
                    "terms": " ".join(str(term) for term in terms if term),
                    "campaign_slug": campaign_slug,
                    "url": url_builder(campaign_slug, map_item),
                }
            )
    return sorted(items, key=lambda item: item["title"].casefold())


def build_scene_search_items(scenes: list[dict], url_builder) -> list[dict]:
    items = []
    for scene_item in scenes:
        tags = scene_item.get("tags", [])
        terms = [
            "раздат",
            "раздатка",
            "сцена",
            "scene",
            "арт",
            scene_item.get("title", ""),
            *(tags or []),
        ]
        items.append(
            {
                "id": scene_item.get("id", ""),
                "title": scene_item.get("title", "Раздат"),
                "description": " · ".join(tags[:3]) or "Раздаточный материал",
                "terms": " ".join(str(term) for term in terms if term),
                "url": url_builder(scene_item),
            }
        )
    return sorted(items, key=lambda item: item["title"].casefold())


def build_audio_search_items(tracks: list[dict], url_builder) -> list[dict]:
    items = []
    for track in tracks:
        tags = track.get("tags", [])
        source_type = track.get("source_type", "")
        category = track.get("category", "")
        terms = [
            "аудио",
            "audio",
            "музыка",
            source_type,
            category,
            track.get("title", ""),
            *(tags or []),
        ]
        items.append(
            {
                "id": track.get("id", ""),
                "title": track.get("title", "Аудио"),
                "description": " · ".join(part for part in [category, ", ".join(tags[:2])] if part) or "Аудио трек",
                "terms": " ".join(str(term) for term in terms if term),
                "url": url_builder(track),
            }
        )
    return sorted(items, key=lambda item: item["title"].casefold())


def build_note_search_items(campaigns: list[dict], notes_by_campaign: dict[str, list[dict]], url_builder) -> list[dict]:
    items = []
    for campaign in campaigns:
        campaign_slug = campaign.get("slug", "")
        if not campaign_slug:
            continue
        for note in notes_by_campaign.get(campaign_slug, []):
            title = note.get("title", "Сессия")
            body = note.get("body", "")
            status = note.get("status", "")
            session_number = note.get("session_number", "")
            terms = [
                "notes",
                "note",
                "заметка",
                "хроника",
                "сессия",
                campaign.get("name", ""),
                campaign_slug,
                title,
                status,
                str(session_number),
                body,
                *(note.get("tags", []) or []),
            ]
            items.append(
                {
                    "id": note.get("id", ""),
                    "title": title,
                    "description": f"{campaign.get('name', campaign_slug)} · {status}" if status else campaign.get("name", campaign_slug),
                    "terms": " ".join(str(term) for term in terms if term),
                    "campaign_slug": campaign_slug,
                    "url": url_builder(campaign_slug, note),
                }
            )
    return sorted(items, key=lambda item: item["title"].casefold())


def build_god_search_items(campaigns: list[dict], gods_by_campaign: dict[str, list[dict]], url_builder) -> list[dict]:
    items = []
    for campaign in campaigns:
        campaign_slug = campaign.get("slug", "")
        if not campaign_slug:
            continue
        for god in gods_by_campaign.get(campaign_slug, []):
            domains = god.get("domains", []) or []
            description_parts = [campaign.get("name", campaign_slug), god.get("alignment", "")]
            if domains:
                description_parts.append(", ".join(domains))
            terms = [
                "gods",
                "god",
                "deity",
                "бог",
                "боги",
                "божество",
                "пантеон",
                "домен",
                "мировоззрение",
                campaign.get("name", ""),
                campaign_slug,
                god.get("name", ""),
                god.get("alignment", ""),
                god.get("pantheon", ""),
                god.get("symbol", ""),
                god.get("source", ""),
                god.get("description", ""),
                *domains,
            ]
            items.append(
                {
                    "id": god.get("id", ""),
                    "title": god.get("name", "Божество"),
                    "description": " · ".join(part for part in description_parts if part),
                    "terms": " ".join(str(term) for term in terms if term),
                    "campaign_slug": campaign_slug,
                    "url": url_builder(campaign_slug, god),
                }
            )
    return sorted(items, key=lambda item: item["title"].casefold())
