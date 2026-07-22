import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ogma.sqlite_store import SqliteStore


DEFAULT_DB = ROOT / "data" / "ogma.db"
DEFAULT_SOURCE = ROOT / "data" / "ogma.db.before-session-pdf-utf8-fix-20260601-222137.bak"
PDF_TEXT_DIR = ROOT / "data" / ".cache" / "pdf-text"
SESSION_TITLES = {
    4: "Культ на крови",
    5: "Интриги Совета",
    6: "Пещера дьяволов",
    7: "Сессия 7",
}


def load_notes(database_path: Path) -> list[tuple[str, dict]]:
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'notes'"
        ).fetchone()
        if table_exists is None:
            return []
        rows = connection.execute(
            "SELECT campaign_slug, json_payload FROM notes ORDER BY campaign_slug, position"
        ).fetchall()
    finally:
        connection.close()

    result = []
    for campaign_slug, payload in rows:
        try:
            item = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            result.append((str(campaign_slug), item))
    return result


def clean_extracted_text(lines: list[str]) -> str:
    paragraphs = []
    current = []
    for raw_line in lines:
        line = raw_line.strip()
        if re.fullmatch(r"--- PAGE \d+ ---", line):
            line = ""
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()


def numbered_section(path: Path, number: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(
        (index + 1 for index, line in enumerate(lines) if line.strip() == str(number)),
        None,
    )
    if start is None:
        return ""
    end = next(
        (
            index
            for index in range(start, len(lines))
            if re.fullmatch(r"\d+", lines[index].strip())
        ),
        len(lines),
    )
    return clean_extracted_text(lines[start:end])


def whole_document(path: Path, leading_lines: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return clean_extracted_text(lines[leading_lines:])


def repaired_session_bodies() -> dict[int, str]:
    return {
        4: numbered_section(PDF_TEXT_DIR / "События Ильмарен.txt", 4),
        5: whole_document(PDF_TEXT_DIR / "заметки 5 сессия - первые два часа.txt", 1),
        6: whole_document(PDF_TEXT_DIR / "События Ильмарен - 6.txt", 2),
    }


def repair_damaged_notes(notes: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    bodies = repaired_session_bodies()
    repaired = []
    for campaign_slug, original in notes:
        note = original.copy()
        session_number = int(note.get("session_number") or 0)
        if session_number in SESSION_TITLES:
            note["title"] = SESSION_TITLES[session_number]
        if session_number in bodies and bodies[session_number]:
            note["body"] = bodies[session_number]
            note["planned_body"] = ""
            note["happened_body"] = bodies[session_number]
            note["recovered_from_pdf_text"] = True
        note["recovered_from_backup"] = True
        repaired.append((campaign_slug, note))
    return repaired


def merge_notes(
    current: list[tuple[str, dict]],
    recovered: list[tuple[str, dict]],
) -> dict[str, list[dict]]:
    by_campaign = defaultdict(list)
    known_ids = defaultdict(set)
    for campaign_slug, item in current:
        by_campaign[campaign_slug].append(item)
        known_ids[campaign_slug].add(str(item.get("id") or ""))
    for campaign_slug, item in recovered:
        item_id = str(item.get("id") or "")
        if not item_id or item_id in known_ids[campaign_slug]:
            continue
        by_campaign[campaign_slug].append(item)
        known_ids[campaign_slug].add(item_id)
    for items in by_campaign.values():
        items.sort(
            key=lambda item: (
                int(item.get("session_number") or 0),
                str(item.get("created_at") or ""),
            )
        )
    return dict(by_campaign)


def backup_database(database_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.name}.before-session-note-recovery-{stamp}.bak"
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
        description="Recover session chronicles from the latest SQLite backup and cached PDF text."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    database_path = args.database.resolve()
    source_path = args.source.resolve()
    current = load_notes(database_path)
    recovered = repair_damaged_notes(load_notes(source_path))
    merged = merge_notes(current, recovered)
    report = {
        "database": str(database_path),
        "source": str(source_path),
        "apply": args.apply,
        "current_notes": len(current),
        "recovered_notes": len(recovered),
        "result_notes": sum(len(items) for items in merged.values()),
        "sessions": [
            {
                "campaign": campaign_slug,
                "number": item.get("session_number"),
                "title": item.get("title"),
                "body_length": len(item.get("happened_body") or item.get("body") or ""),
                "repaired_from_pdf_text": bool(item.get("recovered_from_pdf_text")),
            }
            for campaign_slug, items in merged.items()
            for item in items
        ],
    }

    if args.apply:
        backup_path = backup_database(database_path)
        store = SqliteStore(database_path)
        for campaign_slug, items in merged.items():
            store.save_metadata_list(
                "notes",
                items,
                scope="campaign",
                campaign_slug=campaign_slug,
            )
        report["backup"] = str(backup_path)

    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
