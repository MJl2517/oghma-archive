from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import load_rule_sources, load_rule_tags, load_rules
from ogma.glossary_catalog import CATALOG_SCHEMA, PACK_SCHEMA
from ogma.json_store import read_json, write_json
from ogma.services.rules import _clean_rule_for_export


def write_generated_json(path: Path, payload: dict) -> None:
    write_json(path, payload)
    path.with_name(f".{path.name}.lock").unlink(missing_ok=True)
    path.with_name(f"{path.name}.bak").unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a glossary pack and refresh its catalog entry.")
    parser.add_argument("--id", default="dnd5e-ru")
    parser.add_argument("--filename", default="dnd5e-ru.json")
    parser.add_argument("--title", default="D&D 5e — глоссарий правил")
    parser.add_argument(
        "--description",
        default="Русскоязычный справочник правил D&D 5e для быстрого поиска во время игры.",
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--language", default="ru")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "materials" / "glossaries",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rules = []
    known_rules = set()
    duplicate_count = 0
    for raw_rule in load_rules():
        rule = _clean_rule_for_export(raw_rule)
        identity = (
            rule["title"].casefold(),
            rule["tag"].casefold(),
            rule["source"].casefold(),
            rule["page"],
            rule["book_url"],
            rule["content"],
        )
        if identity in known_rules:
            duplicate_count += 1
            continue
        known_rules.add(identity)
        rules.append(rule)
    sources = load_rule_sources()
    payload = {
        "schema": PACK_SCHEMA,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "labels": {
            "tags": load_rule_tags(),
            "sources": sources,
        },
        "rules": rules,
    }
    pack_path = output_root / args.filename
    write_generated_json(pack_path, payload)
    raw = pack_path.read_bytes()

    manifest_path = output_root / "manifest.json"
    manifest = read_json(manifest_path, fallback={})
    if not isinstance(manifest, dict) or manifest.get("schema") != CATALOG_SCHEMA:
        manifest = {"schema": CATALOG_SCHEMA, "packs": []}
    packs = manifest.get("packs", [])
    if not isinstance(packs, list):
        packs = []
    entry = {
        "id": args.id,
        "title": args.title,
        "description": args.description,
        "version": args.version,
        "language": args.language,
        "rules_count": len(rules),
        "sources": sources,
        "filename": args.filename,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    packs = [pack for pack in packs if isinstance(pack, dict) and pack.get("id") != args.id]
    packs.append(entry)
    packs.sort(key=lambda pack: str(pack.get("title", "")).casefold())
    manifest["packs"] = packs
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_generated_json(manifest_path, manifest)

    print(f"Pack: {pack_path}")
    print(f"Rules: {len(rules)}")
    print(f"Exact duplicates skipped: {duplicate_count}")
    print(f"SHA-256: {entry['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
