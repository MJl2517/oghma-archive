import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ogma.sqlite_store import SqliteStore


DEFAULT_DB = ROOT / "data" / "ogma.db"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def load_character_rows(database_path: Path) -> list[tuple[str, dict]]:
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'characters'"
        ).fetchone()
        if table_exists is None:
            return []
        rows = connection.execute(
            "SELECT campaign_slug, json_payload FROM characters"
        ).fetchall()
    finally:
        connection.close()

    characters = []
    for campaign_slug, payload in rows:
        try:
            item = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            characters.append((str(campaign_slug), item))
    return characters


def scan_embedded_character_json(database_path: Path) -> list[dict]:
    text = database_path.read_bytes().decode("utf-8", errors="ignore")
    decoder = json.JSONDecoder()
    characters = []
    seen_payloads = set()
    for match in re.finditer(r'\{\s*\n\s*"id"\s*:', text):
        try:
            item, end = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if not all(str(item.get(key) or "").strip() for key in ("id", "filename", "name")):
            continue
        if not any(key in item for key in ("age", "gender", "race", "notes", "tags", "groups")):
            continue
        signature = text[match.start():end]
        if signature in seen_payloads:
            continue
        seen_payloads.add(signature)
        characters.append(item)
    return characters


def item_score(item: dict) -> tuple[str, int, int]:
    timestamp = str(
        item.get("updated_at")
        or item.get("uploaded_at")
        or item.get("created_at")
        or ""
    )
    populated_fields = sum(value not in ("", None, [], {}) for value in item.values())
    return timestamp, populated_fields, len(json.dumps(item, ensure_ascii=False))


def prefer_newer(candidates: dict[tuple[str, str], dict], slug: str, item: dict) -> None:
    item_id = str(item.get("id") or "").strip()
    if not item_id:
        return
    key = (slug, item_id)
    existing = candidates.get(key)
    if existing is None or item_score(item) > item_score(existing):
        candidates[key] = item


def character_files_by_campaign(database_path: Path) -> dict[str, set[str]]:
    result = {}
    campaigns_dir = database_path.parent / "campaigns"
    if not campaigns_dir.exists():
        return result
    for campaign_dir in campaigns_dir.iterdir():
        characters_dir = campaign_dir / "characters"
        if not characters_dir.is_dir():
            continue
        result[campaign_dir.name] = {
            path.name
            for path in characters_dir.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_EXTENSIONS
        }
    return result


def collect_candidates(database_path: Path) -> tuple[
    dict[str, list[dict]],
    dict[str, set[str]],
    dict[str, list[dict]],
]:
    files_by_campaign = character_files_by_campaign(database_path)
    current_by_campaign = defaultdict(list)
    candidates = {}

    for slug, item in load_character_rows(database_path):
        current_by_campaign[slug].append(item)
        prefer_newer(candidates, slug, item)

    backup_paths = sorted(
        database_path.parent.glob(f"{database_path.name}*.bak"),
        key=lambda path: path.stat().st_mtime,
    )
    for backup_path in backup_paths:
        for slug, item in load_character_rows(backup_path):
            filename = str(item.get("filename") or item.get("image") or "").strip()
            if filename in files_by_campaign.get(slug, set()):
                prefer_newer(candidates, slug, item)

    filename_campaigns = defaultdict(list)
    for slug, filenames in files_by_campaign.items():
        for filename in filenames:
            filename_campaigns[filename].append(slug)
    for item in scan_embedded_character_json(database_path):
        filename = str(item.get("filename") or "").strip()
        for slug in filename_campaigns.get(filename, []):
            prefer_newer(candidates, slug, item)

    candidates_by_campaign = defaultdict(list)
    for (slug, _item_id), item in candidates.items():
        candidates_by_campaign[slug].append(item)
    for items in candidates_by_campaign.values():
        items.sort(
            key=lambda item: (
                str(item.get("uploaded_at") or item.get("created_at") or ""),
                str(item.get("name") or "").casefold(),
            )
        )
    return dict(candidates_by_campaign), files_by_campaign, dict(current_by_campaign)


def placeholder_character(campaign_slug: str, filename: str, file_path: Path) -> dict:
    timestamp = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(timespec="seconds")
    return {
        "id": uuid5(NAMESPACE_URL, f"ogma:{campaign_slug}:character:{filename}").hex,
        "filename": filename,
        "original_filename": filename,
        "name": file_path.stem,
        "age": "",
        "gender": "Иное",
        "race": "",
        "notes": "",
        "tags": ["Неотсортированные"],
        "uploaded_at": timestamp,
        "recovered_from_art": True,
    }


def recovery_plan(database_path: Path, include_placeholders: bool) -> tuple[dict[str, list[dict]], list[dict]]:
    candidates_by_campaign, files_by_campaign, current_by_campaign = collect_candidates(database_path)
    plan = {}
    report = []
    for slug, filenames in sorted(files_by_campaign.items()):
        current = current_by_campaign.get(slug, [])
        candidate_by_filename = {
            str(item.get("filename") or item.get("image") or ""): item
            for item in candidates_by_campaign.get(slug, [])
        }
        merged = []
        duplicate_art_filenames = set()
        for item in current:
            filename = str(item.get("filename") or item.get("image") or "")
            original_filename = str(item.get("original_filename") or "")
            source_candidate = candidate_by_filename.get(original_filename)
            if (
                original_filename
                and original_filename != filename
                and original_filename in filenames
            ):
                if (
                    source_candidate is not None
                    and str(source_candidate.get("id") or "") != str(item.get("id") or "")
                ):
                    duplicate_art_filenames.add(filename)
                    continue
                duplicate_art_filenames.add(original_filename)
            merged.append(item)
        known_ids = {str(item.get("id") or "") for item in merged}
        covered_filenames = {
            str(item.get("filename") or item.get("image") or "")
            for item in merged
        }
        covered_filenames.update(duplicate_art_filenames)
        exact_recovered = 0
        for item in candidates_by_campaign.get(slug, []):
            item_id = str(item.get("id") or "")
            filename = str(item.get("filename") or item.get("image") or "")
            original_filename = str(item.get("original_filename") or "")
            source_candidate = candidate_by_filename.get(original_filename)
            if (
                original_filename
                and original_filename != filename
                and original_filename in filenames
                and source_candidate is not None
                and str(source_candidate.get("id") or "") != item_id
            ):
                duplicate_art_filenames.add(filename)
                covered_filenames.add(filename)
                continue
            if item_id in known_ids or filename in covered_filenames or filename not in filenames:
                continue
            merged.append(item)
            known_ids.add(item_id)
            covered_filenames.add(filename)
            exact_recovered += 1

        missing_filenames = sorted(filenames - covered_filenames)
        placeholders = []
        if include_placeholders:
            characters_dir = database_path.parent / "campaigns" / slug / "characters"
            placeholders = [
                placeholder_character(slug, filename, characters_dir / filename)
                for filename in missing_filenames
            ]
            merged.extend(placeholders)

        plan[slug] = merged
        report.append(
            {
                "campaign": slug,
                "art_files": len(filenames),
                "current_records": len(current),
                "current_records_kept": len(
                    [
                        item
                        for item in merged
                        if str(item.get("id") or "")
                        in {str(current_item.get("id") or "") for current_item in current}
                    ]
                ),
                "exact_records_recovered": exact_recovered,
                "placeholder_records": len(placeholders),
                "duplicate_art_files_ignored": len(duplicate_art_filenames),
                "still_missing": 0 if include_placeholders else len(missing_filenames),
                "missing_filenames": missing_filenames,
            }
        )
    return plan, report


def backup_database(database_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.name}.before-npc-record-recovery-{stamp}.bak"
    )
    source = sqlite3.connect(database_path)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover NPC metadata from SQLite free pages, database backups, and surviving art files."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--include-placeholders",
        action="store_true",
        help="Create minimal cards for art files whose exact metadata cannot be recovered.",
    )
    args = parser.parse_args()
    database_path = args.database.resolve()
    plan, report = recovery_plan(database_path, args.include_placeholders)
    result = {"database": str(database_path), "apply": args.apply, "campaigns": report}

    if args.apply:
        backup_path = backup_database(database_path)
        store = SqliteStore(database_path)
        for slug, characters in plan.items():
            store.save_metadata_list(
                "characters",
                characters,
                scope="campaign",
                campaign_slug=slug,
            )
        result["backup"] = str(backup_path)

    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
