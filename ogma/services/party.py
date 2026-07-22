import json
import math
import re
import subprocess
from datetime import datetime
from html import unescape
from pathlib import Path
from uuid import uuid4

from ogma.errors import ValidationError
from ogma.json_store import read_json, write_json
from ogma.safe_arithmetic import UnsafeArithmeticExpression, evaluate_arithmetic
from ogma.safe_paths import PathBoundaryError, normalize_relative_path, resolve_destination_under
from ogma.safe_urls import InternalPath, UnsafeUrl
from ogma.safe_json import load_limited_json_stream


ABILITY_LABELS = {
    "str": "Сила",
    "dex": "Ловкость",
    "con": "Телосложение",
    "int": "Интеллект",
    "wis": "Мудрость",
    "cha": "Харизма",
}

SKILL_LABELS = {
    "acrobatics": "Акробатика",
    "animal handling": "Уход за животными",
    "arcana": "Магия",
    "athletics": "Атлетика",
    "deception": "Обман",
    "history": "История",
    "insight": "Проницательность",
    "intimidation": "Запугивание",
    "investigation": "Анализ",
    "medicine": "Медицина",
    "nature": "Природа",
    "perception": "Внимательность",
    "performance": "Выступление",
    "persuasion": "Убеждение",
    "religion": "Религия",
    "sleight of hand": "Ловкость рук",
    "stealth": "Скрытность",
    "survival": "Выживание",
}

FOUNDRY_SKILL_KEYS = {
    "acr": ("acrobatics", "dex"),
    "ani": ("animal handling", "wis"),
    "arc": ("arcana", "int"),
    "ath": ("athletics", "str"),
    "dec": ("deception", "cha"),
    "his": ("history", "int"),
    "ins": ("insight", "wis"),
    "itm": ("intimidation", "cha"),
    "inv": ("investigation", "int"),
    "med": ("medicine", "wis"),
    "nat": ("nature", "int"),
    "prc": ("perception", "wis"),
    "prf": ("performance", "cha"),
    "per": ("persuasion", "cha"),
    "rel": ("religion", "int"),
    "slt": ("sleight of hand", "dex"),
    "ste": ("stealth", "dex"),
    "sur": ("survival", "wis"),
}

PASSIVE_SKILL_REPORT = [
    ("acrobatics", "Акр"),
    ("animal handling", "Жив"),
    ("arcana", "Маг"),
    ("athletics", "Атл"),
    ("deception", "Обм"),
    ("history", "Ист"),
    ("insight", "Прн"),
    ("intimidation", "Зап"),
    ("investigation", "Анл"),
    ("medicine", "Мед"),
    ("nature", "Прр"),
    ("perception", "Внм"),
    ("performance", "Выс"),
    ("persuasion", "Убж"),
    ("religion", "Рел"),
    ("sleight of hand", "Лвр"),
    ("stealth", "Скр"),
    ("survival", "Вжв"),
]

ENCOUNTER_XP_BY_LEVEL = {
    1: {"low": 50, "medium": 75, "high": 100},
    2: {"low": 100, "medium": 150, "high": 200},
    3: {"low": 150, "medium": 225, "high": 400},
    4: {"low": 250, "medium": 375, "high": 500},
    5: {"low": 500, "medium": 750, "high": 1100},
    6: {"low": 600, "medium": 1000, "high": 1400},
    7: {"low": 750, "medium": 1300, "high": 1700},
    8: {"low": 1000, "medium": 1700, "high": 2100},
    9: {"low": 1300, "medium": 2000, "high": 2600},
    10: {"low": 1600, "medium": 2300, "high": 3100},
    11: {"low": 1900, "medium": 2900, "high": 4100},
    12: {"low": 2200, "medium": 3700, "high": 4700},
    13: {"low": 2600, "medium": 4200, "high": 5400},
    14: {"low": 2900, "medium": 4900, "high": 6200},
    15: {"low": 3300, "medium": 5400, "high": 7800},
    16: {"low": 3800, "medium": 6100, "high": 9800},
    17: {"low": 4500, "medium": 7200, "high": 11700},
    18: {"low": 5000, "medium": 8700, "high": 14200},
    19: {"low": 5500, "medium": 10700, "high": 17200},
    20: {"low": 6400, "medium": 13200, "high": 22000},
}

ENCOUNTER_XP_BY_CR = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}

ENCOUNTER_DIFFICULTIES = [
    ("low", "Низкая"),
    ("medium", "Средняя"),
    ("high", "Высокая"),
]

FOUNDRY_LANGUAGE_LABELS = {
    "common": "Общий",
    "druidic": "Друидический",
    "giant": "Великаний",
    "orc": "Орочий",
    "elvish": "Эльфийский",
    "dwarvish": "Дварфийский",
    "gnomish": "Гномий",
    "goblin": "Гоблинский",
    "halfling": "Полуросликов",
    "draconic": "Драконий",
    "abyssal": "Бездны",
    "celestial": "Небесный",
    "deep": "Глубинная речь",
    "infernal": "Инфернальный",
    "primordial": "Первичный",
    "sylvan": "Сильван",
    "undercommon": "Подземный",
    "sign": "Язык жестов",
    "sign language": "Язык жестов",
    "signlanguage": "Язык жестов",
    "handspeech": "Язык жестов",
    "hand speech": "Язык жестов",
    "thievescant": "Воровской жаргон",
    "thieves' cant": "Воровской жаргон",
    "thieves cant": "Воровской жаргон",
    "cant": "Воровской жаргон",
    "deep speech": "Глубинная речь",
    "deepspeech": "Глубинная речь",
    "giantish": "Великаний",
    "orcish": "Орочий",
    "elven": "Эльфийский",
    "dwarven": "Дварфийский",
    "gnome": "Гномий",
    "goblinish": "Гоблинский",
    "halflingish": "Полуросликов",
    "draconic": "Драконий",
    "общий": "Общий",
    "всеобщий": "Всеобщий",
    "друидический": "Друидический",
    "великанский": "Великаний",
    "великаний": "Великаний",
    "орочий": "Орочий",
    "эльфийский": "Эльфийский",
    "дварфийский": "Дварфийский",
    "дворфийский": "Дварфийский",
    "гномий": "Гномий",
    "гоблинский": "Гоблинский",
    "полуросликов": "Полуросликов",
    "драконий": "Драконий",
    "язык жестов": "Язык жестов",
    "жестовый": "Язык жестов",
}

TOOL_NAME_LABELS = {
    "каменщика": "Инструменты каменщика",
    "инструменты каменщика": "Инструменты каменщика",
    "mason": "Инструменты каменщика",
    "masontools": "Инструменты каменщика",
    "mason's tools": "Инструменты каменщика",
    "картографа": "Инструменты картографа",
    "инструменты картографа": "Инструменты картографа",
    "cartographer": "Инструменты картографа",
    "cartographertools": "Инструменты картографа",
    "cartographer's tools": "Инструменты картографа",
    "алхимика": "Инструменты алхимика",
    "инструменты алхимика": "Инструменты алхимика",
    "пивовара": "Инструменты пивовара",
    "инструменты пивовара": "Инструменты пивовара",
    "каллиграфа": "Инструменты каллиграфа",
    "инструменты каллиграфа": "Инструменты каллиграфа",
    "плотника": "Инструменты плотника",
    "инструменты плотника": "Инструменты плотника",
    "сапожника": "Инструменты сапожника",
    "инструменты сапожника": "Инструменты сапожника",
    "повара": "Инструменты повара",
    "инструменты повара": "Инструменты повара",
    "стеклодува": "Инструменты стеклодува",
    "инструменты стеклодува": "Инструменты стеклодува",
    "ювелира": "Инструменты ювелира",
    "инструменты ювелира": "Инструменты ювелира",
    "кожевника": "Инструменты кожевника",
    "инструменты кожевника": "Инструменты кожевника",
    "кузнеца": "Инструменты кузнеца",
    "инструменты кузнеца": "Инструменты кузнеца",
    "smith": "Инструменты кузнеца",
    "smithtools": "Инструменты кузнеца",
    "smith's tools": "Инструменты кузнеца",
    "художника": "Инструменты художника",
    "инструменты художника": "Инструменты художника",
    "гончара": "Инструменты гончара",
    "инструменты гончара": "Инструменты гончара",
    "жестянщика": "Инструменты жестянщика",
    "инструменты жестянщика": "Инструменты жестянщика",
    "ткача": "Инструменты ткача",
    "инструменты ткача": "Инструменты ткача",
    "резчика по дереву": "Инструменты резчика по дереву",
    "инструменты резчика по дереву": "Инструменты резчика по дереву",
    "woodcarver": "Инструменты резчика по дереву",
    "woodcarver's tools": "Инструменты резчика по дереву",
    "грима": "Набор для грима",
    "набор для грима": "Набор для грима",
    "подделки": "Набор для подделки",
    "набор для подделки": "Набор для подделки",
    "набор травника": "Набор травника",
    "травника": "Набор травника",
    "herbalism": "Набор травника",
    "herbalism kit": "Набор травника",
    "навигатора": "Инструменты навигатора",
    "инструменты навигатора": "Инструменты навигатора",
    "отравителя": "Набор отравителя",
    "набор отравителя": "Набор отравителя",
    "воровские инструменты": "Воровские инструменты",
    "вора": "Воровские инструменты",
    "thieves": "Воровские инструменты",
    "thieves' tools": "Воровские инструменты",
    "наземный транспорт": "Наземный транспорт",
    "водный транспорт": "Водный транспорт",
}

TEXT_SECTION_LABELS = {
    "attacks": "Боевые заметки",
    "background": "Предыстория",
    "personality": "Черты характера",
    "trait": "Черты характера",
    "ideals": "Идеалы",
    "ideal": "Идеалы",
    "bonds": "Привязанности",
    "bond": "Привязанности",
    "flaws": "Слабости",
    "flaw": "Слабости",
    "equipment": "Снаряжение",
    "feats": "Черты",
    "features": "Умения",
    "items": "Предметы",
    "notes-1": "Личные заметки",
    "notes-2": "Заметки 2",
    "prof": "Владения и языки",
}


def party_directory(deps: dict, campaign_slug: str) -> Path:
    return deps["DATA_DIR"] / "campaigns" / campaign_slug / "party"


def party_metadata_path(deps: dict, campaign_slug: str) -> Path:
    return party_directory(deps, campaign_slug) / "party.json"


def party_sync_config_path(deps: dict, campaign_slug: str) -> Path:
    return party_directory(deps, campaign_slug) / "sync.json"


def load_party(deps: dict, campaign_slug: str) -> list[dict]:
    payload = read_json(party_metadata_path(deps, campaign_slug), fallback=[])
    return payload if isinstance(payload, list) else []


def save_party(deps: dict, campaign_slug: str, members: list[dict]) -> None:
    directory = party_directory(deps, campaign_slug)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(party_metadata_path(deps, campaign_slug), members)


def load_party_sync_config(deps: dict, campaign_slug: str) -> dict:
    payload = read_json(party_sync_config_path(deps, campaign_slug), fallback={})
    if not isinstance(payload, dict):
        payload = {}
    fallback = f"ogma-party-export/{campaign_slug}"
    try:
        export_dir = normalize_relative_path(
            str(payload.get("foundry_export_dir", "")).strip() or fallback
        )
    except PathBoundaryError:
        export_dir = fallback
    return {"foundry_export_dir": export_dir}


def save_party_sync_config(deps: dict, campaign_slug: str, config: dict) -> dict:
    directory = party_directory(deps, campaign_slug)
    directory.mkdir(parents=True, exist_ok=True)
    payload = load_party_sync_config(deps, campaign_slug)
    if "foundry_export_dir" in config and config["foundry_export_dir"] is not None:
        try:
            payload["foundry_export_dir"] = normalize_relative_path(
                str(config["foundry_export_dir"]).strip()
            )
        except PathBoundaryError as exc:
            raise ValidationError(
                "Foundry export directory must be relative to Foundry Data."
            ) from exc
    write_json(party_sync_config_path(deps, campaign_slug), payload)
    return payload


def party_page_context(deps: dict, query: dict) -> tuple[str, dict]:
    campaign_slug = query.get("campaign", "").strip()
    campaign = deps["get_campaign"](campaign_slug) if campaign_slug else None
    if campaign is None:
        return "redirect_index", {}
    members = [prepare_party_member(item) for item in load_party(deps, campaign_slug)]
    present_members = [member for member in members if member.get("is_present")]
    open_member_id = query.get("member", "").strip()
    sync_config = load_party_sync_config(deps, campaign_slug)
    return "render", {
        "campaign": campaign,
        "members": members,
        "party_summary": prepare_party_summary(present_members),
        "encounter_budget": prepare_encounter_budget(present_members),
        "present_members_count": len(present_members),
        "open_member_id": open_member_id,
        "party_sync": sync_config,
        "foundry_macro": foundry_export_macro(sync_config["foundry_export_dir"]),
        "nav_sections": deps["CAMPAIGN_SECTIONS"],
        "ability_labels": ABILITY_LABELS,
        "skill_labels": SKILL_LABELS,
    }


def upload_party_members(deps: dict, form, files) -> tuple[str, str, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, 0
    members = load_party(deps, campaign_slug)
    imported = 0
    for uploaded_file in files.getlist("party_files"):
        if not uploaded_file or not uploaded_file.filename:
            continue
        try:
            payload = load_limited_json_stream(uploaded_file.stream)
            member = import_party_member(payload, uploaded_file.filename)
        except Exception:
            continue
        existing_index = next((index for index, item in enumerate(members) if item.get("source_id") == member.get("source_id")), None)
        if existing_index is None:
            members.append(member)
        else:
            preserved_id = members[existing_index].get("id") or member["id"]
            member["id"] = preserved_id
            member["created_at"] = members[existing_index].get("created_at", member["created_at"])
            member["dm_notes"] = members[existing_index].get("dm_notes", member.get("dm_notes", ""))
            members[existing_index] = member
        imported += 1
    if imported:
        save_party(deps, campaign_slug, members)
    return "redirect", campaign_slug, imported


def import_party_member(payload: dict, filename: str) -> dict:
    if is_foundry_character(payload):
        return import_foundry_vtt(payload, filename)
    return import_long_story_short(payload, filename)


def is_foundry_character(payload: dict) -> bool:
    return isinstance(payload, dict) and payload.get("type") == "character" and isinstance(payload.get("system"), dict)


def delete_party_member(deps: dict, form, member_id: str) -> tuple[str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug
    members = [item for item in load_party(deps, campaign_slug) if item.get("id") != member_id]
    save_party(deps, campaign_slug, members)
    return "redirect", campaign_slug


def sync_foundry_party_members(deps: dict, form) -> tuple[str, str, dict]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}
    export_dir = form.get("foundry_export_dir", "").strip()
    config = save_party_sync_config(deps, campaign_slug, {"foundry_export_dir": export_dir} if export_dir else {})
    source_dir = resolve_foundry_export_dir(deps, config["foundry_export_dir"])
    if not source_dir.exists() or not source_dir.is_dir():
        return "redirect", campaign_slug, {
            "imported": 0,
            "updated": 0,
            "errors": ["Каталог экспорта Foundry не найден."],
        }

    members = load_party(deps, campaign_slug)
    imported = 0
    updated = 0
    errors = []
    for path in sorted(source_dir.glob("*.json")):
        try:
            with path.open("rb") as stream:
                payload = load_limited_json_stream(stream)
            member = import_party_member(payload, path.name)
        except Exception as error:
            errors.append(f"{path.name}: {error}")
            continue
        existing_index = next((index for index, item in enumerate(members) if same_party_source(item, member)), None)
        if existing_index is None:
            members.append(member)
            imported += 1
            continue
        preserved_id = members[existing_index].get("id") or member["id"]
        member["id"] = preserved_id
        member["created_at"] = members[existing_index].get("created_at", member["created_at"])
        member["dm_notes"] = members[existing_index].get("dm_notes", member.get("dm_notes", ""))
        member["is_present"] = party_member_is_present(members[existing_index])
        members[existing_index] = member
        updated += 1
    if imported or updated:
        save_party(deps, campaign_slug, members)
    return "redirect", campaign_slug, {"imported": imported, "updated": updated, "errors": errors}


def open_foundry_party_folder(deps: dict, form) -> tuple[str, str, dict]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, {}
    export_dir = form.get("foundry_export_dir", "").strip()
    config = save_party_sync_config(deps, campaign_slug, {"foundry_export_dir": export_dir} if export_dir else {})
    source_dir = resolve_foundry_export_dir(deps, config["foundry_export_dir"])
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return "redirect", campaign_slug, {
            "ok": False,
            "error": "export_directory_unavailable",
        }
    try:
        subprocess.Popen(["explorer.exe", str(source_dir.resolve())])
    except OSError:
        return "redirect", campaign_slug, {
            "ok": False,
            "error": "explorer_unavailable",
        }
    return "redirect", campaign_slug, {"ok": True}


def same_party_source(existing: dict, incoming: dict) -> bool:
    existing_source_id = str(existing.get("source_id", "")).strip()
    incoming_source_id = str(incoming.get("source_id", "")).strip()
    return bool(existing_source_id and incoming_source_id and existing_source_id == incoming_source_id)


def resolve_foundry_export_dir(deps: dict, export_dir: str) -> Path:
    try:
        relative = normalize_relative_path(export_dir.strip().strip('"'))
        return resolve_destination_under(Path(deps["foundry_data_dir"]()), relative)
    except (OSError, PathBoundaryError) as exc:
        raise ValidationError(
            "Foundry export directory is outside the approved Foundry Data root."
        ) from exc


def update_party_member_state(deps: dict, form, member_id: str) -> tuple[str, dict, int]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "error", {"ok": False, "error": "campaign_not_found"}, 404
    members = load_party(deps, campaign_slug)
    member = next((item for item in members if item.get("id") == member_id), None)
    if member is None:
        return "error", {"ok": False, "error": "member_not_found"}, 404
    raw = member.setdefault("raw", {})
    vitality = raw.setdefault("vitality", {})
    resources = raw.setdefault("resources", {})
    field = form.get("field", "").strip()
    value = form.get("value", "").strip()
    try:
        numeric_value = int(value)
    except ValueError:
        return "error", {"ok": False, "error": "bad_value"}, 400
    if field == "is_present":
        member["is_present"] = numeric_value > 0
    elif field in {"hp-current", "hp-temp", "deathFails", "deathSuccesses"}:
        vitality.setdefault(field, {})["value"] = numeric_value
        if field.startswith("death"):
            vitality[field] = numeric_value
    elif field.startswith("resource:"):
        resource_id = field.split(":", 1)[1]
        if resource_id not in resources:
            return "error", {"ok": False, "error": "resource_not_found"}, 404
        resources[resource_id]["current"] = numeric_value
    else:
        return "error", {"ok": False, "error": "bad_field"}, 400
    member["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_party(deps, campaign_slug, members)
    return "ok", {"ok": True, "member": prepare_party_member(member)}, 200


def update_party_dm_notes(deps: dict, form, member_id: str) -> tuple[str, str, str]:
    campaign_slug = form.get("campaign_slug", "").strip()
    if deps["get_campaign"](campaign_slug) is None:
        return "not_found", campaign_slug, ""
    members = load_party(deps, campaign_slug)
    member = next((item for item in members if item.get("id") == member_id), None)
    if member is None:
        return "not_found", campaign_slug, ""
    member["dm_notes"] = str(form.get("dm_notes", ""))
    member["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_party(deps, campaign_slug, members)
    return "redirect", campaign_slug, member_id


def import_long_story_short(payload: dict, filename: str) -> dict:
    raw_data = payload.get("data", payload)
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)
    if not isinstance(raw_data, dict):
        raise ValueError("Long Story Short payload has no character data")
    raw_data = fix_text_tree(raw_data)
    source_id = str(payload.get("_id") or payload.get("id") or payload.get("disabledBlocks", {}).get("_id") or raw_data.get("_id") or "").strip()
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": f"pc-{uuid4().hex[:10]}",
        "source": "long-story-short",
        "source_id": source_id or f"{filename}:{raw_data.get('createdAt', now)}",
        "source_filename": filename,
        "name": value_at(raw_data, "name", "value") or "Без имени",
        "raw": raw_data,
        "created_at": now,
        "updated_at": now,
    }


def import_foundry_vtt(payload: dict, filename: str) -> dict:
    payload = fix_text_tree(payload)
    raw_data = foundry_to_common_raw(payload)
    source_id = str(payload.get("_id") or payload.get("flags", {}).get("core", {}).get("sourceId") or "").strip()
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": f"pc-{uuid4().hex[:10]}",
        "source": "foundry-vtt",
        "source_id": source_id or f"{filename}:{payload.get('name', '')}",
        "source_filename": filename,
        "name": raw_data["name"]["value"],
        "raw": raw_data,
        "raw_foundry": payload,
        "created_at": now,
        "updated_at": now,
    }


def foundry_to_common_raw(payload: dict) -> dict:
    system = payload.get("system", {}) if isinstance(payload.get("system"), dict) else {}
    items = payload.get("items", []) if isinstance(payload.get("items"), list) else []
    class_items = [item for item in items if item.get("type") == "class"]
    subclass_items = [item for item in items if item.get("type") == "subclass"]
    race_item = next((item for item in items if item.get("type") == "race"), None)
    background_item = next((item for item in items if item.get("type") == "background"), None)
    level = sum(int(item.get("system", {}).get("levels") or 0) for item in class_items) or ""
    proficiency = proficiency_bonus(level)
    stats = foundry_stats(system, proficiency, payload, items)
    return {
        "jsonType": "character",
        "template": "foundry-vtt",
        "name": {"value": payload.get("name") or "Без имени"},
        "info": {
            "charClass": {"value": ", ".join(item.get("name", "") for item in class_items if item.get("name"))},
            "charSubclass": {"value": ", ".join(item.get("name", "") for item in subclass_items if item.get("name"))},
            "level": {"value": level},
            "background": {"value": item_name_or_detail(background_item, system, "background")},
            "playerName": {"value": ""},
            "race": {"value": item_name_or_detail(race_item, system, "race")},
            "alignment": {"value": system.get("details", {}).get("alignment", "")},
            "experience": {"value": system.get("details", {}).get("xp", {}).get("value", "")},
        },
        "subInfo": foundry_subinfo(system),
        "proficiency": proficiency,
        "stats": stats,
        "saves": foundry_saves(system, stats, proficiency),
        "skills": foundry_skills(system, stats, proficiency),
        "vitality": foundry_vitality(system, items, stats),
        "weaponsList": foundry_weapons(items, stats, proficiency),
        "text": foundry_text_sections(system, items),
        "coins": foundry_coins(system),
        "resources": foundry_resources(system, items, proficiency, stats),
        "proficiencies": foundry_proficiencies(system, items),
        "avatar": {"webp": payload.get("img", ""), "jpeg": payload.get("img", "")},
    }


def foundry_stats(system: dict, proficiency: int, payload: dict | None = None, items: list[dict] | None = None) -> dict:
    abilities = system.get("abilities", {}) if isinstance(system.get("abilities"), dict) else {}
    base_scores = {}
    for key in ABILITY_LABELS:
        ability = abilities.get(key, {}) if isinstance(abilities.get(key), dict) else {}
        base_scores[key] = int_or_default(ability.get("value"), 10)
    effect_scores = foundry_effect_ability_scores(payload or {}, items or [], base_scores)
    stats = {}
    for key in ABILITY_LABELS:
        score = effect_scores.get(key, base_scores.get(key, 10))
        modifier = ability_modifier(score)
        stats[key] = {"name": key, "score": score, "modifier": modifier, "check": modifier}
    return stats


def foundry_effect_ability_scores(payload: dict, items: list[dict], base_scores: dict) -> dict:
    scores = dict(base_scores)
    actor_effects = payload.get("effects", []) if isinstance(payload.get("effects"), list) else []
    item_effects = [
        effect
        for item in items
        if isinstance(item, dict)
        for effect in (item.get("effects", []) if isinstance(item.get("effects"), list) else [])
        if effect.get("transfer") is True
    ]
    for effect in [*actor_effects, *item_effects]:
        if not isinstance(effect, dict) or effect.get("disabled"):
            continue
        changes = effect.get("changes", []) if isinstance(effect.get("changes"), list) else []
        for change in changes:
            if not isinstance(change, dict):
                continue
            match = re.fullmatch(r"system\.abilities\.(str|dex|con|int|wis|cha)\.value", str(change.get("key", "")))
            if not match:
                continue
            value = int_or_default(change.get("value"), None)
            if value is None:
                continue
            key = match.group(1)
            current = scores.get(key)
            mode = int_or_default(change.get("mode"), 0)
            if mode == 2:
                scores[key] = int_or_default(current, base_scores.get(key, 10)) + value
            elif mode == 3:
                scores[key] = value if current is None else min(current, value)
            elif mode == 4:
                scores[key] = value if current is None else max(current, value)
            elif mode == 5:
                scores[key] = value
    return scores


def foundry_saves(system: dict, stats: dict, proficiency: int) -> dict:
    abilities = system.get("abilities", {}) if isinstance(system.get("abilities"), dict) else {}
    saves = {}
    for key in ABILITY_LABELS:
        ability = abilities.get(key, {}) if isinstance(abilities.get(key), dict) else {}
        prof = numeric(ability.get("proficient"))
        value = int_or_default(stats.get(key, {}).get("modifier"), 0) + math.floor(proficiency * prof)
        saves[key] = {"name": key, "isProf": prof > 0, "value": value}
    return saves


def foundry_skills(system: dict, stats: dict, proficiency: int) -> dict:
    skills = {}
    foundry_skills_data = system.get("skills", {}) if isinstance(system.get("skills"), dict) else {}
    for foundry_key, (common_key, default_ability) in FOUNDRY_SKILL_KEYS.items():
        skill = foundry_skills_data.get(foundry_key, {}) if isinstance(foundry_skills_data.get(foundry_key), dict) else {}
        ability_key = skill.get("ability") or default_ability
        prof = numeric(skill.get("value"))
        ability_mod = int_or_default(stats.get(ability_key, {}).get("modifier"), 0)
        skills[common_key] = {
            "baseStat": ability_key,
            "name": common_key,
            "isProf": prof,
            "value": ability_mod + math.floor(proficiency * prof),
        }
    return skills


def foundry_vitality(system: dict, items: list[dict], stats: dict) -> dict:
    attributes = system.get("attributes", {}) if isinstance(system.get("attributes"), dict) else {}
    hp = attributes.get("hp", {}) if isinstance(attributes.get("hp"), dict) else {}
    death = attributes.get("death", {}) if isinstance(attributes.get("death"), dict) else {}
    return {
        "hp-max": {"value": hp.get("max") or hp.get("value") or 0},
        "hp-current": {"value": hp.get("value") or 0},
        "hp-temp": {"value": hp.get("temp") or 0},
        "hit-die": {"value": foundry_hit_die(items)},
        "hp-dice-current": {"value": ""},
        "ac": {"value": foundry_ac(system, items, stats)},
        "speed": {"value": foundry_speed(system)},
        "deathFails": death.get("failure", 0) if isinstance(death, dict) else 0,
        "deathSuccesses": death.get("success", 0) if isinstance(death, dict) else 0,
    }


def foundry_weapons(items: list[dict], stats: dict, proficiency: int) -> list[dict]:
    weapons = []
    for item in items:
        if item.get("type") != "weapon":
            continue
        system = item.get("system", {}) if isinstance(item.get("system"), dict) else {}
        ability_key = foundry_weapon_ability(system)
        ability_mod = int_or_default(stats.get(ability_key, {}).get("modifier"), 0)
        attack_bonus = ability_mod + proficiency
        damage = foundry_damage_formula(system, ability_mod)
        weapons.append({
            "id": item.get("_id") or item.get("name", ""),
            "name": {"value": item.get("name", "Атака")},
            "mod": {"value": signed(attack_bonus)},
            "dmg": {"value": damage},
            "notes": {"value": html_to_text(system.get("description", {}).get("value", ""))},
            "isProf": True,
        })
    return weapons


def foundry_text_sections(system: dict, items: list[dict]) -> dict:
    details = system.get("details", {}) if isinstance(system.get("details"), dict) else {}
    sections = {}
    biography = html_to_text(details.get("biography", {}).get("value", ""))
    if biography:
        sections["background"] = text_section(biography)
    for source_key, section_key in [
        ("trait", "trait"),
        ("ideal", "ideal"),
        ("bond", "bond"),
        ("flaw", "flaw"),
    ]:
        value = html_to_text(details.get(source_key, ""))
        if value:
            sections[section_key] = text_section(value)

    for key, title, item_types in [
        ("features", "Умения", {"class", "subclass", "race", "background", "feat"}),
        ("equipment", "Снаряжение", {"equipment", "consumable", "tool", "loot", "container"}),
        ("items", "Заклинания", {"spell"}),
    ]:
        lines = []
        for item in items:
            if item.get("type") not in item_types:
                continue
            line = item.get("name", "")
            uses = item.get("system", {}).get("uses", {}) if isinstance(item.get("system"), dict) else {}
            max_uses = uses.get("max") if isinstance(uses, dict) else ""
            if max_uses:
                spent = int_or_default(uses.get("spent"), 0)
                line = f"{line} ({max(0, resolve_foundry_number(max_uses, 0, {}, 0) - spent)}/{max_uses})"
            if line:
                lines.append(f"- {line}")
        if lines:
            sections[key] = text_section(f"{title}\n" + "\n".join(lines))
    return sections


def foundry_resources(system: dict, items: list[dict], proficiency: int, stats: dict) -> dict:
    resources = {}
    system_resources = system.get("resources", {}) if isinstance(system.get("resources"), dict) else {}
    for key, resource in system_resources.items():
        if not isinstance(resource, dict) or not resource.get("label"):
            continue
        resources[f"foundry-{key}"] = {
            "id": f"foundry-{key}",
            "name": resource.get("label"),
            "current": resource.get("value", 0),
            "max": resource.get("max", 0),
            "location": "resources",
        }
    for item in items:
        system_item = item.get("system", {}) if isinstance(item.get("system"), dict) else {}
        uses = system_item.get("uses", {}) if isinstance(system_item.get("uses"), dict) else {}
        max_uses = uses.get("max")
        if not max_uses:
            continue
        maximum = resolve_foundry_number(max_uses, proficiency, stats, int_or_default(max_uses, 0))
        if maximum <= 0:
            continue
        spent = int_or_default(uses.get("spent"), 0)
        resource_id = f"item-{item.get('_id') or item.get('name', '')}"
        resources[resource_id] = {
            "id": resource_id,
            "name": item.get("name", "Ресурс"),
            "current": max(0, maximum - spent),
            "max": maximum,
            "location": item.get("type", "item"),
        }
    return resources


def foundry_coins(system: dict) -> dict:
    currency = system.get("currency", {}) if isinstance(system.get("currency"), dict) else {}
    return {key: {"value": currency.get(key, 0)} for key in ["pp", "gp", "ep", "sp", "cp"]}


def foundry_export_macro(export_dir: str) -> str:
    safe_dir = export_dir.replace("\\", "/").strip("/")
    macro = r'''(async () => {
  const EXPORT_DIR = "__EXPORT_DIR__";

  function escapeHtml(str) {
    return String(str ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function safeFileName(name, fallback = "actor") {
    return String(name ?? fallback)
      .normalize("NFKD")
      .replace(/[\\/:*?"<>|]/g, "")
      .replace(/\s+/g, "_")
      .slice(0, 80) || fallback;
  }

  function styleDarkDialog(html) {
    const app = html.closest(".app");

    app.css({
      background: "#181818",
      border: "1px solid rgba(255,255,255,0.25)",
      "box-shadow": "0 12px 36px rgba(0,0,0,0.7)"
    });

    app.find(".window-content").css({
      background: "transparent",
      padding: "0"
    });

    app.find(".window-header").css({
      background: "#101010",
      color: "#f0f0f0",
      border: "none"
    });

    app.find(".dialog-buttons").css({
      background: "#111",
      padding: "8px"
    });

    app.find(".dialog-buttons button").css({
      background: "#333",
      color: "#fff",
      border: "1px solid #777"
    });
  }

  async function ensureFolder(path) {
    const parts = path.split("/").filter(Boolean);
    let current = "";

    for (const part of parts) {
      current = current ? `${current}/${part}` : part;

      try {
        await FilePicker.createDirectory("data", current);
      } catch (_error) {
        // Папка уже существует.
      }
    }
  }

  async function exportActors(actors) {
    if (!actors.length) {
      ui.notifications.warn("Не выбраны персонажи для экспорта.");
      return;
    }

    await ensureFolder(EXPORT_DIR);

    for (const actor of actors) {
      const data = actor.toObject();

      data._id = actor.id;
      data.name = actor.name;
      data.type = actor.type;

      const fileName = `${safeFileName(actor.name, actor.id)}.${actor.id}.json`;

      const file = new File(
        [JSON.stringify(data, null, 2)],
        fileName,
        { type: "application/json" }
      );

      await FilePicker.upload("data", EXPORT_DIR, file, {
        notify: false,
        overwrite: true
      });
    }

    ui.notifications.info(
      `Огма: экспортировано ${actors.length} персонажей в Data/${EXPORT_DIR}`
    );
  }

  async function resolveActorRef(ref) {
    if (!ref) return null;
    if (ref.actor) return ref.actor;
    if (ref.documentName === "Actor") return ref;
    if (ref instanceof Actor) return ref;

    const id = ref.actorId ?? ref.id ?? ref._id;
    const uuid = ref.actorUuid ?? ref.uuid;

    if (uuid) {
      try {
        const actor = await fromUuid(uuid);
        if (actor) return actor;
      } catch (_) {}
    }

    if (id) return game.actors.get(id) ?? null;

    return null;
  }

  async function getActiveGroupActors() {
    const controlled = canvas.tokens.controlled
      .map(t => t.actor)
      .filter(a => a?.type === "character");

    if (controlled.length) {
      return [...new Map(controlled.map(a => [a.id, a])).values()];
    }

    const candidates = [];

    if (game.actors?.party) candidates.push(game.actors.party);

    candidates.push(
      ...game.actors.filter(actor =>
        ["party", "group"].includes(actor.type) &&
        /основ|main|party|группа/i.test(actor.name)
      )
    );

    candidates.push(
      ...game.actors.filter(actor =>
        ["party", "group"].includes(actor.type)
      )
    );

    const party = candidates.find(Boolean);

    if (!party) return [];

    const rawMembers = [];

    if (party.members instanceof Collection) {
      rawMembers.push(...party.members.contents);
    } else if (Array.isArray(party.members)) {
      rawMembers.push(...party.members);
    }

    const systemMembers = party.system?.members;

    if (Array.isArray(systemMembers)) {
      rawMembers.push(...systemMembers);
    } else if (systemMembers && typeof systemMembers === "object") {
      rawMembers.push(...Object.values(systemMembers));
    }

    const actors = [];

    for (const member of rawMembers) {
      const actor = await resolveActorRef(member);
      if (actor?.type === "character") actors.push(actor);
    }

    return [...new Map(actors.map(a => [a.id, a])).values()];
  }

  const allPlayerActors = game.actors
    .filter(actor => actor.type === "character" && actor.hasPlayerOwner)
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));

  if (!allPlayerActors.length) {
    ui.notifications.warn("Не найдено персонажей игроков для экспорта.");
    return;
  }

  const actorRows = allPlayerActors.map(actor => `
    <label class="ogma-export-row">
      <input type="checkbox" name="actor" value="${escapeHtml(actor.id)}">
      <img src="${escapeHtml(actor.img || "icons/svg/mystery-man.svg")}" class="ogma-export-img">
      <span class="ogma-export-name">${escapeHtml(actor.name)}</span>
    </label>
  `).join("");

  const dialog = new Dialog({
    title: "Огма: экспорт персонажей",
    content: `
      <style>
        .ogma-export-box {
          background: #181818;
          color: #f0f0f0;
          padding: 12px;
          font-size: 13px;
        }

        .ogma-export-muted {
          color: #aaa;
          margin-bottom: 10px;
        }

        .ogma-export-path {
          color: #c9a45c;
          margin-bottom: 10px;
          word-break: break-all;
        }

        .ogma-export-list {
          display: flex;
          flex-direction: column;
          gap: 5px;
          max-height: 420px;
          overflow-y: auto;
          padding-right: 4px;
        }

        .ogma-export-row {
          display: flex;
          align-items: center;
          gap: 8px;
          background: #101010;
          border: 1px solid #333;
          border-radius: 6px;
          padding: 7px 8px;
          cursor: pointer;
        }

        .ogma-export-row:hover {
          background: #242424;
          border-color: #c9a45c;
        }

        .ogma-export-img {
          width: 28px;
          height: 28px;
          object-fit: cover;
          border-radius: 4px;
          border: 1px solid #444;
        }

        .ogma-export-name {
          color: #fff;
          font-weight: 700;
        }
      </style>

      <div class="ogma-export-box">
        <div class="ogma-export-muted">
          Выбери персонажей для экспорта.
        </div>

        <div class="ogma-export-path">
          Папка: Data/${escapeHtml(EXPORT_DIR)}
        </div>

        <div class="ogma-export-list">
          ${actorRows}
        </div>
      </div>
    `,
    buttons: {
      selected: {
        label: "Экспорт выбранных",
        callback: async html => {
          const ids = html.find('input[name="actor"]:checked')
            .map((_, el) => el.value)
            .get();

          const actors = ids
            .map(id => game.actors.get(id))
            .filter(Boolean);

          await exportActors(actors);
        }
      },

      activeGroup: {
        label: "Из активной группы",
        callback: async () => {
          const actors = await getActiveGroupActors();
          await exportActors(actors);
        }
      },

      all: {
        label: "Экспортировать всех",
        callback: async () => {
          await exportActors(allPlayerActors);
        }
      },

      close: {
        label: "Закрыть"
      }
    },
    default: "selected",
    render: styleDarkDialog
  });

  dialog.render(true);

  setTimeout(() => {
    dialog.setPosition({
      width: 560,
      height: "auto"
    });
  }, 100);
})();'''
    return macro.replace("__EXPORT_DIR__", safe_dir)


def foundry_proficiencies(system: dict, items: list[dict]) -> dict:
    traits = system.get("traits", {}) if isinstance(system.get("traits"), dict) else {}
    languages_data = traits.get("languages", {}) if isinstance(traits.get("languages"), dict) else {}
    language_values = languages_data.get("value", []) if isinstance(languages_data.get("value"), list) else []
    languages = [normalize_language_name(value) for value in language_values if value]
    if languages_data.get("custom"):
        languages.extend(normalize_language_name(value) for value in normalize_text_list(languages_data.get("custom")))
    tools = [normalize_tool_name(item.get("name", "")) for item in items if item.get("type") == "tool" and item.get("name")]
    return {
        "languages": unique_clean(languages),
        "tools": unique_clean(tools),
    }


def normalize_language_name(value) -> str:
    text = clean_display_name(value)
    if not text:
        return ""
    key = text.casefold()
    compact_key = re.sub(r"[\s_\-'/()]+", "", key)
    return FOUNDRY_LANGUAGE_LABELS.get(key) or FOUNDRY_LANGUAGE_LABELS.get(compact_key) or text


def normalize_tool_name(value) -> str:
    text = clean_display_name(value)
    if not text:
        return ""
    key = text.casefold()
    compact_key = re.sub(r"[\s_\-'/()]+", "", key)
    return TOOL_NAME_LABELS.get(key) or TOOL_NAME_LABELS.get(compact_key) or text


def prepare_party_member(member: dict) -> dict:
    raw = member.get("raw", {}) if isinstance(member.get("raw"), dict) else {}
    info = raw.get("info", {}) if isinstance(raw.get("info"), dict) else {}
    vitality = raw.get("vitality", {}) if isinstance(raw.get("vitality"), dict) else {}
    stats = raw.get("stats", {}) if isinstance(raw.get("stats"), dict) else {}
    saves = raw.get("saves", {}) if isinstance(raw.get("saves"), dict) else {}
    skills = raw.get("skills", {}) if isinstance(raw.get("skills"), dict) else {}
    resources = raw.get("resources", {}) if isinstance(raw.get("resources"), dict) else {}
    text = raw.get("text", {}) if isinstance(raw.get("text"), dict) else {}
    weapons = raw.get("weaponsList", []) if isinstance(raw.get("weaponsList"), list) else []
    text_sections = prepare_text_sections(text)
    proficiency = int_or_default(raw.get("proficiency"), proficiency_bonus(field_value(info, "level") or 1))
    normalized_stats = normalize_stats(stats)
    prepared_skills = prepare_skills(normalized_stats, skills, proficiency)
    proficiency_sections = prepare_proficiency_sections(raw, text_sections)
    prepared = {
        **member,
        "source_label": source_label(member.get("source", "")),
        "is_present": party_member_is_present(member),
        "dm_notes": str(member.get("dm_notes", "")),
        "name": value_at(raw, "name", "value") or member.get("name") or "Без имени",
        "class": field_value(info, "charClass"),
        "subclass": field_value(info, "charSubclass"),
        "level": field_value(info, "level"),
        "race": field_value(info, "race"),
        "background": field_value(info, "background"),
        "alignment": field_value(info, "alignment"),
        "player_name": field_value(info, "playerName"),
        "avatar": avatar_url(raw, str(member.get("id", ""))),
        "summary": member_summary(raw),
        "vitality": {
            "ac": field_value(vitality, "ac"),
            "speed": field_value(vitality, "speed"),
            "hp_current": field_value(vitality, "hp-current"),
            "hp_max": field_value(vitality, "hp-max"),
            "hp_temp": field_value(vitality, "hp-temp"),
            "hit_die": field_value(vitality, "hit-die"),
            "hit_dice_current": field_value(vitality, "hp-dice-current"),
            "death_fails": vitality.get("deathFails", 0),
            "death_successes": vitality.get("deathSuccesses", 0),
        },
        "stats": prepare_stats(normalized_stats),
        "saves": prepare_saves(normalized_stats, saves, proficiency),
        "skills": prepared_skills,
        "passive_skills": prepare_passive_skills(prepared_skills),
        "card_passive_skills": prepare_card_passive_skills(prepared_skills),
        "proficiency_sections": proficiency_sections,
        "languages": proficiency_items(proficiency_sections, "languages"),
        "tools": proficiency_items(proficiency_sections, "tools"),
        "weapons": prepare_weapons(weapons, normalized_stats),
        "resources": prepare_resources(resources),
        "coins": prepare_coins(raw.get("coins", {})),
        "text_sections": text_sections,
        "important_text_sections": [
            section
            for section in text_sections
            if section.get("key") in {"background", "notes-1", "personality", "trait", "ideals", "ideal", "bonds", "bond", "flaws", "flaw"}
        ],
        "raw_json": json.dumps(raw, ensure_ascii=False, indent=2),
    }
    return prepared


def party_member_is_present(member: dict) -> bool:
    value = member.get("is_present", True)
    if isinstance(value, str):
        return value.strip().casefold() not in {"0", "false", "no", "off", "нет"}
    return value is not False


def prepare_party_summary(members: list[dict]) -> dict:
    levels = [int_or_default(member.get("level"), 0) for member in members if int_or_default(member.get("level"), 0) > 0]
    average_level = round(sum(levels) / len(levels), 1) if levels else ""
    average_level_label = str(int(average_level)) if average_level and float(average_level).is_integer() else str(average_level or "")
    passive_keys = [key for key, _short in PASSIVE_SKILL_REPORT]
    best_passives = {}
    for key in passive_keys:
        values = []
        for member in members:
            passive_by_key = {skill["key"]: skill for skill in member.get("passive_skills", [])}
            skill = passive_by_key.get(key)
            if skill:
                values.append(int_or_default(skill.get("passive"), 0))
        best_passives[key] = max(values) if values else None
    passive_rows = []
    for member in members:
        passive_by_key = {skill["key"]: skill for skill in member.get("passive_skills", [])}
        row_skills = []
        for key in passive_keys:
            skill = passive_by_key.get(key)
            value = int_or_default(skill.get("passive"), 0) if skill else ""
            row_skills.append({
                "key": key,
                "value": value,
                "is_best": value != "" and best_passives.get(key) == value,
                "prof_marker": skill.get("prof_marker", "") if skill else "",
                "prof_label": skill.get("prof_label", "") if skill else "",
            })
        passive_rows.append({
            "name": member.get("name", "Без имени"),
            "skills": row_skills,
            "languages": member.get("languages", []),
            "tools": member.get("tools", []),
        })
    return {
        "count": len(members),
        "average_level": average_level_label,
        "passive_labels": [{"key": key, "label": SKILL_LABELS.get(key, key), "short": short} for key, short in PASSIVE_SKILL_REPORT],
        "passive_rows": passive_rows,
        "languages": aggregate_member_items(members, "languages"),
        "tools": aggregate_member_items(members, "tools"),
    }


def cr_to_number(cr: str) -> float:
    if "/" in cr:
        left, right = cr.split("/", 1)
        denominator = int_or_default(right, 1) or 1
        return int_or_default(left, 0) / denominator
    return float(int_or_default(cr, 0))


def encounter_level_rows(members: list[dict]) -> list[dict]:
    rows = []
    for member in members:
        level = int_or_default(member.get("level"), 0)
        if 1 <= level <= 20:
            rows.append({"name": member.get("name", "Без имени"), "level": level})
    return rows


def encounter_budget_for_levels(levels: list[int], difficulty: str) -> int:
    return sum(ENCOUNTER_XP_BY_LEVEL[level][difficulty] for level in levels if level in ENCOUNTER_XP_BY_LEVEL)


def encounter_single_suggestions(budget: int, party_size: int, average_level: float) -> list[dict]:
    suggestions = []
    for cr, xp in ENCOUNTER_XP_BY_CR.items():
        count = budget // xp if xp else 0
        if count <= 0:
            continue
        notes = []
        cr_value = cr_to_number(cr)
        if count > party_size * 2:
            notes.append("много существ")
        if cr_value > average_level:
            notes.append("ПО выше среднего уровня")
        if cr == "0":
            notes.append("ПО 0 лучше использовать осторожно")
        suggestions.append({
            "cr": cr,
            "xp": xp,
            "count": count,
            "total": count * xp,
            "left": budget - count * xp,
            "notes": notes,
        })
    return list(reversed(suggestions))[:14]


def encounter_pair_suggestions(budget: int) -> list[dict]:
    suggestions = []
    cr_items = list(ENCOUNTER_XP_BY_CR.items())
    for index, (left_cr, left_xp) in enumerate(cr_items):
        for right_cr, right_xp in cr_items[index:]:
            total = left_xp + right_xp
            if total <= budget:
                suggestions.append({"left_cr": left_cr, "right_cr": right_cr, "total": total, "left": budget - total})
    return sorted(suggestions, key=lambda item: (item["left"], -item["total"]))[:8]


def encounter_boss_minion_suggestions(budget: int, party_size: int) -> list[dict]:
    suggestions = []
    for boss_cr, boss_xp in ENCOUNTER_XP_BY_CR.items():
        if boss_xp >= budget:
            continue
        for minion_cr, minion_xp in ENCOUNTER_XP_BY_CR.items():
            minion_count = (budget - boss_xp) // minion_xp if minion_xp else 0
            if minion_count < 2 or minion_count > max(12, party_size * 3):
                continue
            total = boss_xp + minion_count * minion_xp
            suggestions.append({
                "boss_cr": boss_cr,
                "minion_cr": minion_cr,
                "minion_count": minion_count,
                "total": total,
                "left": budget - total,
            })
    return sorted(suggestions, key=lambda item: (item["left"], -item["total"]))[:8]


def prepare_encounter_budget(members: list[dict]) -> dict:
    rows = encounter_level_rows(members)
    levels = [row["level"] for row in rows]
    if not levels:
        return {
            "ok": False,
            "message": "В группе нет персонажей с уровнем от 1 до 20.",
            "members": [],
            "difficulties": [],
        }
    party_size = len(levels)
    average_level = round(sum(levels) / party_size, 1)
    min_level = min(levels)
    max_level = max(levels)
    difficulties = []
    for key, label in ENCOUNTER_DIFFICULTIES:
        budget = encounter_budget_for_levels(levels, key)
        difficulties.append({
            "key": key,
            "label": label,
            "budget": budget,
            "single": encounter_single_suggestions(budget, party_size, average_level),
            "pairs": encounter_pair_suggestions(budget),
            "boss_minions": encounter_boss_minion_suggestions(budget, party_size),
        })
    warnings = [
        "Если существ больше чем вдвое больше персонажей, бой может стать заметно опаснее из-за количества действий.",
        "Более 2-3 разных статблоков усложняют ведение сцены за столом.",
        "Существо с ПО выше среднего уровня группы может быстро вывести героя из строя одним действием.",
        "Существа с ПО 0 лучше использовать осторожно, особенно если они не дают опыта.",
    ]
    if max_level - min_level >= 3:
        warnings.insert(0, "В группе большой разброс уровней: младшие персонажи могут оказаться под гораздо большим риском.")
    return {
        "ok": True,
        "members": rows,
        "count": party_size,
        "average_level": average_level,
        "level_summary": ", ".join(f"{level} ур. x {levels.count(level)}" for level in sorted(set(levels))),
        "difficulties": difficulties,
        "warnings": warnings,
    }


def favorite_party_summary_payload(deps: dict) -> dict:
    campaign_slug = deps["favorite_campaign_slug"]()
    if not campaign_slug:
        return {"ok": False, "error": "no_favorite_campaign", "message": "Избранный мир не выбран."}
    campaign = deps["get_campaign"](campaign_slug)
    if campaign is None:
        return {"ok": False, "error": "favorite_campaign_missing", "message": "Избранный мир не найден."}
    members = [prepare_party_member(item) for item in load_party(deps, campaign_slug)]
    present_members = [member for member in members if member.get("is_present")]
    if not present_members:
        return {
            "ok": True,
            "campaign": {"slug": campaign_slug, "name": campaign.get("name", campaign_slug)},
            "count": 0,
            "members": [],
            "languages": [],
            "tools": [],
            "passive_labels": [{"key": key, "label": SKILL_LABELS.get(key, key), "short": short} for key, short in PASSIVE_SKILL_REPORT],
        }
    summary = prepare_party_summary(present_members)
    passive_by_name = {row["name"]: row for row in summary["passive_rows"]}
    return {
        "ok": True,
        "campaign": {"slug": campaign_slug, "name": campaign.get("name", campaign_slug)},
        "count": summary["count"],
        "average_level": summary["average_level"],
        "languages": [item["name"] for item in summary["languages"]],
        "tools": [item["name"] for item in summary["tools"]],
        "passive_labels": summary["passive_labels"],
        "members": [
            {
                "id": member.get("id", ""),
                "name": member.get("name", "Без имени"),
                "ac": member.get("vitality", {}).get("ac") or 0,
                "speed": member.get("vitality", {}).get("speed") or 0,
                "languages": member.get("languages", []),
                "tools": member.get("tools", []),
                "passives": passive_by_name.get(member.get("name", ""), {}).get("skills", []),
            }
            for member in members
            if member.get("is_present")
        ],
    }


def normalize_stats(stats: dict) -> dict:
    normalized = {}
    for key in ABILITY_LABELS:
        stat = stats.get(key, {}) if isinstance(stats.get(key), dict) else {}
        score = int_or_default(stat.get("score"), 10)
        modifier = ability_modifier(score)
        normalized[key] = {**stat, "score": score, "modifier": modifier, "check": modifier}
    return normalized


def prepare_stats(stats: dict) -> list[dict]:
    items = []
    for key, label in ABILITY_LABELS.items():
        stat = stats.get(key, {}) if isinstance(stats.get(key), dict) else {}
        items.append({"key": key, "label": label, "score": stat.get("score", ""), "modifier": signed(stat.get("modifier", 0)), "check": signed(stat.get("check", stat.get("modifier", 0)))})
    return items


def prepare_saves(stats: dict, saves: dict, proficiency: int) -> list[dict]:
    items = []
    for key, label in ABILITY_LABELS.items():
        stat = stats.get(key, {}) if isinstance(stats.get(key), dict) else {}
        save = saves.get(key, {}) if isinstance(saves.get(key), dict) else {}
        prof_multiplier = proficiency_multiplier(save)
        modifier = int_or_default(stat.get("modifier"), 0) + math.floor(proficiency * prof_multiplier)
        items.append({"key": key, "label": label, "value": signed(modifier), "is_prof": prof_multiplier > 0})
    return items


def prepare_skills(stats: dict, skills: dict, proficiency: int) -> list[dict]:
    items = []
    for key, skill in sorted(skills.items(), key=lambda item: SKILL_LABELS.get(item[0], item[0])):
        if not isinstance(skill, dict):
            continue
        base = skill.get("baseStat", "")
        stat = stats.get(base, {}) if isinstance(stats.get(base), dict) else {}
        prof_multiplier = proficiency_multiplier(skill)
        numeric_value = int_or_default(stat.get("modifier"), 0) + math.floor(proficiency * prof_multiplier)
        items.append({
            "key": key,
            "label": SKILL_LABELS.get(key, key),
            "base": ABILITY_LABELS.get(base, base.upper()),
            "value": signed(numeric_value),
            "numeric_value": numeric_value,
            "is_prof": prof_multiplier > 0,
            "prof_multiplier": prof_multiplier,
            "prof_marker": skill_proficiency_marker(prof_multiplier),
            "prof_label": skill_proficiency_label(prof_multiplier),
        })
    return items


def skill_proficiency_marker(multiplier: float) -> str:
    if multiplier >= 2:
        return "⊙"
    if multiplier > 0:
        return "•"
    return ""


def skill_proficiency_label(multiplier: float) -> str:
    if multiplier >= 2:
        return "Компетенция"
    if multiplier > 0:
        return "Владение"
    return ""


def proficiency_multiplier(item: dict) -> float:
    for key in ("isProf", "proficient", "prof"):
        if key in item:
            value = item.get(key)
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return numeric(value)
    return 0.0


def prepare_passive_skills(skills: list[dict]) -> list[dict]:
    passive = []
    for skill in skills:
        value = int_or_default(skill.get("numeric_value"), 0) + 10
        passive.append({**skill, "passive": value})
    return passive


def prepare_card_passive_skills(skills: list[dict]) -> list[dict]:
    priority = ["perception", "insight", "investigation"]
    by_key = {skill.get("key"): skill for skill in prepare_passive_skills(skills)}
    return [by_key[key] for key in priority if key in by_key]


def prepare_weapons(weapons: list[dict], stats: dict) -> list[dict]:
    prepared = []
    for weapon in weapons:
        if not isinstance(weapon, dict):
            continue
        damage = field_value(weapon, "dmg")
        prepared.append({
            "id": weapon.get("id", ""),
            "name": field_value(weapon, "name") or "Атака",
            "mod": field_value(weapon, "mod") or "+0",
            "damage": damage,
            "dice_damage": resolve_formula_tokens(damage, stats),
            "notes": field_value(weapon, "notes"),
            "is_prof": bool(weapon.get("isProf")),
        })
    return prepared


def resolve_formula_tokens(formula, stats: dict) -> str:
    value = str(formula or "").strip()
    for key in ABILITY_LABELS:
        stat = stats.get(key, {}) if isinstance(stats.get(key), dict) else {}
        modifier = stat.get("modifier", 0)
        value = value.replace(f"[{key.upper()}]", signed(modifier))
    while "++" in value:
        value = value.replace("++", "+")
    value = value.replace("+-", "-")
    return value


def prepare_resources(resources: dict) -> list[dict]:
    items = []
    for resource_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        items.append({
            "id": resource_id,
            "name": resource.get("name", "Ресурс"),
            "current": resource.get("current", 0),
            "max": resource.get("max", 0),
            "icon": resource.get("icon", ""),
            "location": resource.get("location", ""),
        })
    return sorted(items, key=lambda item: item["name"])


def prepare_text_sections(text: dict) -> list[dict]:
    sections = []
    for key, value in text.items():
        if not isinstance(value, dict):
            continue
        body = tiptap_to_text(value_at(value, "value", "data") or value_at(value, "data") or value.get("value"))
        if body.strip():
            sections.append({"key": key, "title": TEXT_SECTION_LABELS.get(key, key), "body": body.strip()})
    return sections


def prepare_proficiency_sections(raw: dict, text_sections: list[dict]) -> list[dict]:
    explicit = raw.get("proficiencies", {}) if isinstance(raw.get("proficiencies"), dict) else {}
    sections = []
    languages = explicit.get("languages", []) if isinstance(explicit.get("languages"), list) else []
    languages = [normalize_language_name(language) for language in languages]
    tools = explicit.get("tools", []) if isinstance(explicit.get("tools"), list) else []
    tools = [normalize_tool_name(tool) for tool in tools]
    prof_section = next((section for section in text_sections if section.get("key") == "prof"), None)
    parsed = parse_proficiency_body(prof_section.get("body", "") if prof_section else "")
    languages.extend(parsed.get("languages", []))
    tools.extend(parsed.get("tools", []))
    if languages:
        sections.append({"key": "languages", "title": "Языки", "items": unique_clean(languages), "body": ""})
    if tools:
        sections.append({"key": "tools", "title": "Инструменты", "items": unique_clean(tools), "body": ""})
    if parsed.get("weapons"):
        sections.append({"key": "weapons-prof", "title": "Оружие", "items": unique_clean(parsed["weapons"]), "body": ""})
    if parsed.get("armor"):
        sections.append({"key": "armor-prof", "title": "Доспехи", "items": unique_clean(parsed["armor"]), "body": ""})
    if sections:
        return sections
    if prof_section and prof_section.get("body"):
        return [{"key": "prof", "title": "Владения и языки", "items": [], "body": prof_section["body"]}]
    return []


def parse_proficiency_body(body: str) -> dict:
    parsed = {"languages": [], "tools": [], "weapons": [], "armor": []}
    field_map = {
        "языки": "languages",
        "язык": "languages",
        "languages": "languages",
        "инструменты": "tools",
        "инструмент": "tools",
        "tools": "tools",
        "tool": "tools",
        "оружие": "weapons",
        "оружия": "weapons",
        "weapons": "weapons",
        "weapon": "weapons",
        "доспехи": "armor",
        "доспех": "armor",
        "броня": "armor",
        "armor": "armor",
        "armour": "armor",
    }
    for line in str(body or "").splitlines():
        match = re.match(r"\s*([^:：]+)\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue
        label = clean_display_name(match.group(1)).casefold()
        key = field_map.get(label)
        if not key:
            continue
        values = split_proficiency_values(match.group(2))
        if key == "languages":
            values = [normalize_language_name(value) for value in values]
        elif key == "tools":
            values = [normalize_tool_name(value) for value in values]
        parsed[key].extend(value for value in values if value)
    return {key: unique_clean(values) for key, values in parsed.items()}


def split_proficiency_values(value: str) -> list[str]:
    normalized = re.sub(r"\s+(?:и|and)\s+", ",", str(value or ""), flags=re.IGNORECASE)
    return [clean_display_name(part) for part in re.split(r"[,;]+", normalized) if clean_display_name(part)]


def proficiency_items(sections: list[dict], key: str) -> list[str]:
    section = next((item for item in sections if item.get("key") == key), None)
    if not section:
        return []
    return unique_clean(clean_display_name(item) for item in section.get("items", []))


def aggregate_member_items(members: list[dict], field: str) -> list[dict]:
    owners_by_item = {}
    labels_by_item = {}
    for member in members:
        for item in member.get(field, []):
            label = clean_display_name(item)
            if not label:
                continue
            key = label.casefold()
            labels_by_item.setdefault(key, label)
            owners_by_item.setdefault(key, []).append(member.get("name", "Без имени"))
    return [
        {"name": labels_by_item[key], "owners": owners_by_item[key], "count": len(owners_by_item[key])}
        for key in sorted(labels_by_item, key=lambda value: labels_by_item[value])
    ]


def prepare_coins(coins: dict) -> list[dict]:
    labels = [("pp", "PP"), ("gp", "GP"), ("ep", "EP"), ("sp", "SP"), ("cp", "CP")]
    return [{"key": key, "label": label, "value": field_value(coins, key) or 0} for key, label in labels]


def unique_clean(items: list) -> list[str]:
    seen = set()
    cleaned = []
    for item in items:
        value = clean_display_name(item)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            cleaned.append(value)
    return cleaned


def normalize_text_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;\n]+", str(value or "")) if part.strip()]


def clean_display_name(value) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s*\[[^\]]*[A-Za-z][^\]]*\]\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,;")


def source_label(source: str) -> str:
    if source == "foundry-vtt":
        return "Foundry VTT"
    if source == "long-story-short":
        return "Long Story Short"
    return "JSON"


def member_summary(raw: dict) -> str:
    info = raw.get("info", {}) if isinstance(raw.get("info"), dict) else {}
    parts = [field_value(info, "race"), field_value(info, "charClass"), f"{field_value(info, 'level')} ур." if field_value(info, "level") else ""]
    return " · ".join(str(part) for part in parts if part)


def avatar_url(raw: dict, member_id: str = "") -> str:
    avatar = raw.get("avatar", {}) if isinstance(raw.get("avatar"), dict) else {}
    return normalize_foundry_asset_url(
        str(avatar.get("webp") or avatar.get("jpeg") or "").strip(),
        member_id,
    )


def normalize_foundry_asset_url(path: str, member_id: str = "") -> str:
    if not path:
        return ""
    if path.startswith(("/media/", "/static/")):
        try:
            return InternalPath.parse(path).value
        except UnsafeUrl:
            return ""
    if not member_id:
        return ""
    try:
        foundry_asset_relative_path(path)
    except PathBoundaryError:
        return ""
    return f"/party/{member_id}/asset"


def foundry_asset_relative_path(path: str) -> str:
    value = str(path or "").strip()
    if not value or "?" in value or "#" in value:
        raise PathBoundaryError("Foundry asset path is invalid.")
    return normalize_relative_path(value.lstrip("/"))


def party_member_asset_relative_path(deps: dict, member_id: str) -> str | None:
    for campaign in deps["get_campaigns"]():
        campaign_slug = str(campaign.get("slug", "")).strip()
        member = next(
            (item for item in load_party(deps, campaign_slug) if item.get("id") == member_id),
            None,
        )
        if member is None:
            continue
        raw = member.get("raw", {}) if isinstance(member.get("raw"), dict) else {}
        avatar = raw.get("avatar", {}) if isinstance(raw.get("avatar"), dict) else {}
        raw_path = str(avatar.get("webp") or avatar.get("jpeg") or "").strip()
        if raw_path.startswith(("/media/", "/static/")):
            return None
        try:
            return foundry_asset_relative_path(raw_path)
        except PathBoundaryError:
            return None
    return None


def item_name_or_detail(item: dict | None, system: dict, detail_key: str) -> str:
    if item and item.get("name"):
        return item.get("name", "")
    return str(system.get("details", {}).get(detail_key, "") or "")


def foundry_subinfo(system: dict) -> dict:
    details = system.get("details", {}) if isinstance(system.get("details"), dict) else {}
    return {
        "age": {"value": details.get("age", "")},
        "height": {"value": details.get("height", "")},
        "weight": {"value": details.get("weight", "")},
        "eyes": {"value": details.get("eyes", "")},
        "skin": {"value": details.get("skin", "")},
        "hair": {"value": details.get("hair", "")},
    }


def proficiency_bonus(level) -> int:
    level_number = int_or_default(level, 1)
    return max(2, math.ceil(level_number / 4) + 1)


def ability_modifier(score) -> int:
    return math.floor((int_or_default(score, 10) - 10) / 2)


def numeric(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def int_or_default(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def foundry_hit_die(items: list[dict]) -> str:
    dice = []
    for item in items:
        if item.get("type") != "class":
            continue
        hit_die = item.get("system", {}).get("hd", {}).get("denomination")
        if hit_die:
            hit_die_text = str(hit_die)
            dice.append(hit_die_text if hit_die_text.startswith("d") else f"d{hit_die_text}")
    return ", ".join(dice)


def foundry_speed(system: dict) -> int:
    movement = system.get("attributes", {}).get("movement", {})
    if not isinstance(movement, dict):
        return 0
    for key in ["walk", "fly", "swim", "climb", "burrow"]:
        value = int_or_default(movement.get(key), 0)
        if value:
            return value
    return 30


def foundry_ac(system: dict, items: list[dict], stats: dict) -> int:
    attributes = system.get("attributes", {}) if isinstance(system.get("attributes"), dict) else {}
    ac = attributes.get("ac", {}) if isinstance(attributes.get("ac"), dict) else {}
    if ac.get("value"):
        return int_or_default(ac.get("value"), 10)
    dex = int_or_default(stats.get("dex", {}).get("modifier"), 0)
    best = 10 + dex
    shield = 0
    for item in items:
        item_system = item.get("system", {}) if isinstance(item.get("system"), dict) else {}
        if item.get("type") != "equipment" or not item_system.get("equipped"):
            continue
        armor = item_system.get("armor", {}) if isinstance(item_system.get("armor"), dict) else {}
        armor_value = int_or_default(armor.get("value"), 0)
        item_type = item_system.get("type", {}).get("value") if isinstance(item_system.get("type"), dict) else ""
        if item_type == "shield":
            shield += armor_value or 2
        elif armor_value:
            best = max(best, armor_value + dex)
    return best + shield


def foundry_weapon_ability(system: dict) -> str:
    for activity in (system.get("activities") or {}).values():
        if isinstance(activity, dict) and activity.get("type") == "attack":
            ability = activity.get("attack", {}).get("ability", "")
            if ability in ABILITY_LABELS:
                return ability
    weapon_type = system.get("type", {}).get("value", "") if isinstance(system.get("type"), dict) else ""
    return "dex" if weapon_type in {"simpleR", "martialR"} else "str"


def foundry_damage_formula(system: dict, ability_mod: int) -> str:
    damage = system.get("damage", {}) if isinstance(system.get("damage"), dict) else {}
    base = damage.get("base", {}) if isinstance(damage.get("base"), dict) else {}
    custom = base.get("custom", {}) if isinstance(base.get("custom"), dict) else {}
    if custom.get("enabled") and custom.get("formula"):
        formula = str(custom.get("formula")).replace("@mod", signed(ability_mod)).replace("++", "+").replace("+-", "-")
        if re.fullmatch(r"max\(0,\s*[-+ 0-9]+\)", formula):
            try:
                expression = formula[formula.index(",") + 1 : -1]
                return str(max(0, int(evaluate_arithmetic(expression))))
            except (ArithmeticError, UnsafeArithmeticExpression, ValueError):
                return formula
        return formula
    number = int_or_default(base.get("number"), 0)
    denomination = int_or_default(base.get("denomination"), 0)
    bonus = str(base.get("bonus") or "").strip()
    formula = f"{number}d{denomination}" if number and denomination else ""
    if ability_mod:
        formula = f"{formula}{signed(ability_mod)}" if formula else signed(ability_mod)
    if bonus:
        formula = f"{formula}+{bonus}" if formula else bonus
    return formula.replace("+-", "-") or "1"


def resolve_foundry_number(value, proficiency: int, stats: dict, default: int = 0) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return default
    replacements = {
        "@prof": proficiency,
        "@abilities.wis.mod": int_or_default(stats.get("wis", {}).get("modifier"), 0),
        "@abilities.str.mod": int_or_default(stats.get("str", {}).get("modifier"), 0),
        "@abilities.dex.mod": int_or_default(stats.get("dex", {}).get("modifier"), 0),
        "@abilities.con.mod": int_or_default(stats.get("con", {}).get("modifier"), 0),
        "@abilities.int.mod": int_or_default(stats.get("int", {}).get("modifier"), 0),
        "@abilities.cha.mod": int_or_default(stats.get("cha", {}).get("modifier"), 0),
    }
    for token, number in replacements.items():
        text = text.replace(token, str(number))
    if re.fullmatch(r"[\d+\-*/ ().]+", text):
        try:
            return max(0, int(evaluate_arithmetic(text)))
        except (ArithmeticError, UnsafeArithmeticExpression, ValueError):
            return default
    return int_or_default(text, default)


def text_section(body: str) -> dict:
    return {"value": {"data": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}}}


def html_to_text(value: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", str(value or ""))
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</h[1-6]\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"@UUID\[[^\]]+\]\{([^}]+)\}", r"\1", text)
    text = re.sub(r"&amp;Reference\[([^\] ]+).*?\]", r"\1", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def field_value(container: dict, key: str):
    value = container.get(key, "") if isinstance(container, dict) else ""
    if isinstance(value, dict):
        return value.get("value", "")
    return value


def value_at(container: dict, *path):
    current = container
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return current


def signed(value) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value or "+0")
    return f"+{number}" if number >= 0 else str(number)


def fix_text_tree(value):
    if isinstance(value, dict):
        return {key: fix_text_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [fix_text_tree(item) for item in value]
    if isinstance(value, str):
        return fix_mojibake(value)
    return value


def fix_mojibake(value: str) -> str:
    if not any(marker in value for marker in ("Р", "С", "В", "вЂ", "Г—")):
        return value
    try:
        candidate = value.encode("cp1251").decode("utf-8")
    except UnicodeError:
        return value
    if cyrillic_score(candidate) > cyrillic_score(value):
        return candidate
    return value


def cyrillic_score(value: str) -> int:
    return sum(1 for char in value if "А" <= char <= "я" or char == "ё" or char == "Ё") - value.count("Р") - value.count("С")


def tiptap_to_text(node) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return str(node.get("text", ""))
    if node_type == "hardBreak":
        return "\n"
    content = node.get("content", [])
    if not isinstance(content, list):
        content = []
    children = "".join(tiptap_to_text(child) for child in content)
    if node_type in {"paragraph", "heading"}:
        return f"{children}\n\n"
    if node_type == "listItem":
        return f"- {children.strip()}\n"
    if node_type in {"bulletList", "orderedList"}:
        return f"{children}\n"
    if node_type == "resource":
        attrs = node.get("attrs", {}) if isinstance(node.get("attrs"), dict) else {}
        return f"[ресурс: {attrs.get('textName', attrs.get('id', ''))}]"
    return children
