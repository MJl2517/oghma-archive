from pathlib import Path

from ogma.safe_urls import ExternalHttpUrl, UnsafeUrl

from ogma.foundry import normalize_foundry_relative_path


CHARACTER_GENDER_FALLBACK = "\u0418\u043d\u043e\u0435"
CHARACTER_ATTITUDE_FALLBACK = "\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e"


def map_url(map_item: dict, scope: str, campaign_slug: str, shared_url_builder, campaign_url_builder) -> str:
    if scope == "campaign":
        return campaign_url_builder(campaign_slug, map_item["id"])
    return shared_url_builder(map_item["id"])


def map_foundry_path(
    map_item: dict,
    scope: str,
    campaign_slug: str,
    foundry_assets_dir,
    get_campaign,
    campaign_foundry_slug,
) -> str:
    if scope == "campaign":
        campaign = get_campaign(campaign_slug)
        return normalize_foundry_relative_path(
            foundry_assets_dir(),
            "maps",
            "campaigns",
            campaign_foundry_slug(campaign or campaign_slug),
            map_item["filename"],
        )
    return normalize_foundry_relative_path(foundry_assets_dir(), "maps", "shared", map_item["filename"])


def scene_url(scene: dict, scene_url_builder) -> str:
    return scene_url_builder(scene["id"])


def scene_foundry_path(scene: dict, foundry_assets_dir) -> str:
    return normalize_foundry_relative_path(foundry_assets_dir(), "scenes", scene["filename"])


def audio_url(track: dict, audio_url_builder) -> str:
    if track.get("source_type") == "youtube":
        return track.get("url", "")
    return audio_url_builder(track["id"])


def resource_target(resource: dict) -> str:
    return resource.get("path", "") if resource.get("source_type") == "local" else resource.get("url", "")


def resource_type_label(resource: dict) -> str:
    return "\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0444\u0430\u0439\u043b" if resource.get("source_type") == "local" else "\u0421\u0441\u044b\u043b\u043a\u0430"


def character_url(character: dict, campaign_slug: str, character_url_builder) -> str:
    return character_url_builder(campaign_slug, character["id"])


def character_foundry_path(
    character: dict,
    campaign_slug: str,
    foundry_assets_dir,
    get_campaign,
    campaign_foundry_slug,
) -> str:
    campaign = get_campaign(campaign_slug)
    return normalize_foundry_relative_path(
        foundry_assets_dir(),
        "characters",
        "campaigns",
        campaign_foundry_slug(campaign or campaign_slug),
        character["filename"],
    )


def prepare_maps(
    scope: str,
    campaign_slug: str,
    load_maps,
    maps_directory,
    normalize_map_item_tags,
    shared_url_builder,
    campaign_url_builder,
    foundry_assets_dir,
    get_campaign,
    campaign_foundry_slug,
) -> list[dict]:
    prepared = []
    for item in load_maps(scope, campaign_slug):
        image_path = maps_directory(scope, campaign_slug) / item["filename"]
        if not image_path.exists():
            continue
        enriched = item.copy()
        enriched["tags"] = normalize_map_item_tags(item.get("tags", []))
        enriched["url"] = map_url(item, scope, campaign_slug, shared_url_builder, campaign_url_builder)
        enriched["foundry_path"] = map_foundry_path(
            item,
            scope,
            campaign_slug,
            foundry_assets_dir,
            get_campaign,
            campaign_foundry_slug,
        )
        prepared.append(enriched)
    return prepared


def prepare_scenes(load_scenes, scenes_directory, normalize_scene_item_tags, scene_url_builder, foundry_assets_dir) -> list[dict]:
    prepared = []
    for item in load_scenes():
        image_path = scenes_directory() / item["filename"]
        if not image_path.exists():
            continue
        enriched = item.copy()
        enriched["tags"] = normalize_scene_item_tags(item.get("tags", []))
        enriched["url"] = scene_url(item, scene_url_builder)
        enriched["foundry_path"] = scene_foundry_path(item, foundry_assets_dir)
        prepared.append(enriched)
    return prepared


def prepare_audio_tracks(load_audio_tracks, audio_directory, normalize_audio_item_tags, audio_url_builder, thumbnail_url_builder=None) -> list[dict]:
    prepared = []
    for item in load_audio_tracks():
        if item.get("source_type") == "file" and not (audio_directory() / item.get("filename", "")).exists():
            continue
        enriched = item.copy()
        enriched["tags"] = normalize_audio_item_tags(item.get("tags", []))
        enriched["url"] = audio_url(item, audio_url_builder)
        enriched["thumbnail_url"] = thumbnail_url_builder(item) if thumbnail_url_builder is not None else ""
        prepared.append(enriched)
    return prepared


def prepare_resources(load_resources, normalize_resource_type, normalize_resource_item_tags) -> list[dict]:
    prepared = []
    for item in load_resources():
        enriched = item.copy()
        enriched["source_type"] = normalize_resource_type(item.get("source_type", "web"))
        enriched["tags"] = normalize_resource_item_tags(item.get("tags", []))
        if enriched["source_type"] == "web":
            try:
                enriched["url"] = ExternalHttpUrl.parse(enriched.get("url", "")).value
                enriched["url_is_safe"] = True
            except UnsafeUrl:
                enriched["url"] = ""
                enriched["url_is_safe"] = False
            enriched["target"] = resource_target(enriched)
            enriched["exists"] = True
        else:
            raw_path = str(enriched.get("path", "")).strip()
            enriched["path_display"] = Path(raw_path).name if raw_path else ""
            enriched["target"] = enriched["path_display"]
            try:
                enriched["exists"] = Path(raw_path).resolve(strict=True).is_file() if raw_path else False
            except OSError:
                enriched["exists"] = False
            enriched.pop("path", None)
        enriched["type_label"] = resource_type_label(enriched)
        prepared.append(enriched)
    return prepared


def prepare_characters(
    campaign_slug: str,
    load_characters,
    characters_directory,
    character_category,
    character_tags,
    character_url_builder,
    foundry_assets_dir,
    get_campaign,
    campaign_foundry_slug,
) -> list[dict]:
    prepared = []
    for item in load_characters(campaign_slug):
        image_path = characters_directory(campaign_slug) / item["filename"]
        if not image_path.exists():
            continue
        enriched = {
            "age": "",
            "gender": CHARACTER_GENDER_FALLBACK,
            "race": "",
            "attitude": CHARACTER_ATTITUDE_FALLBACK,
            "notes": "",
            **item,
        }
        enriched["category"] = character_category(enriched)
        enriched["tags"] = character_tags(enriched)
        enriched["url"] = character_url(item, campaign_slug, character_url_builder)
        enriched["foundry_path"] = character_foundry_path(
            item,
            campaign_slug,
            foundry_assets_dir,
            get_campaign,
            campaign_foundry_slug,
        )
        prepared.append(enriched)
    return sorted(prepared, key=lambda character: character.get("name", "").casefold())


def find_by_id(items: list[dict], item_id: str) -> dict | None:
    return next((item for item in items if item["id"] == item_id), None)
