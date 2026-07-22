import base64
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request
from uuid import uuid4

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from ogma.campaign_catalog import CampaignCatalog
from ogma.capabilities import DirectoryCapabilityStore, FileCapabilityStore
from ogma.foundry import ensure_junctions as ensure_foundry_spec_junctions
from ogma.foundry import link_statuses as foundry_spec_statuses
from ogma.foundry import normalize_foundry_relative_path
from ogma.foundry import remove_junction
from ogma.foundry import sync_summary as foundry_sync_summary
from ogma.external_http import ExternalHttpRejected, fetch_restricted, validate_restricted_https_url
from ogma.errors import ExternalOperationError, ValidationError
from ogma.json_store import read_json, write_json
from ogma.jobs import LocalJobBroker
from ogma.markdown import normalize_rule_reference
from ogma.markdown import render_note_content as render_note_content_markup
from ogma.markdown import render_rule_content as render_rule_content_markup
from ogma.markdown import render_text_content as render_text_content_markup
from ogma import media_catalog
from ogma.media import ALLOWED_AUDIO_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, DEFAULT_THUMBNAIL_MAX_SIDE, MAX_CLIPBOARD_IMAGE_SIDE
from ogma.media import copy_image_to_windows_clipboard as copy_image_to_windows_clipboard_service
from ogma.media import ensure_thumbnail, save_image_as_webp, save_uploaded_media_file
from ogma.security import configure_local_security
from ogma.safe_paths import (
    PathBoundaryError,
    normalize_relative_path,
    resolve_destination_under,
)
from ogma.safe_urls import EntityReference
from ogma.server_instance import ServerAlreadyRunningError, ServerInstanceLock
from ogma.settings_store import SettingsStore, THEME_OPTIONS
from ogma.runtime_paths import bundle_root, default_data_dir
from ogma.updater import UpdateManager
from ogma.version import APP_VERSION
from ogma import spotlight as spotlight_service
from ogma.services import favorites as favorite_service
from ogma.services import generators as generator_service
from ogma.storage import ArchiveStorage
from ogma.tags import append_unique_tag, delete_tag_from_list, load_category_list, load_tag_list, normalize_tags
from ogma.tags import order_tags_custom
from ogma.tags import remove_tag_from_items, reorder_existing_tags, save_category_list, save_tag_list
from ogma.tags import replace_item_field_value, sort_tags_alphabetically, visible_tags as collect_visible_tags
from routes import register_domain_routes

APP_NAME = "Архив Огмы"
SOURCE_DIR = Path(__file__).resolve().parent
BASE_DIR = bundle_root(SOURCE_DIR)
DATA_DIR = default_data_dir(SOURCE_DIR)
SHARED_DATA_DIR = DATA_DIR / "shared"
CAMPAIGNS_DIR = DATA_DIR / "campaigns"
CLIPBOARD_CACHE_DIR = DATA_DIR / ".cache" / "clipboard"
THUMBNAIL_CACHE_DIR = DATA_DIR / ".cache" / "thumbnails"
SETTINGS_PATH = DATA_DIR / "settings.json"
DEMO_STATE_PATH = DATA_DIR / "demo_state.json"
FOUNDRY_JUNCTION_REGISTRY_PATH = DATA_DIR / ".security" / "foundry-junctions.json"
DEFAULT_FOUNDRY_DATA_DIR = str(Path.home() / "AppData" / "Local" / "FoundryVTT" / "Data")
try:
    LOCAL_SERVER_PORT = int(os.getenv("OGMA_PORT", "5000"))
except ValueError:
    LOCAL_SERVER_PORT = 5000
if not 1 <= LOCAL_SERVER_PORT <= 65535:
    LOCAL_SERVER_PORT = 5000
DEFAULT_FOUNDRY_ASSETS_DIR = "assets/ogma"
SPOTLIGHT_MATERIAL_OPTIONS = [
    "maps",
    "scenes",
    "audio",
    "resources",
    "rules",
    "generators",
    "campaigns",
    "characters",
    "party",
    "notes",
    "gods",
]

SHARED_FOLDERS = [
    "rules",
    "maps",
    "scenes",
    "audio",
    "generators",
    "resources",
]

CAMPAIGN_FOLDERS = [
    "party",
    "characters",
    "notes",
    "gods",
    "cover",
]

DEFAULT_MAPS_PER_PAGE = 20
MAPS_PER_PAGE_OPTIONS = [20, 40, 80, 120]
DEFAULT_AUDIO_PER_PAGE = DEFAULT_MAPS_PER_PAGE
AUDIO_PER_PAGE_OPTIONS = MAPS_PER_PAGE_OPTIONS
DEFAULT_RESOURCES_PER_PAGE = 24
RESOURCES_PER_PAGE_OPTIONS = [24, 48, 96, 150]
DEFAULT_GENERATORS_PER_PAGE = 24
MEDIA_CACHE_SECONDS = 60 * 60 * 24 * 30

THEME_PAGE_ART = {
    "madness-crown": {
        "default": "img/themes/madness-crown/ruined-library.webp",
        "home": "img/themes/madness-crown/ruined-library.webp",
        "campaign": "img/themes/madness-crown/forgotten-archive.webp",
        "campaign-maps": "img/themes/madness-crown/archive-vault.webp",
        "maps": "img/themes/madness-crown/occult-observatory.webp",
        "scenes": "img/themes/madness-crown/ritual-archive.webp",
        "audio": "img/themes/madness-crown/scriptorium.webp",
        "rules": "img/themes/madness-crown/occult-study.webp",
        "gods": "img/themes/madness-crown/arcane-cathedral.webp",
        "generators": "img/themes/madness-crown/wizard-lab.webp",
        "resources": "img/themes/madness-crown/records-hall.webp",
        "characters": "img/themes/madness-crown/collapsed-university.webp",
        "party": "img/themes/madness-crown/collapsed-university.webp",
        "notes": "img/themes/madness-crown/stone-stacks.webp",
        "settings": "img/themes/madness-crown/archive-vault.webp",
    },
    "frost-ray": {
        "default": "img/themes/frost-ray/icy-mountains.webp",
        "home": "img/themes/frost-ray/icy-mountains.webp",
        "campaign": "img/themes/frost-ray/icebound-castle.webp",
        "campaign-maps": "img/themes/frost-ray/frozen-fortress.webp",
        "maps": "img/themes/frost-ray/glacier-canyon.webp",
        "scenes": "img/themes/frost-ray/moonlit-ice.webp",
        "audio": "img/themes/frost-ray/frozen-waterfall.webp",
        "rules": "img/themes/frost-ray/blue-ice-cave.webp",
        "gods": "img/themes/frost-ray/ice-cavern-plain.webp",
        "generators": "img/themes/frost-ray/arctic-shore.webp",
        "resources": "img/themes/frost-ray/freezing-coast.webp",
        "characters": "img/themes/frost-ray/snowy-valley.webp",
        "party": "img/themes/frost-ray/snowy-valley.webp",
        "notes": "img/themes/frost-ray/blizzard-valley.webp",
        "settings": "img/themes/frost-ray/frozen-fortress.webp",
    },
    "hadar-hunger": {
        "default": "img/themes/hadar-hunger/astral-vacuum.webp",
        "home": "img/themes/hadar-hunger/astral-vacuum.webp",
        "campaign": "img/themes/hadar-hunger/black-castle.webp",
        "campaign-maps": "img/themes/hadar-hunger/starless-fortress.webp",
        "maps": "img/themes/hadar-hunger/broken-bridge.webp",
        "scenes": "img/themes/hadar-hunger/void-rift.webp",
        "audio": "img/themes/hadar-hunger/astral-sea.webp",
        "rules": "img/themes/hadar-hunger/astral-storm.webp",
        "gods": "img/themes/hadar-hunger/astral-chapel.webp",
        "generators": "img/themes/hadar-hunger/cosmic-cavern.webp",
        "resources": "img/themes/hadar-hunger/void-observatory.webp",
        "characters": "img/themes/hadar-hunger/alien-field.webp",
        "party": "img/themes/hadar-hunger/alien-field.webp",
        "notes": "img/themes/hadar-hunger/star-haunted-field.webp",
        "settings": "img/themes/hadar-hunger/starless-fortress.webp",
    },
    "goodberry": {
        "default": "img/themes/goodberry/wild-grove.webp",
        "home": "img/themes/goodberry/wild-grove.webp",
        "campaign": "img/themes/goodberry/overgrown-sanctuary.webp",
        "campaign-maps": "img/themes/goodberry/druidic-circle.webp",
        "maps": "img/themes/goodberry/rushing-river.webp",
        "scenes": "img/themes/goodberry/magical-thicket.webp",
        "audio": "img/themes/goodberry/forest-spring.webp",
        "rules": "img/themes/goodberry/living-arch.webp",
        "gods": "img/themes/goodberry/moonlit-grove.webp",
        "generators": "img/themes/goodberry/living-ruins.webp",
        "resources": "img/themes/goodberry/woodland-shrine.webp",
        "characters": "img/themes/goodberry/wild-valley.webp",
        "party": "img/themes/goodberry/wild-valley.webp",
        "notes": "img/themes/goodberry/magical-ravine.webp",
        "settings": "img/themes/goodberry/overgrown-sanctuary.webp",
    },
    "shield-faith": {
        "default": "img/themes/shield-faith/golden-castle.webp",
        "home": "img/themes/shield-faith/golden-castle.webp",
        "campaign": "img/themes/shield-faith/hilltop-sanctuary.webp",
        "campaign-maps": "img/themes/shield-faith/fortified-church.webp",
        "maps": "img/themes/shield-faith/golden-fields.webp",
        "scenes": "img/themes/shield-faith/golden-courtyard.webp",
        "audio": "img/themes/shield-faith/cathedral-nave.webp",
        "rules": "img/themes/shield-faith/grand-church.webp",
        "gods": "img/themes/shield-faith/oath-hall.webp",
        "generators": "img/themes/shield-faith/church-library.webp",
        "resources": "img/themes/shield-faith/sunlit-monastery.webp",
        "characters": "img/themes/shield-faith/pilgrim-road.webp",
        "party": "img/themes/shield-faith/pilgrim-road.webp",
        "notes": "img/themes/shield-faith/country-church.webp",
        "settings": "img/themes/shield-faith/fortified-church.webp",
    },
}
GENERATORS_PER_PAGE_OPTIONS = [24, 48, 96, 150]
DEFAULT_RULE_TAGS = [
    "Действие [Action]",
    "Движение [Move]",
    "Сражение [Combat]",
    "Урон и атака [Damage and Attack]",
    "Состояния [Conditions]",
    "Характеристики и Навыки [Stats and Skills]",
    "Заклинания [Spells]",
    "Снаряжение [Equipment]",
    "Окружающая среда [Environment]",
    "Опасности и ловушки [Hazards and Traps]",
    "Монстры и существа [Monsters and Creatures]",
    "Без категории",
]
SERVICE_RULE_TAG = "Без категории"
DEFAULT_RULE_SOURCES = ["PHB", "DMG", "MM", "XGE", "TCE", "Homebrew"]
DEFAULT_MAP_TAGS = [
    "Неотсортированные",
    "Пустыни",
    "Леса",
    "Поля",
    "Реки",
    "Руины",
    "Города",
    "Подземелья",
    "Пещеры",
    "Болота",
    "Горы",
    "Снег",
    "Дороги",
    "Интерьеры",
]
REQUIRED_MAP_TAGS = ["Неотсортированные"]
UNSORTED_MAP_TAG = REQUIRED_MAP_TAGS[0]
DEFAULT_SCENE_TAGS = [
    "Неотсортированные",
    "Атмосфера",
    "Локации",
    "Города",
    "Подземелья",
    "Природа",
    "Монстры",
    "Предметы",
]
REQUIRED_SCENE_TAGS = ["Неотсортированные"]
UNSORTED_SCENE_TAG = REQUIRED_SCENE_TAGS[0]
DEFAULT_AUDIO_CATEGORIES = ["Музыка", "Эмбиент", "Прочее"]
DEFAULT_AUDIO_TAGS = [
    "Неотсортированные",
    "Бой",
    "Напряжение",
    "Природа",
    "Город",
    "Торговля",
    "Пустыня",
    "Весёлое",
    "Хитрое",
    "Страшное",
    "Таверна",
    "Путешествие",
    "Подземелье",
    "Мистика",
]
REQUIRED_AUDIO_TAGS = ["Неотсортированные"]
UNSORTED_AUDIO_TAG = REQUIRED_AUDIO_TAGS[0]
DEFAULT_RESOURCE_CATEGORIES = ["Книги", "Сайты", "Инструменты", "Материалы", "Прочее"]
DEFAULT_RESOURCE_TAGS = [
    "Неотсортированные",
    "Правила",
    "Справочник",
    "Генератор",
    "Лор",
    "Карты",
    "Персонажи",
    "Подготовка",
    "Homebrew",
    "D&D 5e",
]
REQUIRED_RESOURCE_TAGS = ["Неотсортированные"]
UNSORTED_RESOURCE_TAG = REQUIRED_RESOURCE_TAGS[0]
DEFAULT_GENERATOR_CATEGORIES = ["Погода", "События", "Имена", "Сокровища", "Прочее"]
DEFAULT_GENERATOR_TAGS = ["Неотсортированные", "Путешествие", "Город", "Подземелье", "Социалка", "Бой"]
REQUIRED_GENERATOR_TAGS = ["Неотсортированные"]
UNSORTED_GENERATOR_TAG = REQUIRED_GENERATOR_TAGS[0]
RESOURCE_SORT_OPTIONS = {
    "title": "Название",
    "category": "Категория",
    "type": "Тип",
    "updated": "Обновлено",
    "created": "Создано",
}
DEFAULT_CHARACTER_GROUPS = [
    "Неотсортированные",
    "NPC",
    "Союзники",
    "Враги",
    "Нейтральные",
]
REQUIRED_CHARACTER_GROUPS = ["Неотсортированные"]
UNSORTED_CHARACTER_GROUP = REQUIRED_CHARACTER_GROUPS[0]
DEFAULT_CHARACTER_TAGS = DEFAULT_CHARACTER_GROUPS
REQUIRED_CHARACTER_TAGS = REQUIRED_CHARACTER_GROUPS
UNSORTED_CHARACTER_TAG = UNSORTED_CHARACTER_GROUP
CHARACTER_ATTITUDES = ["Неизвестно", "Дружелюбный", "Враждебный", "Нейтральный"]
CHARACTER_GENDERS = ["М", "Ж", "Иное"]
DEFAULT_NOTE_TAGS = ["Неотсортированные", "Сюжет", "NPC", "Локация", "Бой", "Исследование", "Социалка"]
REQUIRED_NOTE_TAGS = ["Неотсортированные"]
UNSORTED_NOTE_TAG = REQUIRED_NOTE_TAGS[0]
LEGACY_NOTE_TAGS = {"codexsession"}
DEFAULT_GOD_DOMAINS = [
    "Знание",
    "Жизнь",
    "Свет",
    "Природа",
    "Буря",
    "Обман",
    "Война",
    "Смерть",
    "Магия",
]
DEFAULT_GOD_RANKS = [
    "абсолютное божество",
    "великое божество",
    "среднее божество",
    "младшее божество",
    "полу-бог",
    "квази-бог",
    "мертвое божество",
]
DEFAULT_GOD_ALIGNMENTS = [
    "Законно-доброе",
    "Нейтрально-доброе",
    "Хаотично-доброе",
    "Законно-нейтральное",
    "Нейтральное",
    "Хаотично-нейтральное",
    "Законно-злое",
    "Нейтрально-злое",
    "Хаотично-злое",
    "Не указано",
]
FALLBACK_GOD_ALIGNMENT = "Не указано"
DEFAULT_NOTES_LIMIT = 20
NOTES_LIMIT_STEP = 20
MAX_NOTES_LIMIT = 200
NOTE_TYPES = ["Сессия"]
NOTE_STATUSES = ["В планах", "Проведена"]
NOTE_SORT_OPTIONS = {
    "session": "Свежие сверху",
}

SECTIONS = [
    {
        "slug": "maps",
        "title": "Карты",
        "eyebrow": "Локации и поля боя",
        "description": "Боевые карты, регионы, города и планы локаций. Могут быть общими или привязанными к кампейну.",
        "accent": "brass",
        "icon": "map",
        "search_terms": ["карта", "локация", "город", "подземелье", "scene", "battlemap"],
    },
    {
        "slug": "scenes",
        "title": "Раздат",
        "eyebrow": "Материалы для игроков",
        "description": "Иллюстрации, handouts, портреты, подсказки и любые материалы, которые можно быстро показать или выдать игрокам.",
        "accent": "moon",
        "icon": "handout",
        "search_terms": ["раздат", "раздатка", "сцена", "арт", "иллюстрация", "handout", "изображение", "показать игрокам"],
    },
    {
        "slug": "audio",
        "title": "Аудио",
        "eyebrow": "Музыка и атмосфера",
        "description": "Треки, эмбиент и YouTube-ссылки для сессий: категории, теги, пакетная загрузка и быстрый запуск.",
        "accent": "verdigris",
        "icon": "audio",
        "search_terms": ["аудио", "музыка", "эмбиент", "трек", "youtube", "саундтрек", "звук"],
    },
    {
        "slug": "characters",
        "title": "Неигровые персонажи",
        "eyebrow": "NPC",
        "description": "Арты, портреты, связи, заметки и игровые данные союзников, врагов, нейтральных и важных NPC.",
        "accent": "ember",
        "icon": "mask",
        "search_terms": ["персонаж", "npc", "нпс", "арт", "портрет", "злодей"],
        "campaign_only": True,
    },
    {
        "slug": "party",
        "title": "Группа",
        "eyebrow": "Игроки",
        "description": "Листы игроков, состав партии, прогресс, ресурсы и общий статус приключения. Раздел пока в разработке.",
        "accent": "verdigris",
        "icon": "rune",
        "search_terms": ["группа", "игроки", "партия", "персонажи игроков", "party"],
        "campaign_only": True,
    },
    {
        "slug": "notes",
        "title": "Хроника сессий",
        "eyebrow": "Журнал партии",
        "description": "Прошедшие и грядущие сессии кампейна: планы, итоги, markdown-записи и связанные NPC, карты и раздат.",
        "accent": "ink",
        "icon": "quill",
        "search_terms": ["сессия", "хроника", "журнал", "партия", "план", "итоги"],
        "campaign_only": True,
    },
    {
        "slug": "gods",
        "title": "Боги",
        "eyebrow": "Пантеон",
        "description": "Каталог богов кампейна: мировоззрения, домены, символы, пантеоны и мастерские заметки.",
        "accent": "gold",
        "icon": "rune",
        "search_terms": ["боги", "бог", "пантеон", "домен", "мировоззрение", "deity", "god"],
        "campaign_only": True,
    },
    {
        "slug": "rules",
        "title": "Глоссарий правил",
        "eyebrow": "RAW и быстрый поиск",
        "description": "База правил D&D 5e для поиска формулировок, состояний, действий, заклинаний и исключений.",
        "accent": "verdigris",
        "icon": "book",
        "search_terms": ["правила", "raw", "глоссарий", "условия", "действия", "заклинание"],
    },
    {
        "slug": "generators",
        "title": "Генераторы",
        "eyebrow": "Таблицы и случайности",
        "description": "Сокровища, имена, слухи, сюжетные зацепки, энкаунтеры и броски по мастерским таблицам.",
        "accent": "gold",
        "icon": "dice",
        "search_terms": ["генератор", "сокровища", "имя", "зацепка", "таблица", "случайный"],
    },
    {
        "slug": "resources",
        "title": "Ресурсы",
        "eyebrow": "Книги и ссылки",
        "description": "PDF, внешние ссылки, справочники, домашние правила и материалы, которые нужны под рукой.",
        "accent": "moon",
        "icon": "resource",
        "search_terms": ["ресурс", "pdf", "книга", "ссылка", "справочник", "материал"],
    },
]

GLOBAL_SECTIONS = [section for section in SECTIONS if not section.get("campaign_only")]
CAMPAIGN_SECTIONS = [section for section in SECTIONS if section.get("campaign_only")]

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", os.getenv("OGMA_STORAGE_BACKEND", "sqlite")).strip().lower() or "sqlite"
if STORAGE_BACKEND not in {"json", "sqlite"}:
    STORAGE_BACKEND = "sqlite"

STATIC_IMAGE_CACHE_SECONDS = 60 * 60 * 24 * 30
STATIC_ASSET_CACHE_SECONDS = 60 * 60 * 24 * 7
STATIC_DEFAULT_CACHE_SECONDS = 60 * 60
STATIC_IMAGE_EXTENSIONS = {".avif", ".gif", ".ico", ".jpg", ".jpeg", ".png", ".svg", ".webp"}
STATIC_FONT_EXTENSIONS = {".eot", ".otf", ".ttf", ".woff", ".woff2"}
STATIC_SCRIPT_STYLE_EXTENSIONS = {".css", ".js", ".mjs"}


class OgmaFlask(Flask):
    def get_send_file_max_age(self, name: str | None) -> int:
        suffix = Path(name or "").suffix.lower()
        if suffix in STATIC_IMAGE_EXTENSIONS or suffix in STATIC_FONT_EXTENSIONS:
            return STATIC_IMAGE_CACHE_SECONDS
        if suffix in STATIC_SCRIPT_STYLE_EXTENSIONS:
            return STATIC_ASSET_CACHE_SECONDS
        return STATIC_DEFAULT_CACHE_SECONDS


storage = ArchiveStorage(DATA_DIR, SHARED_FOLDERS, CAMPAIGN_FOLDERS, backend=STORAGE_BACKEND)
file_capabilities = FileCapabilityStore()
directory_capabilities = DirectoryCapabilityStore()
local_jobs = LocalJobBroker()
campaign_catalog = CampaignCatalog(
    CAMPAIGNS_DIR,
    CAMPAIGN_FOLDERS,
    storage.campaign_metadata_path,
    storage.campaign_cover_directory,
    ALLOWED_IMAGE_EXTENSIONS,
)
settings_store = SettingsStore(
    DATA_DIR,
    SETTINGS_PATH,
    DEFAULT_FOUNDRY_DATA_DIR,
    DEFAULT_FOUNDRY_ASSETS_DIR,
    SPOTLIGHT_MATERIAL_OPTIONS,
)
update_manager = UpdateManager(DATA_DIR, BASE_DIR, APP_VERSION)
app = OgmaFlask(__name__)
configure_local_security(app, DATA_DIR, LOCAL_SERVER_PORT)


class DemoStateLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /demo/state " not in record.getMessage()


logging.getLogger("werkzeug").addFilter(DemoStateLogFilter())


def ensure_storage() -> None:
    """Create the first-pass archive structure without touching user files."""
    storage.ensure()
    if not SETTINGS_PATH.exists():
        save_settings(default_settings())


def slugify_campaign_name(name: str) -> str:
    return campaign_catalog.slugify(name)


campaign_metadata_path = storage.campaign_metadata_path
campaign_cover_directory = storage.campaign_cover_directory


def default_settings() -> dict:
    return settings_store.default()


def merge_settings(settings: dict) -> dict:
    return settings_store.merge(settings)


def favorite_campaign_slug() -> str:
    return str(load_settings().get("favorites", {}).get("campaign_slug", "")).strip()


def favorite_campaign_nav_group() -> dict | None:
    slug = favorite_campaign_slug()
    if not slug:
        return None
    campaign = get_campaign(slug)
    if campaign is None:
        return None
    links = [
        {"title": item["title"], "url": url_for("section", slug=item["slug"], campaign=slug)}
        for item in CAMPAIGN_SECTIONS
    ]
    return {"slug": slug, "name": campaign.get("name", slug), "url": url_for("campaign_detail", slug=slug), "links": links}


def load_settings() -> dict:
    return settings_store.load()


def save_settings(settings: dict) -> None:
    settings_store.save(settings)


def issue_file_capability(path: str) -> tuple[str, str]:
    return file_capabilities.issue(path)


def resolve_file_capability(token: str) -> Path:
    return file_capabilities.consume(token)


def issue_directory_capability(path: str) -> tuple[str, str]:
    return directory_capabilities.issue(path)


def resolve_directory_capability(token: str) -> Path:
    return directory_capabilities.consume(token)


def start_local_job(kind: str, operation) -> str:
    return local_jobs.start(kind, operation)


def local_job_status(job_id: str) -> dict:
    return local_jobs.status(job_id)


def update_status() -> dict:
    return update_manager.local_status()


def check_for_updates() -> dict:
    return update_manager.check_latest(force=True)


def download_update() -> dict:
    return update_manager.download_latest()


def install_update() -> dict:
    return update_manager.launch_prepared_installer()


def foundry_settings() -> dict:
    return settings_store.foundry()


def foundry_data_dir() -> Path:
    return settings_store.foundry_data_dir()


def foundry_assets_dir() -> str:
    return settings_store.foundry_assets_dir()


def get_campaigns() -> list[dict]:
    campaigns = storage.load_campaigns()
    for campaign in campaigns:
        slug = str(campaign.get("slug", "")).strip()
        campaign.setdefault("foundry_slug", slug)
        if campaign.get("cover_image"):
            campaign["cover_url"] = url_for("serve_campaign_cover", campaign_slug=slug)
    return sorted(campaigns, key=lambda item: item.get("created_at", ""), reverse=True)


def campaign_foundry_slug(campaign_or_slug: dict | str | None) -> str:
    return campaign_catalog.foundry_slug(campaign_or_slug)


def get_campaign(slug: str) -> dict | None:
    for campaign in storage.load_campaigns():
        if campaign.get("slug") != slug:
            continue
        campaign = campaign.copy()
        campaign.setdefault("foundry_slug", slug)
        if campaign.get("cover_image"):
            campaign["cover_url"] = url_for("serve_campaign_cover", campaign_slug=slug)
        return campaign
    return None


def create_campaign(name: str, description: str = "", system: str = "") -> dict:
    base_slug = slugify_campaign_name(name)
    slug = base_slug
    counter = 2
    campaigns = storage.load_campaigns()
    existing_slugs = {str(item.get("slug", "")) for item in campaigns}
    while slug in existing_slugs or (CAMPAIGNS_DIR / slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    campaign_dir = CAMPAIGNS_DIR / slug
    campaign_dir.mkdir(parents=True, exist_ok=False)
    for folder in CAMPAIGN_FOLDERS:
        (campaign_dir / folder).mkdir(exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    campaign = {
        "slug": slug,
        "foundry_slug": slug,
        "name": name.strip(),
        "description": description.strip(),
        "system": system.strip(),
        "created_at": now,
        "updated_at": now,
        "folders": CAMPAIGN_FOLDERS,
    }
    storage.save_campaign(campaign)
    return campaign


def update_campaign(slug: str, name: str, description: str = "", system: str = "") -> dict | None:
    campaigns = storage.load_campaigns()
    updated = None
    for campaign in campaigns:
        if campaign.get("slug") != slug:
            continue
        campaign["name"] = name.strip() or campaign.get("name", slug)
        campaign["description"] = description.strip()
        campaign["system"] = system.strip()
        campaign["foundry_slug"] = campaign_foundry_slug(campaign) or slug
        campaign["updated_at"] = datetime.now().isoformat(timespec="seconds")
        updated = campaign
        break
    if updated is None:
        return None
    storage.save_campaign(updated)
    return updated.copy()


def save_campaign_cover(slug: str, uploaded_file) -> str | None:
    return campaign_catalog.save_cover(slug, uploaded_file)


def delete_campaign_cover(slug: str) -> None:
    campaign_catalog.delete_cover(slug)


def set_campaign_cover(slug: str, cover_image: str = "") -> dict | None:
    campaigns = storage.load_campaigns()
    updated = None
    for campaign in campaigns:
        if campaign.get("slug") != slug:
            continue
        if cover_image:
            campaign["cover_image"] = cover_image
        else:
            campaign.pop("cover_image", None)
        campaign["updated_at"] = datetime.now().isoformat(timespec="seconds")
        updated = campaign
        break
    if updated is None:
        return None
    storage.save_campaign(updated)
    return updated.copy()


def delete_campaign_record(slug: str) -> None:
    raise RuntimeError(
        "Permanent campaign deletion is disabled until recoverable soft-delete and backup are implemented."
    )


def get_section(slug: str) -> dict | None:
    return next((section for section in SECTIONS if section["slug"] == slug), None)


def allowed_open_folder(folder_key: str) -> Path | None:
    if folder_key.startswith("shared:"):
        folder = folder_key.split(":", 1)[1]
        if folder in SHARED_FOLDERS:
            return SHARED_DATA_DIR / folder

    settings = load_settings()
    folders = {
        "shared": SHARED_DATA_DIR,
        "campaigns": CAMPAIGNS_DIR,
        "foundry-data": Path(settings["foundry"]["data_dir"]),
        "foundry-assets": Path(settings["foundry"]["data_dir"]) / settings["foundry"]["assets_dir"],
    }
    return folders.get(folder_key)


def normalize_map_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_MAP_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_MAP_TAG]


def normalize_scene_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_SCENE_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_SCENE_TAG]


def normalize_audio_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_AUDIO_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_AUDIO_TAG]


def normalize_audio_category(raw_category) -> str:
    value = str(raw_category or "").strip()
    if not value:
        return DEFAULT_AUDIO_CATEGORIES[0]
    categories = load_audio_categories()
    match = next((category for category in categories if category.casefold() == value.casefold()), None)
    return match or value


def is_youtube_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    host = parsed.netloc.casefold()
    return parsed.scheme in {"http", "https"} and (
        host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}
        or host.endswith(".youtube.com")
    )


def canonical_youtube_oembed_url(value: str) -> str:
    parsed = urlparse((value or "").strip())
    host = parsed.netloc.casefold()
    path_parts = [part for part in parsed.path.split("/") if part]
    video_id = ""

    if host == "youtu.be" and path_parts:
        video_id = path_parts[0]
    elif path_parts and path_parts[0] in {"shorts", "embed", "live", "v"} and len(path_parts) > 1:
        video_id = path_parts[1]
    else:
        video_id = parse_qs(parsed.query).get("v", [""])[0]

    if re.fullmatch(r"[\w-]{11}", video_id or ""):
        return f"https://www.youtube.com/watch?v={video_id}"
    return (value or "").strip()


def youtube_video_id(value: str) -> str:
    canonical_url = canonical_youtube_oembed_url(value)
    parsed = urlparse(canonical_url)
    return parse_qs(parsed.query).get("v", [""])[0]


def fetch_youtube_metadata(url: str) -> dict:
    if not is_youtube_url(url):
        return {}
    endpoint = "https://www.youtube.com/oembed?" + urlencode({"url": canonical_youtube_oembed_url(url), "format": "json"})
    try:
        request_data = Request(
            endpoint,
            headers={
                "Accept": "application/json",
                "Accept-Language": "ru,en;q=0.8",
                "User-Agent": "Mozilla/5.0 OghmaArchive/1.0",
            },
        )
        response_data = fetch_restricted(
            request_data,
            allowed_hosts={"www.youtube.com"},
            allowed_content_types={"application/json"},
            maximum_bytes=256 * 1024,
            timeout_seconds=4,
        )
        payload = json.loads(response_data.decode("utf-8"))
    except (ExternalHttpRejected, OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def fetch_youtube_title(url: str) -> str:
    return str(fetch_youtube_metadata(url).get("title") or "").strip()


def save_youtube_thumbnail(url: str, thumbnail_url: str = "") -> str:
    if not is_youtube_url(url):
        return ""
    video_id = youtube_video_id(url)
    if not video_id:
        return ""
    source_url = str(thumbnail_url or "").strip()
    if not source_url:
        source_url = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
    try:
        source_url = validate_restricted_https_url(
            source_url,
            {"i.ytimg.com", "img.youtube.com"},
        )
    except ExternalHttpRejected:
        return ""
    target_dir = audio_directory() / "youtube-thumbnails"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{video_id}.webp"
    target_path = target_dir / filename
    try:
        request_data = Request(
            source_url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 OghmaArchive/1.0",
            },
        )
        image_data = fetch_restricted(
            request_data,
            allowed_hosts={"i.ytimg.com", "img.youtube.com"},
            allowed_content_types={"image/jpeg", "image/png", "image/webp"},
            maximum_bytes=1_500_000,
            timeout_seconds=6,
        )
        if not image_data:
            return ""
        save_image_as_webp(BytesIO(image_data), target_path)
    except Exception:
        target_path.unlink(missing_ok=True)
        return ""
    return f"youtube-thumbnails/{filename}"


def delete_audio_thumbnail(thumbnail_filename: str) -> None:
    clean_name = str(thumbnail_filename or "").strip()
    if not clean_name:
        return
    target_path = (audio_directory() / clean_name).resolve()
    thumbnail_root = (audio_directory() / "youtube-thumbnails").resolve()
    try:
        target_path.relative_to(thumbnail_root)
    except ValueError:
        return
    if target_path.exists() and target_path.is_file():
        target_path.unlink()


def normalize_character_category(raw_category) -> str:
    groups = normalize_tags(raw_category)
    non_service_groups = [group for group in groups if group.casefold() != UNSORTED_CHARACTER_GROUP.casefold()]
    return (non_service_groups or [UNSORTED_CHARACTER_GROUP])[0]


def normalize_character_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_CHARACTER_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_CHARACTER_TAG]


def normalize_note_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_NOTE_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_NOTE_TAG]


def normalize_god_domains(raw_domains) -> list[str]:
    return sort_tags_alphabetically(normalize_tags(raw_domains))


def normalize_god_alignment(raw_alignment) -> str:
    alignment = str(raw_alignment or "").strip()
    if not alignment:
        return FALLBACK_GOD_ALIGNMENT
    match = next((item for item in load_god_alignments_raw() if item.casefold() == alignment.casefold()), None)
    return match or alignment


def character_category(item: dict) -> str:
    category = item.get("category") or normalize_character_category(item.get("groups", []))
    if category.casefold() == "игроки":
        return UNSORTED_CHARACTER_GROUP
    return category


def character_tags(item: dict) -> list[str]:
    raw_tags = item.get("tags")
    if raw_tags:
        return normalize_character_item_tags(raw_tags)
    return normalize_character_item_tags([character_category(item)])


maps_directory = storage.maps_directory
scenes_directory = storage.scenes_directory
audio_directory = storage.audio_directory
resources_directory = storage.resources_directory
characters_directory = storage.characters_directory
notes_directory = storage.notes_directory
gods_directory = storage.gods_directory
rules_directory = storage.rules_directory
maps_metadata_path = storage.maps_metadata_path
scenes_metadata_path = storage.scenes_metadata_path
audio_metadata_path = storage.audio_metadata_path
resources_metadata_path = storage.resources_metadata_path
characters_metadata_path = storage.characters_metadata_path
notes_metadata_path = storage.notes_metadata_path
gods_metadata_path = storage.gods_metadata_path
rules_metadata_path = storage.rules_metadata_path
maps_tags_path = storage.maps_tags_path
scenes_tags_path = storage.scenes_tags_path
audio_tags_path = storage.audio_tags_path
audio_categories_path = storage.audio_categories_path
resources_tags_path = storage.resources_tags_path
resources_categories_path = storage.resources_categories_path
characters_groups_path = storage.characters_groups_path
characters_tags_path = storage.characters_tags_path
notes_tags_path = storage.notes_tags_path
gods_domains_path = storage.gods_domains_path
gods_alignments_path = storage.gods_alignments_path
rules_tags_path = storage.rules_tags_path
rules_sources_path = storage.rules_sources_path


def load_rule_tags() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("rules:tags", DEFAULT_RULE_TAGS, scope="shared")
        excluded_keys = {SERVICE_RULE_TAG.casefold()}
        return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in excluded_keys], [SERVICE_RULE_TAG])
    return load_tag_list(rules_tags_path(), DEFAULT_RULE_TAGS, [SERVICE_RULE_TAG])


def save_rule_tags(tags: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("rules:tags", order_tags_custom(tags, [SERVICE_RULE_TAG]), scope="shared")
        return
    save_tag_list(rules_tags_path(), tags, [SERVICE_RULE_TAG])


def load_rule_sources() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        return normalize_tags(storage.load_labels("rules:sources", DEFAULT_RULE_SOURCES, scope="shared"))
    sources_path = rules_sources_path()
    if sources_path.exists():
        return normalize_tags(read_json(sources_path, fallback=[]))
    return DEFAULT_RULE_SOURCES[:]


def save_rule_sources(sources: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("rules:sources", normalize_tags(sources), scope="shared")
        return
    write_json(rules_sources_path(), normalize_tags(sources))


def default_rules() -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    return [
        {
            "id": "sample-advantage",
            "title": "Преимущество и помеха",
            "tag": "Характеристики и Навыки [Stats and Skills]",
            "source": "PHB",
            "book_url": "",
            "page": "173",
            "content": (
                "Короткая карточка-заготовка для будущей RAW-выдержки. "
                "Здесь можно хранить полный текст правила, заметки мастера и ссылки на связанные материалы.\n\n"
                "| Ситуация | Что бросается |\n"
                "| --- | --- |\n"
                "| Преимущество | 2d20, выбирается большее |\n"
                "| Помеха | 2d20, выбирается меньшее |"
            ),
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "sample-cover",
            "title": "Укрытие",
            "tag": "Сражение [Combat]",
            "source": "PHB",
            "book_url": "",
            "page": "196",
            "content": (
                "Заготовка для правила об укрытии. Текст можно заменить на точную выдержку из нужной книги.\n\n"
                "Изображения поддерживаются строкой вида `![схема укрытия](/static/img/example.png)`."
            ),
            "created_at": now,
            "updated_at": now,
        },
    ]


def load_rules() -> list[dict]:
    rules = storage.load_rules()
    if rules is None:
        rules = default_rules()
        save_rules(rules)
    return rules


def rule_plain_summary(content: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    return text[:limit].rstrip() + ("..." if len(text) > limit else "")


def rule_search_items() -> list[dict]:
    return spotlight_service.rule_search_items(load_rules(), SERVICE_RULE_TAG, rule_plain_summary)


def save_rules(rules: list[dict]) -> None:
    storage.save_rules(rules)


def save_rule_item(rule: dict) -> None:
    storage.save_rule_item(rule)


def delete_rule_item(rule_id: str) -> bool:
    return storage.delete_rule_item(rule_id)


def replace_rule_field_value(field: str, old_value: str, new_value: str, updated_at: str) -> list[str]:
    return storage.replace_rule_field_value(field, old_value, new_value, updated_at)


def find_rule(rule_id: str) -> dict | None:
    return next((rule for rule in load_rules() if rule.get("id") == rule_id), None)


load_maps = storage.load_maps
save_maps = storage.save_maps
load_scenes = storage.load_scenes
save_scenes = storage.save_scenes
load_audio_tracks = storage.load_audio_tracks
save_audio_tracks = storage.save_audio_tracks
load_resources = storage.load_resources
save_resources = storage.save_resources
load_generators = storage.load_generators
load_generator = storage.load_generator
save_generators = storage.save_generators


def load_map_tags(scope: str, campaign_slug: str = "") -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("maps:tags", DEFAULT_MAP_TAGS, scope=scope, campaign_slug=campaign_slug if scope == "campaign" else "")
        required_keys = {tag.casefold() for tag in REQUIRED_MAP_TAGS}
        return sort_tags_alphabetically([tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys], REQUIRED_MAP_TAGS)
    return sort_tags_alphabetically(load_tag_list(maps_tags_path(scope, campaign_slug), DEFAULT_MAP_TAGS, REQUIRED_MAP_TAGS), REQUIRED_MAP_TAGS)


def load_scene_tags() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("scenes:tags", DEFAULT_SCENE_TAGS, scope="shared")
        required_keys = {tag.casefold() for tag in REQUIRED_SCENE_TAGS}
        return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys], REQUIRED_SCENE_TAGS)
    return load_tag_list(scenes_tags_path(), DEFAULT_SCENE_TAGS, REQUIRED_SCENE_TAGS)


def save_map_tags(scope: str, tags: list[str], campaign_slug: str = "") -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("maps:tags", sort_tags_alphabetically(tags, REQUIRED_MAP_TAGS), scope=scope, campaign_slug=campaign_slug if scope == "campaign" else "")
        return
    save_tag_list(maps_tags_path(scope, campaign_slug), sort_tags_alphabetically(tags, REQUIRED_MAP_TAGS), REQUIRED_MAP_TAGS)


def save_scene_tags(tags: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("scenes:tags", order_tags_custom(tags, REQUIRED_SCENE_TAGS), scope="shared")
        return
    save_tag_list(scenes_tags_path(), tags, REQUIRED_SCENE_TAGS)


def load_audio_tags() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("audio:tags", DEFAULT_AUDIO_TAGS, scope="shared")
        required_keys = {tag.casefold() for tag in REQUIRED_AUDIO_TAGS}
        return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys], REQUIRED_AUDIO_TAGS)
    return load_tag_list(audio_tags_path(), DEFAULT_AUDIO_TAGS, REQUIRED_AUDIO_TAGS)


def save_audio_tags(tags: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("audio:tags", order_tags_custom(tags, REQUIRED_AUDIO_TAGS), scope="shared")
        return
    save_tag_list(audio_tags_path(), tags, REQUIRED_AUDIO_TAGS)


def load_audio_categories() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        categories = storage.load_labels("audio:categories", DEFAULT_AUDIO_CATEGORIES, scope="shared")
        return normalize_tags(categories) or [DEFAULT_AUDIO_CATEGORIES[-1]]
    return load_category_list(
        audio_categories_path(),
        DEFAULT_AUDIO_CATEGORIES,
        empty_fallback=[DEFAULT_AUDIO_CATEGORIES[-1]],
    )


def save_audio_categories(categories: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("audio:categories", normalize_tags(categories) or [DEFAULT_AUDIO_CATEGORIES[-1]], scope="shared")
        return
    save_category_list(audio_categories_path(), categories, DEFAULT_AUDIO_CATEGORIES[-1])


def normalize_resource_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_RESOURCE_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_RESOURCE_TAG]


def normalize_generator_item_tags(raw_tags) -> list[str]:
    tags = normalize_tags(raw_tags)
    non_service_tags = [tag for tag in tags if tag.casefold() != UNSORTED_GENERATOR_TAG.casefold()]
    return sort_tags_alphabetically(non_service_tags) or [UNSORTED_GENERATOR_TAG]


def load_resource_tags() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("resources:tags", DEFAULT_RESOURCE_TAGS, scope="shared")
        required_keys = {tag.casefold() for tag in REQUIRED_RESOURCE_TAGS}
        return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys], REQUIRED_RESOURCE_TAGS)
    return load_tag_list(resources_tags_path(), DEFAULT_RESOURCE_TAGS, REQUIRED_RESOURCE_TAGS)


def save_resource_tags(tags: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("resources:tags", order_tags_custom(tags, REQUIRED_RESOURCE_TAGS), scope="shared")
        return
    save_tag_list(resources_tags_path(), tags, REQUIRED_RESOURCE_TAGS)


def load_generator_tags() -> list[str]:
    tags = storage.load_labels("generators:tags", DEFAULT_GENERATOR_TAGS, scope="shared")
    required_keys = {tag.casefold() for tag in REQUIRED_GENERATOR_TAGS}
    return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in required_keys], REQUIRED_GENERATOR_TAGS)


def save_generator_tags(tags: list[str]) -> None:
    storage.save_labels("generators:tags", order_tags_custom(tags, REQUIRED_GENERATOR_TAGS), scope="shared")


def load_resource_categories() -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        categories = normalize_tags(storage.load_labels("resources:categories", DEFAULT_RESOURCE_CATEGORIES, scope="shared"))
        return categories
    return load_category_list(resources_categories_path(), DEFAULT_RESOURCE_CATEGORIES)


def save_resource_categories(categories: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("resources:categories", normalize_tags(categories) or [DEFAULT_RESOURCE_CATEGORIES[-1]], scope="shared")
        return
    save_category_list(resources_categories_path(), categories, DEFAULT_RESOURCE_CATEGORIES[-1])


def load_generator_categories() -> list[str]:
    return normalize_tags(storage.load_labels("generators:categories", DEFAULT_GENERATOR_CATEGORIES, scope="shared")) or [DEFAULT_GENERATOR_CATEGORIES[-1]]


def save_generator_categories(categories: list[str]) -> None:
    storage.save_labels("generators:categories", normalize_tags(categories) or [DEFAULT_GENERATOR_CATEGORIES[-1]], scope="shared")


def normalize_resource_category(raw_category) -> str:
    value = str(raw_category or "").strip()
    if not value:
        return DEFAULT_RESOURCE_CATEGORIES[0]
    categories = load_resource_categories()
    match = next((category for category in categories if category.casefold() == value.casefold()), None)
    return match or value


def normalize_generator_category(raw_category) -> str:
    value = str(raw_category or "").strip()
    if not value:
        return DEFAULT_GENERATOR_CATEGORIES[-1]
    categories = load_generator_categories()
    match = next((category for category in categories if category.casefold() == value.casefold()), None)
    return match or value


def normalize_resource_type(raw_type: str) -> str:
    return "local" if str(raw_type or "").strip().casefold() == "local" else "web"


def visible_map_tags(scope: str, maps: list[dict], campaign_slug: str = "") -> list[str]:
    return sort_tags_alphabetically(
        collect_visible_tags(load_map_tags(scope, campaign_slug), maps, lambda item: item.get("tags", []), REQUIRED_MAP_TAGS),
        REQUIRED_MAP_TAGS,
    )


def visible_scene_tags(scenes: list[dict]) -> list[str]:
    return collect_visible_tags(load_scene_tags(), scenes, lambda item: item.get("tags", []), REQUIRED_SCENE_TAGS)


def visible_audio_tags(tracks: list[dict]) -> list[str]:
    return collect_visible_tags(load_audio_tags(), tracks, lambda item: item.get("tags", []), REQUIRED_AUDIO_TAGS)


def visible_resource_tags(resources: list[dict]) -> list[str]:
    return collect_visible_tags(load_resource_tags(), resources, lambda item: item.get("tags", []), REQUIRED_RESOURCE_TAGS)


def visible_generator_tags(generators: list[dict]) -> list[str]:
    return collect_visible_tags(load_generator_tags(), generators, lambda item: item.get("tags", []), REQUIRED_GENERATOR_TAGS)


load_characters = storage.load_characters
save_characters = storage.save_characters
load_notes = storage.load_notes
save_notes = storage.save_notes
load_gods = storage.load_gods
save_gods = storage.save_gods


def load_note_tags(campaign_slug: str) -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        tags = storage.load_labels("notes:tags", DEFAULT_NOTE_TAGS, scope="campaign", campaign_slug=campaign_slug)
        excluded_keys = {tag.casefold() for tag in LEGACY_NOTE_TAGS}
        required_keys = {tag.casefold() for tag in REQUIRED_NOTE_TAGS}
        return order_tags_custom([tag for tag in normalize_tags(tags) if tag.casefold() not in excluded_keys and tag.casefold() not in required_keys], REQUIRED_NOTE_TAGS)
    return load_tag_list(notes_tags_path(campaign_slug), DEFAULT_NOTE_TAGS, REQUIRED_NOTE_TAGS, list(LEGACY_NOTE_TAGS))


def save_note_tags(campaign_slug: str, tags: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("notes:tags", order_tags_custom(tags, REQUIRED_NOTE_TAGS), scope="campaign", campaign_slug=campaign_slug)
        return
    save_tag_list(notes_tags_path(campaign_slug), tags, REQUIRED_NOTE_TAGS, list(LEGACY_NOTE_TAGS))


def visible_note_tags(campaign_slug: str, notes: list[dict]) -> list[str]:
    return collect_visible_tags(load_note_tags(campaign_slug), notes, lambda item: normalize_note_item_tags(item.get("tags", [])), REQUIRED_NOTE_TAGS)


def load_god_domains(campaign_slug: str) -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        return normalize_tags(storage.load_labels("gods:domains", DEFAULT_GOD_DOMAINS, scope="campaign", campaign_slug=campaign_slug))
    path = gods_domains_path(campaign_slug)
    if path.exists():
        return normalize_tags(read_json(path, fallback=[]))
    return DEFAULT_GOD_DOMAINS[:]


def save_god_domains(campaign_slug: str, domains: list[str]) -> None:
    domains = normalize_tags(domains)
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("gods:domains", domains, scope="campaign", campaign_slug=campaign_slug)
        return
    write_json(gods_domains_path(campaign_slug), domains)


def load_god_alignments_raw(campaign_slug: str = "") -> list[str]:
    if campaign_slug and STORAGE_BACKEND == "sqlite":
        return normalize_tags(storage.load_labels("gods:alignments", DEFAULT_GOD_ALIGNMENTS, scope="campaign", campaign_slug=campaign_slug))
    if campaign_slug:
        path = gods_alignments_path(campaign_slug)
        if path.exists():
            return normalize_tags(read_json(path, fallback=[]))
    return DEFAULT_GOD_ALIGNMENTS[:]


def load_god_alignments(campaign_slug: str) -> list[str]:
    alignments = load_god_alignments_raw(campaign_slug)
    if FALLBACK_GOD_ALIGNMENT not in alignments:
        alignments.append(FALLBACK_GOD_ALIGNMENT)
    return alignments


def save_god_alignments(campaign_slug: str, alignments: list[str]) -> None:
    alignments = normalize_tags(alignments) or DEFAULT_GOD_ALIGNMENTS[:]
    if FALLBACK_GOD_ALIGNMENT not in alignments:
        alignments.append(FALLBACK_GOD_ALIGNMENT)
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("gods:alignments", alignments, scope="campaign", campaign_slug=campaign_slug)
        return
    write_json(gods_alignments_path(campaign_slug), alignments)


def visible_god_domains(campaign_slug: str, gods: list[dict]) -> list[str]:
    return collect_visible_tags(load_god_domains(campaign_slug), gods, lambda item: item.get("domains", []), [])


def visible_god_ranks(gods: list[dict]) -> list[str]:
    return collect_visible_tags(load_god_ranks(), gods, lambda item: [item.get("rank", "")], [])


def load_god_ranks(campaign_slug: str = "") -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        return normalize_tags(storage.load_labels("gods:ranks", DEFAULT_GOD_RANKS, scope="campaign", campaign_slug=campaign_slug))
    return DEFAULT_GOD_RANKS[:]


def save_god_ranks(campaign_slug: str, ranks: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("gods:ranks", normalize_tags(ranks) or DEFAULT_GOD_RANKS[:], scope="campaign", campaign_slug=campaign_slug)


def load_god_pantheons(campaign_slug: str = "") -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        return normalize_tags(storage.load_labels("gods:pantheons", [], scope="campaign", campaign_slug=campaign_slug))
    return []


def save_god_pantheons(campaign_slug: str, pantheons: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("gods:pantheons", normalize_tags(pantheons), scope="campaign", campaign_slug=campaign_slug)


def visible_god_pantheons(campaign_slug: str, gods: list[dict]) -> list[str]:
    return collect_visible_tags(load_god_pantheons(campaign_slug), gods, lambda item: item.get("pantheons", []) or [item.get("pantheon", "")], [])


def load_character_groups(campaign_slug: str) -> list[str]:
    if STORAGE_BACKEND == "sqlite":
        groups = storage.load_labels("characters:tags", DEFAULT_CHARACTER_TAGS, scope="campaign", campaign_slug=campaign_slug)
        groups = [group for group in normalize_tags(groups) if group.casefold() != "игроки"]
        required_keys = {required_group.casefold() for required_group in REQUIRED_CHARACTER_TAGS}
        groups = [group for group in groups if group.casefold() not in required_keys]
        return order_tags_custom(groups, REQUIRED_CHARACTER_TAGS)
    tags_path = characters_tags_path(campaign_slug)
    legacy_groups_path = characters_groups_path(campaign_slug)
    if tags_path.exists():
        groups = normalize_tags(read_json(tags_path, fallback=[]))
    elif legacy_groups_path.exists():
        groups = normalize_tags(read_json(legacy_groups_path, fallback=[]))
    else:
        groups = DEFAULT_CHARACTER_TAGS[:]
    groups = [group for group in groups if group.casefold() != "игроки"]

    required_keys = {required_group.casefold() for required_group in REQUIRED_CHARACTER_TAGS}
    groups = [group for group in groups if group.casefold() not in required_keys]
    return order_tags_custom(groups, REQUIRED_CHARACTER_TAGS)


def save_character_groups(campaign_slug: str, groups: list[str]) -> None:
    if STORAGE_BACKEND == "sqlite":
        storage.save_labels("characters:tags", order_tags_custom(groups, REQUIRED_CHARACTER_TAGS), scope="campaign", campaign_slug=campaign_slug)
        return
    save_tag_list(characters_tags_path(campaign_slug), groups, REQUIRED_CHARACTER_TAGS)


def visible_character_groups(campaign_slug: str, characters: list[dict]) -> list[str]:
    return collect_visible_tags(load_character_groups(campaign_slug), characters, character_tags, REQUIRED_CHARACTER_TAGS)


load_character_tags = load_character_groups
save_character_tags = save_character_groups
visible_character_tags = visible_character_groups


def map_url(map_item: dict, scope: str, campaign_slug: str = "") -> str:
    return media_catalog.map_url(
        map_item,
        scope,
        campaign_slug,
        lambda map_id: url_for("serve_shared_map", map_id=map_id),
        lambda slug, map_id: url_for("serve_campaign_map", campaign_slug=slug, map_id=map_id),
    )


def map_thumbnail_url(map_item: dict, scope: str, campaign_slug: str = "") -> str:
    if scope == "campaign":
        return url_for("serve_campaign_map_thumbnail", campaign_slug=campaign_slug, map_id=map_item["id"])
    return url_for("serve_shared_map_thumbnail", map_id=map_item["id"])


def map_foundry_path(map_item: dict, scope: str, campaign_slug: str = "") -> str:
    return media_catalog.map_foundry_path(
        map_item,
        scope,
        campaign_slug,
        foundry_assets_dir,
        get_campaign,
        campaign_foundry_slug,
    )


def scene_url(scene: dict) -> str:
    return media_catalog.scene_url(scene, lambda scene_id: url_for("serve_scene_image", scene_id=scene_id))


def scene_thumbnail_url(scene: dict) -> str:
    return url_for("serve_scene_thumbnail", scene_id=scene["id"])


def scene_foundry_path(scene: dict) -> str:
    return media_catalog.scene_foundry_path(scene, foundry_assets_dir)


def audio_url(track: dict) -> str:
    return media_catalog.audio_url(track, lambda track_id: url_for("serve_audio_file", track_id=track_id))


def audio_thumbnail_url(track: dict) -> str:
    thumbnail_filename = track.get("thumbnail_filename", "")
    if not thumbnail_filename:
        return ""
    if not (audio_directory() / thumbnail_filename).exists():
        return ""
    return url_for("serve_audio_thumbnail", track_id=track["id"])


def resource_target(resource: dict) -> str:
    return media_catalog.resource_target(resource)


def resource_type_label(resource: dict) -> str:
    return media_catalog.resource_type_label(resource)


def prepare_maps(scope: str, campaign_slug: str = "") -> list[dict]:
    prepared = media_catalog.prepare_maps(
        scope,
        campaign_slug,
        load_maps,
        maps_directory,
        normalize_map_item_tags,
        lambda map_id: url_for("serve_shared_map", map_id=map_id),
        lambda slug, map_id: url_for("serve_campaign_map", campaign_slug=slug, map_id=map_id),
        foundry_assets_dir,
        get_campaign,
        campaign_foundry_slug,
    )
    for item in prepared:
        item["thumbnail_url"] = map_thumbnail_url(item, scope, campaign_slug)
    return prepared


def prepare_scenes() -> list[dict]:
    prepared = media_catalog.prepare_scenes(
        load_scenes,
        scenes_directory,
        normalize_scene_item_tags,
        lambda scene_id: url_for("serve_scene_image", scene_id=scene_id),
        foundry_assets_dir,
    )
    for item in prepared:
        item["thumbnail_url"] = scene_thumbnail_url(item)
    return prepared


def prepare_audio_tracks() -> list[dict]:
    return media_catalog.prepare_audio_tracks(
        load_audio_tracks,
        audio_directory,
        normalize_audio_item_tags,
        lambda track_id: url_for("serve_audio_file", track_id=track_id),
        audio_thumbnail_url,
    )


def prepare_resources() -> list[dict]:
    return media_catalog.prepare_resources(load_resources, normalize_resource_type, normalize_resource_item_tags)


def prepare_generator(item: dict | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    generator = item.copy()
    generator["tags"] = normalize_generator_item_tags(generator.get("tags", []))
    generator["category"] = normalize_generator_category(generator.get("category", ""))
    generator["rows"] = sorted(
        [
            {
                "id": str(row.get("id", "")).strip(),
                "min": int(row.get("min", row.get("range_min", 0))),
                "max": int(row.get("max", row.get("range_max", 0))),
                "result_markdown": str(row.get("result_markdown") or row.get("result") or "").strip(),
                "result_html": render_text_content(str(row.get("result_markdown") or row.get("result") or "").strip()),
            }
            for row in generator.get("rows", [])
            if isinstance(row, dict)
        ],
        key=lambda row: (row["min"], row["max"]),
    )
    return generator


def prepare_generators() -> list[dict]:
    return [generator for generator in (prepare_generator(item) for item in load_generators()) if generator is not None]


def character_url(character: dict, campaign_slug: str) -> str:
    return media_catalog.character_url(
        character,
        campaign_slug,
        lambda slug, character_id: url_for("serve_character_image", campaign_slug=slug, character_id=character_id),
    )


def character_thumbnail_url(character: dict, campaign_slug: str) -> str:
    return url_for("serve_character_thumbnail", campaign_slug=campaign_slug, character_id=character["id"])


def character_foundry_path(character: dict, campaign_slug: str) -> str:
    return media_catalog.character_foundry_path(
        character,
        campaign_slug,
        foundry_assets_dir,
        get_campaign,
        campaign_foundry_slug,
    )


def active_page_art_filename(active_theme: str, body_classes: list[str]) -> str:
    theme_art = THEME_PAGE_ART.get(active_theme) or THEME_PAGE_ART["madness-crown"]
    class_set = set(body_classes)
    if "page-campaign-maps" in class_set:
        page_key = "campaign-maps"
    else:
        page_key = next(
            (
                class_name.removeprefix("page-")
                for class_name in body_classes
                if class_name.startswith("page-") and class_name != "page"
            ),
            "default",
        )
    return theme_art.get(page_key, theme_art["default"])


def prepare_characters(campaign_slug: str) -> list[dict]:
    prepared = media_catalog.prepare_characters(
        campaign_slug,
        load_characters,
        characters_directory,
        character_category,
        character_tags,
        lambda slug, character_id: url_for(
            "serve_character_image",
            campaign_slug=slug,
            character_id=character_id,
        ),
        foundry_assets_dir,
        get_campaign,
        campaign_foundry_slug,
    )
    for item in prepared:
        item["thumbnail_url"] = character_thumbnail_url(item, campaign_slug)
    return prepared


def parse_note_references(raw_references) -> list[dict]:
    if isinstance(raw_references, str):
        try:
            raw_references = json.loads(raw_references)
        except json.JSONDecodeError:
            raw_references = []
    if not isinstance(raw_references, list):
        return []

    references = []
    seen = set()
    for item in raw_references:
        if not isinstance(item, dict):
            continue
        ref_type = str(item.get("type", "")).strip()
        ref_id = str(item.get("id", "")).strip()
        try:
            reference = EntityReference(ref_type, ref_id)
        except ValueError:
            continue
        key = (reference.type, reference.id)
        if key in seen:
            continue
        seen.add(key)
        references.append({"type": reference.type, "id": reference.id})
    return references


def normalize_session_hours(value):
    raw_value = str(value or "").strip().replace(",", ".")
    if not raw_value:
        return ""
    try:
        hours = float(raw_value)
    except ValueError:
        return ""
    if hours < 0:
        return ""
    return int(hours) if hours.is_integer() else round(hours, 2)


def infer_session_hours_from_text(text: str, keywords: list[str]):
    keyword_keys = [keyword.casefold() for keyword in keywords]
    for line in str(text or "").splitlines()[:8]:
        line_key = line.casefold()
        if keyword_keys and not any(keyword in line_key for keyword in keyword_keys):
            continue
        match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:ч\.?|час(?:а|ов)?)\b", line_key)
        if match:
            return normalize_session_hours(match.group(1))
    return ""


def format_session_hours(value) -> str:
    hours = normalize_session_hours(value)
    if hours == "":
        return ""
    return str(hours).replace(".", ",")


def build_session_stats(notes: list[dict]) -> dict:
    def is_numbered_game(note: dict) -> bool:
        try:
            return int(note.get("session_number") or 0) > 0
        except (TypeError, ValueError):
            return False

    completed = [note for note in notes if note.get("status") == "Проведена"]
    completed_games = [note for note in completed if is_numbered_game(note)]
    prep_hours = sum(float(note.get("prep_hours") or 0) for note in notes)
    play_hours = sum(float(note.get("play_hours") or 0) for note in completed_games)
    dated_sessions = []
    for note in completed_games:
        raw_date = str(note.get("world_date", "")).strip()
        if not raw_date:
            continue
        try:
            dated_sessions.append(datetime.strptime(raw_date, "%Y-%m-%d").date())
        except ValueError:
            continue
    dated_sessions.sort()
    weekly_frequency = ""
    monthly_frequency = ""
    if len(dated_sessions) >= 2:
        days_span = max(1, (dated_sessions[-1] - dated_sessions[0]).days)
        session_intervals = len(dated_sessions) - 1
        weekly_frequency = round(session_intervals / (days_span / 7), 1)
        monthly_frequency = round(session_intervals / (days_span / 30.4375), 1)
    return {
        "completed_count": len(completed_games),
        "prep_hours": int(prep_hours) if prep_hours.is_integer() else round(prep_hours, 1),
        "play_hours": int(play_hours) if play_hours.is_integer() else round(play_hours, 1),
        "weekly_frequency": weekly_frequency,
        "monthly_frequency": monthly_frequency,
    }


def build_global_session_stats(campaigns: list[dict]) -> dict:
    all_notes = []
    for campaign in campaigns:
        campaign_slug = str(campaign.get("slug", "")).strip()
        if campaign_slug:
            all_notes.extend(prepare_notes(campaign_slug))
    stats = build_session_stats(all_notes)
    planned_count = 0
    for note in all_notes:
        if note.get("status") != "В планах":
            continue
        raw_date = str(note.get("world_date", "")).strip()
        if not raw_date:
            continue
        try:
            if datetime.strptime(raw_date, "%Y-%m-%d").date() >= datetime.now().date():
                planned_count += 1
        except ValueError:
            continue
    return {
        **stats,
        "campaign_count": len(campaigns),
        "planned_count": planned_count,
        "session_count": len(all_notes),
    }


def build_global_session_calendar_events(campaigns: list[dict]) -> list[dict]:
    events = []
    for campaign in campaigns:
        campaign_slug = str(campaign.get("slug", "")).strip()
        if not campaign_slug:
            continue
        campaign_name = str(campaign.get("name") or campaign_slug).strip()
        for note in prepare_notes(campaign_slug):
            if note.get("status") not in NOTE_STATUSES or not note.get("world_date"):
                continue
            events.append(
                {
                    "id": note.get("id", ""),
                    "title": note.get("title", ""),
                    "session_number": note.get("session_number", 0),
                    "status": note.get("status", ""),
                    "world_date": note.get("world_date", ""),
                    "campaign_slug": campaign_slug,
                    "campaign_name": campaign_name,
                    "url": url_for("notes_page", campaign=campaign_slug, note=note.get("id", "")),
                }
            )
    return sorted(events, key=lambda event: (event["world_date"], event["campaign_name"], event["session_number"]))


def normalize_note(note: dict) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    note_type = "Сессия"
    status = note.get("status") if note.get("status") in NOTE_STATUSES else "В планах"
    raw_session_number = note.get("session_number", note.get("number", ""))
    try:
        session_number = max(0, int(raw_session_number))
    except (TypeError, ValueError):
        session_number = 0
    title = str(note.get("title", "")).strip()
    if not title:
        title = "Нулевая сессия" if session_number == 0 else f"Сессия {session_number}"
    planned_body = str(note.get("planned_body", note.get("body", ""))).strip()
    happened_body = str(note.get("happened_body", "")).strip()
    combined_body = "\n\n".join(part for part in [planned_body, happened_body] if part)
    prep_hours = normalize_session_hours(note.get("prep_hours", ""))
    if prep_hours == "":
        prep_hours = infer_session_hours_from_text(combined_body, ["подготов"])
    play_hours = normalize_session_hours(note.get("play_hours", ""))
    if play_hours == "":
        play_hours = infer_session_hours_from_text(happened_body or combined_body, ["игр", "прошло", "сесс"])
    return {
        "id": str(note.get("id") or uuid4().hex),
        "title": title,
        "body": combined_body,
        "planned_body": planned_body,
        "happened_body": happened_body,
        "type": note_type,
        "status": status,
        "session_number": session_number,
        "prep_hours": prep_hours,
        "play_hours": play_hours,
        "tags": normalize_note_item_tags(note.get("tags", [])),
        "world_date": str(note.get("world_date", "")).strip(),
        "references": parse_note_references(note.get("references", [])),
        "created_at": str(note.get("created_at") or now),
        "updated_at": str(note.get("updated_at") or now),
    }


def note_excerpt(note: dict, limit: int = 180) -> str:
    source = note.get("happened_body") if note.get("status") == "Проведена" else note.get("planned_body")
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", source or note.get("body", ""))
    body = re.sub(r"[\[\]`*_>#-]+", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return "Текста пока нет."
    return body if len(body) <= limit else f"{body[:limit].rstrip()}..."


def prepare_notes(campaign_slug: str) -> list[dict]:
    prepared = []
    for index, item in enumerate(load_notes(campaign_slug)):
        source = item.copy()
        if "session_number" not in source and "number" not in source:
            source["session_number"] = index
        note = normalize_note(source)
        note["excerpt"] = note_excerpt(note)
        prepared.append(note)
    return prepared


def normalize_god(god: dict, campaign_slug: str = "") -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    alignments = load_god_alignments(campaign_slug) if campaign_slug else DEFAULT_GOD_ALIGNMENTS
    raw_alignment = str(god.get("alignment", "")).strip()
    alignment = next((item for item in alignments if item.casefold() == raw_alignment.casefold()), None) or raw_alignment or FALLBACK_GOD_ALIGNMENT
    domains = normalize_god_domains(god.get("domains", god.get("tags", [])))
    pantheons = normalize_tags(god.get("pantheons", god.get("panteons", god.get("pantheon", ""))))
    source = god.get("source", "")
    if isinstance(source, dict):
        source = source.get("shortName") or source.get("name") or ""
    return {
        "id": str(god.get("id") or uuid4().hex),
        "name": str(god.get("name", god.get("title", ""))).strip() or "Безымянное божество",
        "english_name": str(god.get("english_name", god.get("name_eng", ""))).strip(),
        "url": str(god.get("url", "")).strip(),
        "alignment": alignment,
        "short_alignment": str(god.get("short_alignment", god.get("shortAlignment", ""))).strip(),
        "domains": domains,
        "pantheon": (pantheons[0] if pantheons else str(god.get("pantheon", "")).strip()),
        "pantheons": pantheons,
        "rank": str(god.get("rank", "")).strip(),
        "titles": normalize_tags(god.get("titles", [])),
        "symbol": str(god.get("symbol", "")).strip(),
        "source": str(source).strip(),
        "source_name": str(god.get("source_name", "")).strip(),
        "images": normalize_tags(god.get("images", [])),
        "description": str(god.get("description", god.get("body", ""))).strip(),
        "created_at": str(god.get("created_at") or now),
        "updated_at": str(god.get("updated_at") or now),
    }


def prepare_gods(campaign_slug: str) -> list[dict]:
    gods = [normalize_god(item, campaign_slug) for item in load_gods(campaign_slug)]
    return sorted(gods, key=lambda item: (item.get("alignment", ""), item.get("name", "").casefold()))


def find_god_by_id(campaign_slug: str, god_id: str) -> dict | None:
    return next((god for god in prepare_gods(campaign_slug) if god["id"] == god_id), None)


def filter_gods(
    gods: list[dict],
    selected_domains: list[str],
    excluded_domains: list[str],
    search: str,
    alignments: list[str] | str = "",
    excluded_alignments: list[str] | None = None,
    ranks: list[str] | None = None,
    excluded_ranks: list[str] | None = None,
    pantheons: list[str] | None = None,
    excluded_pantheons: list[str] | None = None,
) -> list[dict]:
    selected = {domain.casefold() for domain in normalize_tags(selected_domains)}
    excluded = {domain.casefold() for domain in normalize_tags(excluded_domains)}
    if isinstance(alignments, str):
        alignments = [alignments] if alignments else []
    selected_alignments = {alignment.casefold() for alignment in normalize_tags(alignments)}
    excluded_alignment_keys = {alignment.casefold() for alignment in normalize_tags(excluded_alignments or [])}
    selected_ranks = {rank.casefold() for rank in normalize_tags(ranks or [])}
    excluded_rank_keys = {rank.casefold() for rank in normalize_tags(excluded_ranks or [])}
    selected_pantheons = {pantheon.casefold() for pantheon in normalize_tags(pantheons or [])}
    excluded_pantheon_keys = {pantheon.casefold() for pantheon in normalize_tags(excluded_pantheons or [])}
    query = search.strip().casefold()
    filtered = []
    for god in gods:
        domains = {domain.casefold() for domain in god.get("domains", [])}
        god_pantheons = {pantheon.casefold() for pantheon in god.get("pantheons", []) or [god.get("pantheon", "")]}
        god_alignment = god.get("alignment", "").casefold()
        god_rank = god.get("rank", "").casefold()
        if selected and not selected.issubset(domains):
            continue
        if excluded and excluded.intersection(domains):
            continue
        if selected_alignments and god_alignment not in selected_alignments:
            continue
        if excluded_alignment_keys and god_alignment in excluded_alignment_keys:
            continue
        if selected_ranks and god.get("rank", "").casefold() not in selected_ranks:
            continue
        if excluded_rank_keys and god_rank in excluded_rank_keys:
            continue
        if selected_pantheons and not selected_pantheons.intersection(god_pantheons):
            continue
        if excluded_pantheon_keys and excluded_pantheon_keys.intersection(god_pantheons):
            continue
        if query:
            haystack = " ".join(
                [
                    god.get("name", ""),
                    god.get("english_name", ""),
                    god.get("alignment", ""),
                    god.get("pantheon", ""),
                    " ".join(god.get("pantheons", [])),
                    god.get("rank", ""),
                    " ".join(god.get("titles", [])),
                    god.get("symbol", ""),
                    god.get("source", ""),
                    " ".join(god.get("domains", [])),
                    god.get("description", ""),
                ]
            ).casefold()
            if query not in haystack:
                continue
        filtered.append(god)
    return filtered


def gods_by_alignment(gods: list[dict], alignments: list[str]) -> list[dict]:
    known = alignments[:]
    for god in gods:
        alignment = god.get("alignment") or FALLBACK_GOD_ALIGNMENT
        if alignment.casefold() not in {item.casefold() for item in known}:
            known.append(alignment)
    groups = []
    for alignment in known:
        group_gods = [god for god in gods if (god.get("alignment") or FALLBACK_GOD_ALIGNMENT).casefold() == alignment.casefold()]
        if group_gods:
            groups.append({"alignment": alignment, "gods": sorted(group_gods, key=lambda item: item.get("name", "").casefold())})
    return groups


def note_reference_key(reference: dict) -> str:
    return f"{reference.get('type', '')}:{reference.get('id', '')}"


def find_note_by_id(campaign_slug: str, note_id: str) -> dict | None:
    return next((note for note in prepare_notes(campaign_slug) if note["id"] == note_id), None)


def sort_notes(notes: list[dict], sort_key: str) -> list[dict]:
    sort_key = sort_key if sort_key in NOTE_SORT_OPTIONS else "session"
    sorter = lambda note: (note.get("session_number", 0), note.get("title", "").casefold())
    return sorted(notes, key=sorter, reverse=True)


def filter_notes(
    notes: list[dict],
    selected_tags: list[str],
    excluded_tags: list[str],
    search: str,
    note_type: str,
    status: str,
    reference_filter: str,
    date_from: str,
    date_to: str,
) -> list[dict]:
    selected = {tag.casefold() for tag in normalize_tags(selected_tags)}
    excluded = {tag.casefold() for tag in normalize_tags(excluded_tags)}
    query = search.strip().casefold()
    filtered = []
    for note in notes:
        tags = {tag.casefold() for tag in note.get("tags", [])}
        if selected and not selected.issubset(tags):
            continue
        if excluded and excluded.intersection(tags):
            continue
        if note_type and note.get("type") != note_type:
            continue
        if status and note.get("status") != status:
            continue
        if reference_filter and reference_filter not in {note_reference_key(ref) for ref in note.get("references", [])}:
            continue
        if date_from and (not note.get("world_date") or note.get("world_date") < date_from):
            continue
        if date_to and (not note.get("world_date") or note.get("world_date") > date_to):
            continue
        if query:
            session_label = "нулевая сессия" if note.get("session_number", 0) == 0 else f"сессия {note.get('session_number', '')}"
            haystack = " ".join(
                [
                    note.get("title", ""),
                    note.get("world_date", ""),
                    str(note.get("session_number", "")),
                    f"#{note.get('session_number', '')}",
                    session_label,
                ]
            ).casefold()
            if query not in haystack:
                continue
        filtered.append(note)
    return filtered


def note_url(campaign_slug: str, note_id: str) -> str:
    return url_for("notes_page", campaign=campaign_slug, note=note_id)


def build_note_reference_options(campaign_slug: str) -> list[dict]:
    options = []
    for character in prepare_characters(campaign_slug):
        options.append(
            {
                "type": "character",
                "id": character["id"],
                "label": character["name"],
                "group": "NPC",
                "url": url_for("characters_page", campaign=campaign_slug, q=character["name"], character=character["id"]),
                "image_url": character.get("url", ""),
                "subtitle": character.get("race", "") or "NPC кампейна",
                "tags": character.get("tags", [])[:4],
                "terms": " ".join(
                    [
                        character["id"],
                        character["name"],
                        character.get("foundry_path", ""),
                        url_for("characters_page", campaign=campaign_slug, q=character["name"], character=character["id"]),
                    ]
                ),
            }
        )
    for god in prepare_gods(campaign_slug):
        options.append(
            {
                "type": "god",
                "id": god["id"],
                "label": god["name"],
                "group": "Боги",
                "url": url_for("gods_page", campaign=campaign_slug, q=god["name"], god=god["id"]),
                "image_url": "",
                "subtitle": " · ".join([item for item in [god.get("alignment", ""), god.get("pantheon", "")] if item]) or "Божество кампейна",
                "tags": god.get("domains", [])[:4],
                "terms": " ".join(
                    [
                        god["id"],
                        god["name"],
                        god.get("alignment", ""),
                        god.get("pantheon", ""),
                        god.get("symbol", ""),
                        god.get("source", ""),
                        " ".join(god.get("domains", [])),
                        url_for("gods_page", campaign=campaign_slug, q=god["name"], god=god["id"]),
                    ]
                ),
            }
        )
    for map_item in prepare_maps("shared"):
        options.append(
            {
                "type": "map",
                "id": map_item["id"],
                "label": map_item["title"],
                "group": "Карты",
                "url": url_for("maps_page"),
                "image_url": map_item.get("url", ""),
                "subtitle": " · ".join(map_item.get("tags", [])[:3]) or "Общая карта",
                "tags": map_item.get("tags", [])[:4],
                "terms": " ".join(
                    [
                        map_item["id"],
                        map_item["title"],
                        map_item.get("foundry_path", ""),
                        url_for("maps_page"),
                    ]
                ),
            }
        )
    for scene in prepare_scenes():
        options.append(
            {
                "type": "scene",
                "id": scene["id"],
                "label": scene["title"],
                "group": "Раздат",
                "url": url_for("scenes_page"),
                "image_url": scene.get("url", ""),
                "subtitle": " · ".join(scene.get("tags", [])[:3]) or "Раздаточный материал",
                "tags": scene.get("tags", [])[:4],
                "terms": " ".join(
                    [
                        scene["id"],
                        scene["title"],
                        scene.get("foundry_path", ""),
                        url_for("scenes_page"),
                    ]
                ),
            }
        )
    for generator in prepare_generators():
        options.append(
            {
                "type": "generator",
                "id": generator["id"],
                "label": generator["title"],
                "group": "Генераторы",
                "url": url_for("generators_page", q=generator["title"]),
                "image_url": "",
                "subtitle": " · ".join(
                    [
                        item
                        for item in [
                            generator.get("category", ""),
                            generator.get("dice_expression", ""),
                        ]
                        if item
                    ]
                )
                or "Таблица случайных результатов",
                "tags": generator.get("tags", [])[:4],
                "terms": " ".join(
                    [
                        generator["id"],
                        generator["title"],
                        generator.get("description", ""),
                        generator.get("category", ""),
                        generator.get("dice_expression", ""),
                        " ".join(generator.get("tags", [])),
                        " ".join(row.get("result_markdown", "") for row in generator.get("rows", [])),
                        url_for("generators_page", q=generator["title"]),
                    ]
                ),
            }
        )
    return sorted(options, key=lambda item: (item["group"], item["label"].casefold()))


def material_preview_payload(campaign_slug: str, material_type: str, material_id: str) -> dict | None:
    campaign = get_campaign(campaign_slug)
    if campaign is None:
        return None

    if material_type == "party":
        return {
            "type": "party",
            "kicker": "Группа игроков",
            "title": campaign["name"],
            "subtitle": "Персонажи игроков и общая информация группы.",
            "page_url": url_for("section", slug="party", campaign=campaign_slug),
            "image_url": campaign.get("cover_url", ""),
            "tags": ["Группа"],
            "fields": [
                {"label": "Кампейн", "value": campaign["name"]},
                {"label": "Раздел", "value": "Группа игроков"},
            ],
        }

    if material_type == "character":
        character = next((item for item in prepare_characters(campaign_slug) if item.get("id") == material_id), None)
        if character is None:
            return None
        return {
            "type": "character",
            "kicker": "NPC",
            "title": character.get("name", ""),
            "subtitle": "Карточка неигрового персонажа",
            "page_url": url_for("characters_page", campaign=campaign_slug, q=character.get("name", ""), character=character.get("id", "")),
            "image_url": character.get("url", ""),
            "copy_image_url": url_for("copy_character_image", character_id=character.get("id", "")),
            "foundry_path": character.get("foundry_path", ""),
            "tags": character.get("tags", []),
            "fields": [
                {"label": "Возраст", "value": character.get("age") or "Не указано"},
                {"label": "Пол", "value": character.get("gender") or "Не указано"},
                {"label": "Раса", "value": character.get("race") or "Не указано"},
                {"label": "Заметки", "value": character.get("notes") or "Заметок пока нет.", "markdown": True},
            ],
        }

    if material_type == "god":
        god = next((item for item in prepare_gods(campaign_slug) if item.get("id") == material_id), None)
        if god is None:
            return None
        return {
            "type": "god",
            "kicker": "Божество",
            "title": god.get("name", ""),
            "subtitle": " · ".join([item for item in [god.get("english_name", ""), god.get("rank", "")] if item]) or "Карточка бога кампейна",
            "page_url": url_for("gods_page", campaign=campaign_slug, q=god.get("name", ""), god=god.get("id", "")),
            "image_url": (god.get("images") or [""])[0],
            "tags": god.get("domains", []),
            "fields": [
                {"label": "Мировоззрение", "value": god.get("alignment") or "Не указано"},
                {"label": "Пантеон", "value": ", ".join(god.get("pantheons", [])) or god.get("pantheon") or "Не указан"},
                {"label": "Ранг", "value": god.get("rank") or "Не указан"},
                {"label": "Титулы", "value": ", ".join(god.get("titles", [])) or "Не указаны"},
                {"label": "Символ", "value": god.get("symbol") or "Не указан"},
                {"label": "Источник", "value": god.get("source") or "Не указан"},
                {"label": "Описание", "value": god.get("description") or "Описание пока не добавлено.", "markdown": True},
            ],
        }

    if material_type == "map":
        map_item = next((item for item in prepare_maps("shared") if item.get("id") == material_id), None)
        if map_item is None:
            return None
        return {
            "type": "map",
            "kicker": "Карта",
            "title": map_item.get("title", ""),
            "subtitle": "Общая карта",
            "page_url": url_for("maps_page"),
            "image_url": map_item.get("url", ""),
            "copy_image_url": url_for("copy_map_image", map_id=map_item.get("id", "")),
            "foundry_path": map_item.get("foundry_path", ""),
            "tags": map_item.get("tags", []),
            "fields": [
                {"label": "Теги", "value": ", ".join(map_item.get("tags", [])) or "Без тегов"},
            ],
        }

    if material_type == "scene":
        scene = next((item for item in prepare_scenes() if item.get("id") == material_id), None)
        if scene is None:
            return None
        return {
            "type": "scene",
            "kicker": "Сцена",
            "title": scene.get("title", ""),
            "subtitle": "Сцена или арт для показа игрокам",
            "page_url": url_for("scenes_page"),
            "image_url": scene.get("url", ""),
            "copy_image_url": url_for("copy_scene_image", map_id=scene.get("id", "")),
            "foundry_path": scene.get("foundry_path", ""),
            "tags": scene.get("tags", []),
            "fields": [
                {"label": "Теги", "value": ", ".join(scene.get("tags", [])) or "Без тегов"},
            ],
        }

    if material_type == "generator":
        generator = next((item for item in prepare_generators() if item.get("id") == material_id), None)
        if generator is None:
            return None
        sample_rows = generator.get("rows", [])[:6]
        rows_text = "\n".join(
            f"{row.get('min')}–{row.get('max')}: {row.get('result_markdown', '')}"
            if row.get("min") != row.get("max")
            else f"{row.get('min')}: {row.get('result_markdown', '')}"
            for row in sample_rows
        )
        return {
            "type": "generator",
            "kicker": "Генератор",
            "title": generator.get("title", ""),
            "subtitle": " · ".join(
                [
                    item
                    for item in [
                        generator.get("category", ""),
                        generator.get("dice_expression", ""),
                    ]
                    if item
                ]
            )
            or "Таблица случайных результатов",
            "page_url": url_for("generators_page", q=generator.get("title", "")),
            "image_url": "",
            "tags": generator.get("tags", []),
            "fields": [
                {"label": "Формула", "value": generator.get("dice_expression") or "Не указана"},
                {"label": "Описание", "value": generator.get("description") or "Описание пока не добавлено.", "markdown": True},
                {"label": "Примеры строк", "value": rows_text or "Строки пока не добавлены.", "markdown": True},
            ],
        }

    return None


def note_backlinks(campaign_slug: str, active_note: dict, notes: list[dict]) -> list[dict]:
    active_title = active_note.get("title", "")
    active_ref_keys = {note_reference_key(ref) for ref in active_note.get("references", [])}
    backlinks = []
    for note in notes:
        if note["id"] == active_note["id"]:
            continue
        linked_by_title = bool(active_title and f"[[{active_title.casefold()}]]" in note.get("body", "").casefold())
        linked_by_note = any(ref.get("type") == "note" and ref.get("id") == active_note["id"] for ref in note.get("references", []))
        shared_entity = bool(active_ref_keys.intersection({note_reference_key(ref) for ref in note.get("references", [])}))
        if linked_by_title or linked_by_note or shared_entity:
            backlinks.append({**note, "url": note_url(campaign_slug, note["id"])})
    return backlinks


def build_character_search_items(campaigns: list[dict]) -> list[dict]:
    characters_by_campaign = {
        campaign.get("slug", ""): prepare_characters(campaign.get("slug", ""))
        for campaign in campaigns
        if campaign.get("slug", "")
    }
    return spotlight_service.build_character_search_items(
        campaigns,
        characters_by_campaign,
        lambda campaign_slug, character: url_for(
            "characters_page",
            campaign=campaign_slug,
            q=character.get("name", ""),
            character=character.get("id", ""),
        ),
    )


def build_resource_search_items() -> list[dict]:
    return spotlight_service.build_resource_search_items(
        prepare_resources(),
        lambda resource: url_for("resources_page", q=resource.get("title", "")),
    )


def build_generator_search_items() -> list[dict]:
    return [
        {
            "title": item.get("title", ""),
            "description": item.get("description") or f"{item.get('category', '')} · {item.get('dice_expression', '')}",
            "terms": " ".join(
                [
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("category", ""),
                    item.get("dice_expression", ""),
                    " ".join(item.get("tags", [])),
                ]
            ),
            "url": url_for("generators_page", q=item.get("title", "")),
        }
        for item in prepare_generators()
    ]


def build_map_search_items(campaigns: list[dict]) -> list[dict]:
    campaign_maps_by_slug = {
        campaign.get("slug", ""): prepare_maps("campaign", campaign.get("slug", ""))
        for campaign in campaigns
        if campaign.get("slug", "")
    }
    return spotlight_service.build_map_search_items(
        campaigns,
        prepare_maps("shared"),
        campaign_maps_by_slug,
        lambda campaign_slug, map_item: (
            url_for("maps_page", campaign=campaign_slug, q=map_item.get("title", ""))
            if campaign_slug
            else url_for("maps_page", q=map_item.get("title", ""))
        ),
    )


def build_scene_search_items() -> list[dict]:
    return spotlight_service.build_scene_search_items(
        prepare_scenes(),
        lambda scene_item: url_for("scenes_page", q=scene_item.get("title", "")),
    )


def build_audio_search_items() -> list[dict]:
    return spotlight_service.build_audio_search_items(
        prepare_audio_tracks(),
        lambda track: url_for("audio_page", q=track.get("title", "")),
    )


def build_note_search_items(campaigns: list[dict]) -> list[dict]:
    notes_by_campaign = {
        campaign.get("slug", ""): prepare_notes(campaign.get("slug", ""))
        for campaign in campaigns
        if campaign.get("slug", "")
    }
    return spotlight_service.build_note_search_items(
        campaigns,
        notes_by_campaign,
        lambda campaign_slug, note: url_for(
            "notes_page",
            campaign=campaign_slug,
            q=note.get("title", ""),
            note=note.get("id", ""),
        ),
    )


def build_god_search_items(campaigns: list[dict]) -> list[dict]:
    gods_by_campaign = {
        campaign.get("slug", ""): prepare_gods(campaign.get("slug", ""))
        for campaign in campaigns
        if campaign.get("slug", "")
    }
    return spotlight_service.build_god_search_items(
        campaigns,
        gods_by_campaign,
        lambda campaign_slug, god: url_for(
            "gods_page",
            campaign=campaign_slug,
            q=god.get("name", ""),
            god=god.get("id", ""),
        ),
    )


def filter_maps_by_tags(maps: list[dict], selected_tags: list[str], excluded_tags: list[str] | None = None) -> list[dict]:
    selected = {tag.casefold() for tag in selected_tags}
    excluded = {tag.casefold() for tag in normalize_tags(excluded_tags or [])}
    if not selected and not excluded:
        return maps

    filtered = []
    for item in maps:
        item_tags = {tag.casefold() for tag in item.get("tags", [])}
        if selected.issubset(item_tags) and not excluded.intersection(item_tags):
            filtered.append(item)
    return filtered


def filter_media_by_search(items: list[dict], search: str = "") -> list[dict]:
    raw_query = search.strip()
    query = raw_query.casefold() if len(raw_query) >= 3 else ""
    if not query:
        return items
    filtered = []
    for item in items:
        haystack = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("filename", "")),
                " ".join(str(tag) for tag in item.get("tags", [])),
            ]
        ).casefold()
        if query in haystack:
            filtered.append(item)
    return filtered


def filter_characters(
    characters: list[dict],
    selected_groups: list[str],
    search: str = "",
    excluded_groups: list[str] | None = None,
) -> list[dict]:
    selected = {tag.casefold() for tag in normalize_tags(selected_groups)}
    excluded = {tag.casefold() for tag in normalize_tags(excluded_groups or [])}
    raw_query = search.strip()
    query = raw_query.casefold() if len(raw_query) >= 3 else ""
    filtered = []
    for item in characters:
        item_tags = {tag.casefold() for tag in character_tags(item)}
        name = item.get("name", "")
        if selected and not selected.issubset(item_tags):
            continue
        if excluded and excluded.intersection(item_tags):
            continue
        if query and query not in name.casefold():
            continue
        filtered.append(item)
    return filtered


def paginate_items(items: list[dict], page: int, per_page: int) -> tuple[list[dict], dict]:
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
    }


def maps_redirect(scope: str, campaign_slug: str = ""):
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    search = request.form.get("return_search", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {}
    if tags:
        params["tag"] = tags
    if excluded_tags:
        params["exclude_tag"] = excluded_tags
    if page and page > 1:
        params["page"] = page
    if per_page in MAPS_PER_PAGE_OPTIONS and per_page != DEFAULT_MAPS_PER_PAGE:
        params["per_page"] = per_page
    if search:
        params["q"] = search
    if scope == "campaign":
        params["campaign"] = campaign_slug
    return redirect(url_for("maps_page", **params))


def scenes_redirect():
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    search = request.form.get("return_search", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {}
    if tags:
        params["tag"] = tags
    if excluded_tags:
        params["exclude_tag"] = excluded_tags
    if page and page > 1:
        params["page"] = page
    if per_page in MAPS_PER_PAGE_OPTIONS and per_page != DEFAULT_MAPS_PER_PAGE:
        params["per_page"] = per_page
    if search:
        params["q"] = search
    return redirect(url_for("scenes_page", **params))


def audio_redirect():
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    category = request.form.get("return_category", "").strip()
    search = request.form.get("return_search", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {}
    for tag in tags:
        params.setdefault("tag", []).append(tag)
    for tag in excluded_tags:
        params.setdefault("exclude_tag", []).append(tag)
    if category:
        params["category"] = category
    if search:
        params["q"] = search
    if page and page > 1:
        params["page"] = page
    if per_page in AUDIO_PER_PAGE_OPTIONS and per_page != DEFAULT_AUDIO_PER_PAGE:
        params["per_page"] = per_page
    return redirect(url_for("audio_page", **params))


def resources_redirect():
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    category = request.form.get("return_category", "").strip()
    source_type = request.form.get("return_type", "").strip()
    search = request.form.get("return_search", "").strip()
    sort = request.form.get("return_sort", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {}
    for tag in tags:
        params.setdefault("tag", []).append(tag)
    for tag in excluded_tags:
        params.setdefault("exclude_tag", []).append(tag)
    if category:
        params["category"] = category
    if source_type:
        params["type"] = source_type
    if search:
        params["q"] = search
    if sort and sort in RESOURCE_SORT_OPTIONS:
        params["sort"] = sort
    if page and page > 1:
        params["page"] = page
    if per_page in RESOURCES_PER_PAGE_OPTIONS and per_page != DEFAULT_RESOURCES_PER_PAGE:
        params["per_page"] = per_page
    return redirect(url_for("resources_page", **params))


def generators_redirect():
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    category = request.form.get("return_category", "").strip()
    search = request.form.get("return_search", "").strip()
    sort = request.form.get("return_sort", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {}
    for tag in tags:
        params.setdefault("tag", []).append(tag)
    for tag in excluded_tags:
        params.setdefault("exclude_tag", []).append(tag)
    if category:
        params["category"] = category
    if search:
        params["q"] = search
    if sort:
        params["sort"] = sort
    if page and page > 1:
        params["page"] = page
    if per_page in GENERATORS_PER_PAGE_OPTIONS and per_page != DEFAULT_GENERATORS_PER_PAGE:
        params["per_page"] = per_page
    return redirect(url_for("generators_page", **params))


def characters_redirect(campaign_slug: str):
    groups = normalize_tags(request.form.getlist("return_tag") or request.form.getlist("return_group"))
    excluded_groups = normalize_tags(request.form.getlist("return_exclude_tag") or request.form.getlist("return_exclude_group"))
    search = request.form.get("return_search", "").strip()
    page = request.form.get("return_page", type=int)
    per_page = request.form.get("return_per_page", type=int)
    params = {"campaign": campaign_slug}
    if groups:
        params["tag"] = groups
    if excluded_groups:
        params["exclude_tag"] = excluded_groups
    if search:
        params["q"] = search
    if page and page > 1:
        params["page"] = page
    if per_page in MAPS_PER_PAGE_OPTIONS and per_page != DEFAULT_MAPS_PER_PAGE:
        params["per_page"] = per_page
    return redirect(url_for("characters_page", **params))


def notes_redirect(campaign_slug: str, note_id: str = ""):
    tags = normalize_tags(request.form.getlist("return_tag"))
    excluded_tags = normalize_tags(request.form.getlist("return_exclude_tag"))
    search = request.form.get("return_search", "").strip()
    note_type = request.form.get("return_type", "").strip()
    status = request.form.get("return_status", "").strip()
    sort = request.form.get("return_sort", "").strip()
    reference = request.form.get("return_ref", "").strip()
    date_from = request.form.get("return_date_from", "").strip()
    date_to = request.form.get("return_date_to", "").strip()
    params = {"campaign": campaign_slug}
    if note_id:
        params["note"] = note_id
    if tags:
        params["tag"] = tags
    if excluded_tags:
        params["exclude_tag"] = excluded_tags
    if search:
        params["q"] = search
    if note_type:
        params["type"] = note_type
    if status:
        params["status"] = status
    if sort and sort != "updated":
        params["sort"] = sort
    if reference:
        params["ref"] = reference
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    return redirect(url_for("notes_page", **params))


def gods_redirect(campaign_slug: str, god_id: str = ""):
    domains = normalize_tags(request.form.getlist("return_domain") or request.form.getlist("return_tag"))
    excluded_domains = normalize_tags(request.form.getlist("return_exclude_domain") or request.form.getlist("return_exclude_tag"))
    alignments = normalize_tags(request.form.getlist("return_alignment"))
    excluded_alignments = normalize_tags(request.form.getlist("return_exclude_alignment"))
    ranks = normalize_tags(request.form.getlist("return_rank"))
    excluded_ranks = normalize_tags(request.form.getlist("return_exclude_rank"))
    pantheons = normalize_tags(request.form.getlist("return_pantheon"))
    excluded_pantheons = normalize_tags(request.form.getlist("return_exclude_pantheon"))
    search = request.form.get("return_search", "").strip()
    params = {"campaign": campaign_slug}
    if god_id:
        params["god"] = god_id
    if domains:
        params["domain"] = domains
    if excluded_domains:
        params["exclude_domain"] = excluded_domains
    if alignments:
        params["alignment"] = alignments
    if excluded_alignments:
        params["exclude_alignment"] = excluded_alignments
    if ranks:
        params["rank"] = ranks
    if excluded_ranks:
        params["exclude_rank"] = excluded_ranks
    if pantheons:
        params["pantheon"] = pantheons
    if excluded_pantheons:
        params["exclude_pantheon"] = excluded_pantheons
    if search:
        params["q"] = search
    return redirect(url_for("gods_page", **params))


def save_uploaded_maps(files, scope: str, campaign_slug: str = "", batch_tags=None, single_title: str = "") -> int:
    target_dir = maps_directory(scope, campaign_slug)
    target_dir.mkdir(parents=True, exist_ok=True)
    maps = load_maps(scope, campaign_slug)
    tags_for_upload = normalize_map_item_tags(batch_tags)
    known_tags = load_map_tags(scope, campaign_slug)
    uploaded = 0
    clean_single_title = (single_title or "").strip()
    valid_files = [item for item in files if item and getattr(item, "filename", "")]
    use_single_title = len(valid_files) == 1 and bool(clean_single_title)

    for uploaded_file in files:
        saved_file = save_uploaded_media_file(uploaded_file, target_dir, ALLOWED_IMAGE_EXTENSIONS, "map")
        if saved_file is None:
            continue
        maps.append(
            {
                "id": uuid4().hex,
                "filename": saved_file["filename"],
                "original_filename": saved_file["original_filename"],
                "title": clean_single_title if use_single_title else saved_file["title"],
                "tags": tags_for_upload,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        for tag in tags_for_upload:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        uploaded += 1

    if uploaded:
        save_map_tags(scope, known_tags, campaign_slug)
        save_maps(scope, maps, campaign_slug)
    return uploaded


def save_uploaded_characters(files, campaign_slug: str, batch_groups=None, single_title: str = "") -> int:
    target_dir = characters_directory(campaign_slug)
    target_dir.mkdir(parents=True, exist_ok=True)
    characters = load_characters(campaign_slug)
    tags_for_upload = normalize_character_item_tags(batch_groups)
    known_groups = load_character_tags(campaign_slug)
    uploaded = 0
    clean_single_title = (single_title or "").strip()
    valid_files = [item for item in files if item and getattr(item, "filename", "")]
    use_single_title = len(valid_files) == 1 and bool(clean_single_title)

    for uploaded_file in files:
        saved_file = save_uploaded_media_file(uploaded_file, target_dir, ALLOWED_IMAGE_EXTENSIONS, "character")
        if saved_file is None:
            continue
        characters.append(
            {
                "id": uuid4().hex,
                "filename": saved_file["filename"],
                "original_filename": saved_file["original_filename"],
                "name": clean_single_title if use_single_title else saved_file["title"],
                "age": "",
                "gender": "Иное",
                "race": "",
                "notes": "",
                "tags": tags_for_upload,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        for tag in tags_for_upload:
            if tag.casefold() not in {known_group.casefold() for known_group in known_groups}:
                known_groups.append(tag)
        uploaded += 1

    if uploaded:
        save_character_tags(campaign_slug, known_groups)
        save_characters(campaign_slug, characters)
    return uploaded


def save_uploaded_scenes(files, batch_tags=None, single_title: str = "") -> int:
    target_dir = scenes_directory()
    target_dir.mkdir(parents=True, exist_ok=True)
    scenes = load_scenes()
    tags_for_upload = normalize_scene_item_tags(batch_tags)
    known_tags = load_scene_tags()
    uploaded = 0
    clean_single_title = (single_title or "").strip()
    valid_files = [item for item in files if item and getattr(item, "filename", "")]
    use_single_title = len(valid_files) == 1 and bool(clean_single_title)

    for uploaded_file in files:
        saved_file = save_uploaded_media_file(uploaded_file, target_dir, ALLOWED_IMAGE_EXTENSIONS, "scene")
        if saved_file is None:
            continue
        scenes.append(
            {
                "id": uuid4().hex,
                "filename": saved_file["filename"],
                "original_filename": saved_file["original_filename"],
                "title": clean_single_title if use_single_title else saved_file["title"],
                "tags": tags_for_upload,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        for tag in tags_for_upload:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        uploaded += 1

    if uploaded:
        save_scene_tags(known_tags)
        save_scenes(scenes)
    return uploaded


def save_uploaded_audio(files, category: str, batch_tags=None) -> int:
    target_dir = audio_directory()
    target_dir.mkdir(parents=True, exist_ok=True)
    tracks = load_audio_tracks()
    tags_for_upload = normalize_audio_item_tags(batch_tags)
    known_tags = load_audio_tags()
    known_categories = load_audio_categories()
    clean_category = normalize_audio_category(category)
    uploaded = 0

    if clean_category.casefold() not in {item.casefold() for item in known_categories}:
        known_categories.append(clean_category)

    for uploaded_file in files:
        saved_file = save_uploaded_media_file(uploaded_file, target_dir, ALLOWED_AUDIO_EXTENSIONS, "audio")
        if saved_file is None:
            continue
        tracks.append(
            {
                "id": uuid4().hex,
                "source_type": "file",
                "filename": saved_file["filename"],
                "original_filename": saved_file["original_filename"],
                "title": saved_file["title"],
                "category": clean_category,
                "tags": tags_for_upload,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        for tag in tags_for_upload:
            if tag.casefold() not in {known_tag.casefold() for known_tag in known_tags}:
                known_tags.append(tag)
        uploaded += 1

    if uploaded:
        save_audio_tags(known_tags)
        save_audio_categories(known_categories)
        save_audio_tracks(tracks)
    return uploaded


def delete_maps_by_ids(scope: str, campaign_slug: str, map_ids: set[str]) -> int:
    maps = load_maps(scope, campaign_slug)
    kept_maps = []
    deleted = 0
    target_dir = maps_directory(scope, campaign_slug)

    for item in maps:
        if item["id"] not in map_ids:
            kept_maps.append(item)
            continue

        map_path = target_dir / item["filename"]
        if map_path.exists() and map_path.is_file():
            map_path.unlink()
        deleted += 1

    if deleted:
        save_maps(scope, kept_maps, campaign_slug)
    return deleted


def delete_scenes_by_ids(scene_ids: set[str]) -> int:
    scenes = load_scenes()
    kept_scenes = []
    deleted = 0
    target_dir = scenes_directory()

    for item in scenes:
        if item["id"] not in scene_ids:
            kept_scenes.append(item)
            continue

        image_path = target_dir / item["filename"]
        if image_path.exists() and image_path.is_file():
            image_path.unlink()
        deleted += 1

    if deleted:
        save_scenes(kept_scenes)
    return deleted


def delete_audio_by_ids(track_ids: set[str]) -> int:
    tracks = load_audio_tracks()
    kept_tracks = []
    deleted = 0
    target_dir = audio_directory()

    for item in tracks:
        if item["id"] not in track_ids:
            kept_tracks.append(item)
            continue
        if item.get("source_type") == "file":
            audio_path = target_dir / item.get("filename", "")
            if audio_path.exists() and audio_path.is_file():
                audio_path.unlink()
        if item.get("source_type") == "youtube":
            delete_audio_thumbnail(item.get("thumbnail_filename", ""))
        deleted += 1

    if deleted:
        save_audio_tracks(kept_tracks)
    return deleted


def delete_characters_by_ids(campaign_slug: str, character_ids: set[str]) -> int:
    characters = load_characters(campaign_slug)
    kept_characters = []
    deleted = 0
    target_dir = characters_directory(campaign_slug)

    for item in characters:
        if item["id"] not in character_ids:
            kept_characters.append(item)
            continue

        image_path = target_dir / item["filename"]
        if image_path.exists() and image_path.is_file():
            image_path.unlink()
        deleted += 1

    if deleted:
        save_characters(campaign_slug, kept_characters)
    return deleted


def delete_all_maps(scope: str, campaign_slug: str) -> int:
    target_dir = maps_directory(scope, campaign_slug)
    maps = load_maps(scope, campaign_slug)
    deleted = 0

    if target_dir.exists():
        for path in target_dir.iterdir():
            if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                path.unlink()
                deleted += 1

    save_maps(scope, [], campaign_slug)
    return max(deleted, len(maps))


def delete_all_scenes() -> int:
    target_dir = scenes_directory()
    scenes = load_scenes()
    deleted = 0

    if target_dir.exists():
        for path in target_dir.iterdir():
            if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                path.unlink()
                deleted += 1

    save_scenes([])
    return max(deleted, len(scenes))


def delete_all_characters(campaign_slug: str) -> int:
    target_dir = characters_directory(campaign_slug)
    characters = load_characters(campaign_slug)
    deleted = 0

    if target_dir.exists():
        for path in target_dir.iterdir():
            if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                path.unlink()
                deleted += 1

    save_characters(campaign_slug, [])
    return max(deleted, len(characters))


def rules_by_tag(rules: list[dict], tags: list[str]) -> list[dict]:
    known_tags = tags[:]
    for rule in rules:
        tag = rule.get("tag") or SERVICE_RULE_TAG
        if tag.casefold() not in {item.casefold() for item in known_tags}:
            known_tags.append(tag)

    grouped = []
    for tag in known_tags:
        tag_rules = [rule for rule in rules if (rule.get("tag") or SERVICE_RULE_TAG).casefold() == tag.casefold()]
        grouped.append({"tag": tag, "rules": sorted(tag_rules, key=lambda item: item.get("title", ""))})
    return grouped


def rule_link_for_reference(target: str) -> dict | None:
    target = (target or "").strip()
    if not target:
        return None

    parsed = urlparse(target)
    target_rule_id = parse_qs(parsed.query).get("rule", [""])[0] if parsed.query else ""
    rules = load_rules()

    if target_rule_id:
        rule = next((item for item in rules if item.get("id") == target_rule_id), None)
        if rule:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}

    normalized_target = normalize_rule_reference(target)
    for rule in rules:
        title = rule.get("title", "")
        title_without_alias = re.sub(r"\s*\[[^\]]+\]\s*", " ", title).strip()
        title_aliases = re.findall(r"\[([^\]]+)\]", title)
        book_slug = (rule.get("book_url", "") or "").rstrip("/").rsplit("/", 1)[-1]
        if normalize_rule_reference(rule.get("id", "")) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if rule.get("id", "").startswith("ttg-") and normalize_rule_reference(rule.get("id", "")[4:]) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if normalize_rule_reference(book_slug) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if normalize_rule_reference(rule.get("book_url", "")) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if normalize_rule_reference(title) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if normalize_rule_reference(title_without_alias) == normalized_target:
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}
        if any(normalize_rule_reference(alias) == normalized_target for alias in title_aliases):
            return {"href": url_for("rules_page", rule=rule["id"]), "rule_id": rule["id"], "external": False}

    title_candidates = [
        rule
        for rule in rules
        if normalized_target and normalized_target in normalize_rule_reference(rule.get("title", ""))
    ]
    title_candidates.sort(key=lambda rule: len(rule.get("title", "")))
    title_match = title_candidates[0] if title_candidates else None
    if title_match:
        return {"href": url_for("rules_page", rule=title_match["id"]), "rule_id": title_match["id"], "external": False}

    if parsed.scheme in {"http", "https"}:
        return {"href": target, "rule_id": "", "external": True}
    if re.fullmatch(r"[A-Za-z0-9_-]+", target):
        return {"href": f"https://new.ttg.club/glossary/{target}", "rule_id": "", "external": True}
    return None


def render_rule_content(content: str):
    return render_rule_content_markup(content, rule_link_for_reference)


def render_text_content(content: str):
    return render_text_content_markup(content, rule_link_for_reference)


def render_note_content(content: str):
    return render_note_content_markup(content, rule_link_for_reference)


def demo_empty_state() -> dict:
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "content": None,
    }


def load_demo_state() -> dict:
    state = read_json(DEMO_STATE_PATH, fallback=demo_empty_state())
    if not isinstance(state, dict):
        return demo_empty_state()
    if "updated_at" not in state:
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state.setdefault("content", None)
    return state


def save_demo_state(content: dict | None) -> dict:
    state = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "content": content,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DEMO_STATE_PATH, state)
    return state


def clear_demo_state() -> dict:
    return save_demo_state(None)


def demo_media_payload(kind: str, item: dict, image_url: str, subtitle: str) -> dict:
    return {
        "kind": kind,
        "layout": "image",
        "title": item.get("title") or item.get("name") or "Материал",
        "subtitle": subtitle,
        "image_url": image_url,
        "tags": item.get("tags", []),
    }


def build_demo_content(kind: str, item_id: str, scope: str = "shared", campaign_slug: str = "") -> tuple[dict, int]:
    if not load_settings().get("demo", {}).get("enabled"):
        return {"ok": False, "error": "demo_disabled"}, 403

    kind = str(kind or "").strip()
    item_id = str(item_id or "").strip()
    scope = str(scope or "shared").strip() or "shared"
    campaign_slug = str(campaign_slug or "").strip()
    if not kind or not item_id:
        return {"ok": False, "error": "missing_item"}, 400

    if kind == "map":
        if scope == "campaign" and get_campaign(campaign_slug) is None:
            return {"ok": False, "error": "campaign_not_found"}, 404
        item = find_map_by_id(scope, campaign_slug, item_id)
        if item is None:
            return {"ok": False, "error": "map_not_found"}, 404
        content = demo_media_payload("map", item, map_url(item, scope, campaign_slug), "Карта")
    elif kind == "scene":
        item = find_scene_by_id(item_id)
        if item is None:
            return {"ok": False, "error": "scene_not_found"}, 404
        content = demo_media_payload("scene", item, scene_url(item), "Раздат")
    elif kind == "character":
        if get_campaign(campaign_slug) is None:
            return {"ok": False, "error": "campaign_not_found"}, 404
        item = find_character_by_id(campaign_slug, item_id)
        if item is None:
            return {"ok": False, "error": "character_not_found"}, 404
        fields = [
            {"label": "Возраст", "value": item.get("age", "")},
            {"label": "Пол", "value": item.get("gender", "")},
            {"label": "Раса", "value": item.get("race", "")},
        ]
        content = {
            "kind": "character",
            "layout": "character",
            "title": item.get("name") or "NPC",
            "subtitle": "NPC",
            "image_url": character_url(item, campaign_slug),
            "tags": character_tags(item),
            "fields": [field for field in fields if field["value"]],
            "notes_html": str(render_text_content(item.get("notes", ""))) if item.get("notes") else "",
        }
    elif kind == "rule":
        item = find_rule(item_id)
        if item is None:
            return {"ok": False, "error": "rule_not_found"}, 404
        content = {
            "kind": "rule",
            "layout": "text",
            "title": item.get("title") or "Правило",
            "subtitle": item.get("tag") or SERVICE_RULE_TAG,
            "source": item.get("source", ""),
            "page": item.get("page", ""),
            "content_html": str(render_rule_content(item.get("content", ""))),
        }
    elif kind == "generator":
        roll_payload, status = generator_service.roll_generator(globals(), item_id)
        if status != 200:
            return roll_payload, status
        item = prepare_generator(load_generator(item_id))
        if item is None:
            return {"ok": False, "error": "generator_not_found"}, 404
        subtitle_parts = [
            str(item.get("category") or "").strip(),
            str(roll_payload.get("formula") or "").strip(),
            f"выпало {roll_payload.get('total')}",
        ]
        content = {
            "kind": "generator",
            "layout": "text",
            "title": item.get("title") or "Генератор",
            "subtitle": " · ".join(part for part in subtitle_parts if part),
            "source": roll_payload.get("details", ""),
            "content_html": (
                f'<p class="generator-demo-total">Выпало: {escape(str(roll_payload.get("total", "")))}</p>'
                f'{roll_payload.get("result_html") or ""}'
            ),
        }
    elif kind == "god":
        if get_campaign(campaign_slug) is None:
            return {"ok": False, "error": "campaign_not_found"}, 404
        item = find_god_by_id(campaign_slug, item_id)
        if item is None:
            return {"ok": False, "error": "god_not_found"}, 404
        detail_rows = [
            ("Пантеон", ", ".join(item.get("pantheons", [])) or item.get("pantheon", "")),
            ("Ранг", item.get("rank", "")),
            ("Титулы", ", ".join(item.get("titles", []))),
            ("Символ", item.get("symbol", "")),
            ("Домены", ", ".join(item.get("domains", []))),
        ]
        detail_html = "".join(
            f"<div><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>"
            for label, value in detail_rows
            if value
        )
        details_block = f'<div class="god-demo-fields">{detail_html}</div>' if detail_html else ""
        content = {
            "kind": "god",
            "layout": "text",
            "title": item.get("name") or "Божество",
            "subtitle": " · ".join(part for part in [item.get("alignment", ""), item.get("rank", ""), item.get("pantheon", "")] if part),
            "source": item.get("source", ""),
            "content_html": (
                f'{details_block}'
                f'<div class="god-demo-description">{str(render_note_content(item.get("description") or "Описание пока не добавлено."))}</div>'
            ),
        }
    else:
        return {"ok": False, "error": "unsupported_kind"}, 400

    return {"ok": True, "state": save_demo_state(content)}, 200


def find_map_by_id(scope: str, campaign_slug: str, map_id: str) -> dict | None:
    return media_catalog.find_by_id(load_maps(scope, campaign_slug), map_id)


def find_scene_by_id(scene_id: str) -> dict | None:
    return media_catalog.find_by_id(load_scenes(), scene_id)


def find_character_by_id(campaign_slug: str, character_id: str) -> dict | None:
    return media_catalog.find_by_id(load_characters(campaign_slug), character_id)


def _foundry_link_path(data_dir: Path, relative_path: str, *, require_root: bool = False) -> Path:
    relative = normalize_relative_path(relative_path)
    parts = relative.split("/")
    if require_root and not data_dir.is_dir():
        raise ValidationError("The approved Foundry Data directory is unavailable.")
    if not data_dir.exists():
        return data_dir.joinpath(*parts)
    if len(parts) == 1:
        parent = data_dir.resolve(strict=True)
    else:
        parent = resolve_destination_under(data_dir, "/".join(parts[:-1]))
    return parent / parts[-1]


def _foundry_registry_records() -> list[dict]:
    payload = read_json(FOUNDRY_JUNCTION_REGISTRY_PATH, fallback=[])
    if not isinstance(payload, list):
        return []
    return [
        {
            "relative_path": str(item.get("relative_path", "")).strip(),
            "target": str(item.get("target", "")).strip(),
        }
        for item in payload
        if isinstance(item, dict)
        and str(item.get("relative_path", "")).strip()
        and str(item.get("target", "")).strip()
    ]


def _save_foundry_registry(records: list[dict]) -> None:
    write_json(FOUNDRY_JUNCTION_REGISTRY_PATH, records)


def _foundry_spec_relative_path(settings: dict, spec: dict) -> str:
    data_dir = Path(settings["foundry"]["data_dir"])
    try:
        relative = spec["link"].relative_to(data_dir)
    except ValueError as exc:
        raise ValidationError("Foundry junction escaped its approved root.") from exc
    return normalize_relative_path(str(relative))


def foundry_link_specs(settings: dict | None = None) -> list[dict]:
    settings = settings or load_settings()
    data_dir = Path(settings["foundry"]["data_dir"])
    assets_dir = settings["foundry"]["assets_dir"]
    specs = [
        {
            "label": "Общие карты",
            "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "maps", "shared")),
            "target": maps_directory("shared"),
            "foundry_path": normalize_foundry_relative_path(assets_dir, "maps", "shared"),
        },
        {
            "label": "Раздат",
            "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "scenes")),
            "target": scenes_directory(),
            "foundry_path": normalize_foundry_relative_path(assets_dir, "scenes"),
        }
    ]
    for campaign in get_campaigns():
        slug = campaign["slug"]
        foundry_slug = campaign_foundry_slug(campaign)
        specs.extend(
            [
                {
                    "label": f"Карты кампейна: {campaign.get('name', slug)}",
                    "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "maps", "campaigns", foundry_slug)),
                    "target": maps_directory("campaign", slug),
                    "foundry_path": normalize_foundry_relative_path(assets_dir, "maps", "campaigns", foundry_slug),
                },
                {
                    "label": f"NPC кампейна: {campaign.get('name', slug)}",
                    "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "characters", "campaigns", foundry_slug)),
                    "target": characters_directory(slug),
                    "foundry_path": normalize_foundry_relative_path(assets_dir, "characters", "campaigns", foundry_slug),
                },
            ]
        )
    return specs


def campaign_foundry_link_specs(campaign_slug: str, settings: dict | None = None) -> list[dict]:
    settings = settings or load_settings()
    data_dir = Path(settings["foundry"]["data_dir"])
    assets_dir = settings["foundry"]["assets_dir"]
    campaign = get_campaign(campaign_slug)
    foundry_slug = campaign_foundry_slug(campaign or campaign_slug)
    label_name = (campaign or {}).get("name", campaign_slug)
    return [
        {
            "label": f"Карты кампейна: {label_name}",
            "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "maps", "campaigns", foundry_slug)),
            "target": maps_directory("campaign", campaign_slug),
            "foundry_path": normalize_foundry_relative_path(assets_dir, "maps", "campaigns", foundry_slug),
        },
        {
            "label": f"NPC кампейна: {label_name}",
            "link": _foundry_link_path(data_dir, normalize_foundry_relative_path(assets_dir, "characters", "campaigns", foundry_slug)),
            "target": characters_directory(campaign_slug),
            "foundry_path": normalize_foundry_relative_path(assets_dir, "characters", "campaigns", foundry_slug),
        },
    ]


def remove_campaign_foundry_junctions(campaign_slug: str, settings: dict | None = None) -> int:
    settings = settings or load_settings()
    data_dir = Path(settings["foundry"]["data_dir"])
    requested = {
        _foundry_spec_relative_path(settings, spec)
        for spec in campaign_foundry_link_specs(campaign_slug, settings)
    }
    records = _foundry_registry_records()
    kept = []
    removed = 0
    for record in records:
        relative = record["relative_path"]
        if relative not in requested:
            kept.append(record)
            continue
        try:
            link = _foundry_link_path(data_dir, relative, require_root=True)
        except (OSError, PathBoundaryError, ValidationError):
            kept.append(record)
            continue
        if remove_junction(link, Path(record["target"])):
            removed += 1
        elif link.exists():
            kept.append(record)
    if kept != records:
        _save_foundry_registry(kept)
    return removed


def cleanup_stale_foundry_junctions(settings: dict | None = None) -> int:
    settings = settings or load_settings()
    data_dir = Path(settings["foundry"]["data_dir"])
    active = {
        _foundry_spec_relative_path(settings, spec)
        for spec in foundry_link_specs(settings)
    }
    records = _foundry_registry_records()
    kept = []
    removed = 0
    for record in records:
        relative = record["relative_path"]
        if relative in active:
            kept.append(record)
            continue
        try:
            link = _foundry_link_path(data_dir, relative, require_root=True)
        except (OSError, PathBoundaryError, ValidationError):
            kept.append(record)
            continue
        if remove_junction(link, Path(record["target"])):
            removed += 1
        elif link.exists():
            kept.append(record)
    if kept != records:
        _save_foundry_registry(kept)
    return removed


def foundry_link_statuses(settings: dict | None = None) -> list[dict]:
    return foundry_spec_statuses(foundry_link_specs(settings))


def ensure_foundry_junctions(settings: dict | None = None) -> list[dict]:
    settings = settings or load_settings()
    data_dir = Path(settings["foundry"]["data_dir"])
    if not data_dir.is_dir():
        raise ValidationError("The approved Foundry Data directory is unavailable.")
    cleanup_stale_foundry_junctions(settings)
    specs = foundry_link_specs(settings)
    before = foundry_spec_statuses(specs)
    rows = ensure_foundry_spec_junctions(specs)
    records = _foundry_registry_records()
    known = {record["relative_path"] for record in records}
    for spec, previous, current in zip(specs, before, rows):
        if previous.get("state") != "missing" or current.get("state") != "linked":
            continue
        relative = _foundry_spec_relative_path(settings, spec)
        if relative in known:
            continue
        records.append(
            {
                "relative_path": relative,
                "target": str(Path(spec["target"]).resolve(strict=True)),
            }
        )
        known.add(relative)
    _save_foundry_registry(records)
    return rows


def choose_windows_folder(initial_path: str = "", title: str = "Выберите папку") -> str | None:
    escaped_initial = str(initial_path or "").replace("'", "''")
    escaped_title = str(title or "Выберите папку").replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog\n"
        f"$dialog.Description = '{escaped_title}'\n"
        "$dialog.ShowNewFolderButton = $true\n"
        f"$initial = '{escaped_initial}'\n"
        "if ($initial -and [System.IO.Directory]::Exists($initial)) { $dialog.SelectedPath = $initial }\n"
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.SelectedPath) }\n"
    )
    encoded_command = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-EncodedCommand", encoded_command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    selected = result.stdout.strip()
    return selected or None


def choose_windows_file(initial_path: str = "", title: str = "Выберите файл") -> str | None:
    initial = Path(initial_path).parent if initial_path else Path.home()
    escaped_initial = str(initial if initial.exists() else Path.home()).replace("'", "''")
    escaped_title = str(title or "Выберите файл").replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$dialog = New-Object System.Windows.Forms.OpenFileDialog\n"
        f"$dialog.Title = '{escaped_title}'\n"
        "$dialog.CheckFileExists = $true\n"
        "$dialog.CheckPathExists = $true\n"
        "$dialog.Multiselect = $false\n"
        "$dialog.Filter = 'Все файлы (*.*)|*.*|PDF (*.pdf)|*.pdf|Документы (*.pdf;*.doc;*.docx;*.txt)|*.pdf;*.doc;*.docx;*.txt|Изображения (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'\n"
        f"$dialog.InitialDirectory = '{escaped_initial}'\n"
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.FileName) }\n"
    )
    encoded_command = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-EncodedCommand", encoded_command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    selected = result.stdout.strip()
    return selected or None


def copy_image_to_windows_clipboard(image_path: Path) -> dict:
    return copy_image_to_windows_clipboard_service(image_path, CLIPBOARD_CACHE_DIR, MAX_CLIPBOARD_IMAGE_SIDE)


def thumbnail_response(image_path: Path):
    try:
        thumbnail_path = ensure_thumbnail(image_path.resolve(), THUMBNAIL_CACHE_DIR, DEFAULT_THUMBNAIL_MAX_SIDE)
    except (OSError, ValueError):
        thumbnail_path = None
    if thumbnail_path is None:
        abort(415)
    return send_from_directory(thumbnail_path.parent, thumbnail_path.name, max_age=MEDIA_CACHE_SECONDS)


def copy_image_file_response(image_path: Path, missing_message: str, browser_image_url: str = ""):
    if not image_path.exists():
        return jsonify({"ok": False, "error": missing_message}), 404

    resolved_image = image_path.resolve()

    def operation():
        try:
            clipboard_result = copy_image_to_windows_clipboard(resolved_image)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise ExternalOperationError("Windows clipboard operation failed.") from exc
        return {"ok": True, **clipboard_result}

    job_id = start_local_job("copy_image_to_clipboard", operation)
    return jsonify(
        {
            "ok": True,
            "job_id": job_id,
            "status_url": url_for("local_job_status", job_id=job_id),
        }
    ), 202


@app.context_processor
def inject_globals() -> dict:
    body_classes = ["page"]
    current_settings = load_settings()
    appearance = current_settings.get("appearance", {})
    active_theme = appearance.get("theme", "madness-crown")
    raw_endpoint = (request.endpoint or "unknown").rsplit(".", 1)[-1]
    endpoint = raw_endpoint.replace("_", "-")
    body_classes.append(f"route-{endpoint}")
    body_classes.append(f"theme-{active_theme}")

    if raw_endpoint == "index":
        body_classes.append("page-home")
    elif raw_endpoint == "maps_page":
        body_classes.append("page-maps")
        if request.args.get("campaign"):
            body_classes.append("page-campaign-maps")
    elif raw_endpoint == "scenes_page":
        body_classes.append("page-maps")
        body_classes.append("page-scenes")
    elif raw_endpoint == "audio_page":
        body_classes.append("page-audio")
    elif raw_endpoint == "resources_page":
        body_classes.append("page-resources")
    elif raw_endpoint == "generators_page":
        body_classes.append("page-generators")
    elif raw_endpoint == "characters_page":
        body_classes.append("page-characters")
    elif raw_endpoint == "notes_page":
        body_classes.append("page-notes")
    elif raw_endpoint == "gods_page":
        body_classes.append("page-gods")
    elif raw_endpoint == "campaign_detail":
        body_classes.append("page-campaign")
    elif raw_endpoint == "settings_page":
        body_classes.append("page-settings")
    elif raw_endpoint == "section":
        section_slug = (request.view_args or {}).get("slug", "")
        if section_slug:
            body_classes.append(f"page-{section_slug}")

    campaigns = get_campaigns()
    favorite_group = favorite_campaign_nav_group()
    if favorite_group and not any(item.get("slug") == favorite_group.get("slug") for item in campaigns):
        favorite_group = None
    use_static_spotlight = STORAGE_BACKEND != "sqlite"
    favorite_payload = favorite_service.favorites_payload(globals())

    return {
        "app_name": APP_NAME,
        "asset_version": APP_VERSION,
        "has_ogma_logo": (BASE_DIR / "static" / "img" / "ogma-logo.png").exists(),
        "sections": SECTIONS,
        "global_sections": GLOBAL_SECTIONS,
        "campaign_sections": CAMPAIGN_SECTIONS,
        "campaigns": campaigns,
        "global_session_stats": build_global_session_stats(campaigns),
        "global_session_calendar_events": build_global_session_calendar_events(campaigns),
        "favorite_campaign_group": favorite_group,
        "favorite_campaign_slug": favorite_group.get("slug", "") if favorite_group else "",
        "favorite_panel": favorite_payload,
        "rule_search_items": rule_search_items() if use_static_spotlight else [],
        "character_search_items": build_character_search_items(campaigns) if use_static_spotlight else [],
        "map_search_items": build_map_search_items(campaigns) if use_static_spotlight else [],
        "scene_search_items": build_scene_search_items() if use_static_spotlight else [],
        "audio_search_items": build_audio_search_items() if use_static_spotlight else [],
        "note_search_items": build_note_search_items(campaigns) if use_static_spotlight else [],
        "god_search_items": build_god_search_items(campaigns) if use_static_spotlight else [],
        "resource_search_items": build_resource_search_items() if use_static_spotlight else [],
        "generator_search_items": build_generator_search_items() if use_static_spotlight else [],
        "settings": current_settings,
        "active_theme": active_theme,
        "active_page_art_url": url_for("static", filename=active_page_art_filename(active_theme, body_classes)),
        "theme_options": THEME_OPTIONS,
        "storage_backend": STORAGE_BACKEND,
        "body_classes": " ".join(body_classes),
        "render_text_content": render_text_content,
        "rule_plain_summary": rule_plain_summary,
    }


ensure_storage()


register_domain_routes(app, globals())


def run_application() -> int:
    requested_host = os.environ.get("OGMA_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if requested_host != "127.0.0.1":
        raise RuntimeError("Oghma may only bind to 127.0.0.1.")

    dev_enabled = os.environ.get("OGMA_DEV", "").strip().lower() in {"1", "true", "yes", "on"}

    def run_dev_server() -> None:
        print(
            "[OGHMA DEV] http://oghma.local "
            "(Flask debugger and auto-reloader enabled)",
            flush=True,
        )
        app.run(
            host="127.0.0.1",
            port=LOCAL_SERVER_PORT,
            debug=True,
            use_reloader=True,
        )

    def run_production_server() -> None:
        try:
            from waitress import serve
        except ImportError as exc:
            raise RuntimeError(
                "Waitress is required for the production-local launcher. "
                "Install dependencies from requirements.txt."
            ) from exc
        print(
            "[OGHMA PROD] http://oghma.local "
            "(Waitress, loopback only)",
            flush=True,
        )
        serve(app, host="127.0.0.1", port=LOCAL_SERVER_PORT, threads=4)

    try:
        if dev_enabled and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            # The reloader parent does not bind. Its child acquires the lock.
            run_dev_server()
        else:
            with ServerInstanceLock(LOCAL_SERVER_PORT):
                if dev_enabled:
                    run_dev_server()
                else:
                    run_production_server()
    except ServerAlreadyRunningError as exc:
        print(f"[OGMA] {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run_application())
