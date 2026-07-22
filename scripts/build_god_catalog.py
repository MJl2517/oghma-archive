from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ogma.god_catalog import CATALOG_SCHEMA, PACK_SCHEMA
from ogma.json_store import write_json


PACKS = [
    {
        "id": "forgotten-realms",
        "title": "Фаэрун",
        "description": "Боги Фаэруна и связанные расовые пантеоны Забытых Королевств.",
        "pantheons": [
            "Фаэрунский пантеон",
            "Эльфийский пантеон (Селдарин)",
            "Дварфийский пантеон (Морндинсамман)",
            "Пантеон гномов",
            "Пантеон Дроу (Тёмные Селдарин)",
            "Пантеон полуросликов",
            "Пантеон орков",
            "Пантеон гоблиноидов",
            "Боги великанов",
            "Пантеон драконов",
        ],
    },
    {
        "id": "eberron",
        "title": "Эберрон",
        "description": "Владычествующий Сонм, Тёмная Шестёрка и другие силы Эберрона.",
        "pantheons": [
            "Верховные Владыки Эбеорна (Владычествующий Сонм)",
            "Тёмная Шестёрка Эбеорна",
            "Другие боги Эберона",
            "Божества предвечных войн",
        ],
    },
    {
        "id": "greyhawk",
        "title": "Серый Ястреб",
        "description": "Пантеон сеттинга Greyhawk для кампаний в мире Оэрт.",
        "pantheons": ["Пантеон Грейхока (Серый ястреб)"],
    },
    {
        "id": "dragonlance",
        "title": "Кринн",
        "description": "Боги Кринна из сеттинга Dragonlance.",
        "pantheons": ["Пантеон Кринна (Сага о копье)"],
    },
    {
        "id": "theros",
        "title": "Терос",
        "description": "Божества мира Терос.",
        "pantheons": ["Терос"],
    },
    {
        "id": "thylea",
        "title": "Тилея",
        "description": "Древние титаны Тилеи из сеттинга Odyssey of the Dragonlords.",
        "pantheons": ["Боги Тилеи (Древние титаны)"],
    },
    {
        "id": "egyptian",
        "title": "Египетские боги",
        "description": "Пантеон фараонов и божества древнеегипетской мифологии.",
        "pantheons": ["Пантеон фараонов (eгипетские боги)"],
    },
    {
        "id": "greek",
        "title": "Греческие боги",
        "description": "Олимпийцы, титаны и другие божества греческой мифологии.",
        "pantheons": ["Греческие боги"],
    },
    {
        "id": "norse",
        "title": "Скандинавские боги",
        "description": "Асы, ваны и другие боги северной мифологии.",
        "pantheons": ["Асгардский пантеон (скандинавские боги)"],
    },
    {
        "id": "celtic",
        "title": "Кельтские боги",
        "description": "Божества и героические силы кельтской мифологии.",
        "pantheons": ["Кельтские боги"],
    },
    {
        "id": "other-deities",
        "title": "Прочие божества",
        "description": "Божества, для которых в исходном справочнике не указан отдельный пантеон.",
        "pantheons": ["Неизвестный"],
    },
]

PANTHEON_DISPLAY_NAMES = {
    "Верховные Владыки Эбеорна (Владычествующий Сонм)": "Верховные Владыки Эберрона (Владычествующий Сонм)",
    "Тёмная Шестёрка Эбеорна": "Тёмная Шестёрка Эберрона",
    "Пантеон фараонов (eгипетские боги)": "Пантеон фараонов (египетские боги)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split an Oghma gods export into installable setting packs.")
    parser.add_argument("source", type=Path, help="Path to an ogma.gods.export.v1 JSON file.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "materials" / "gods")
    return parser.parse_args()


def unique(values) -> list[str]:
    result = []
    known = set()
    for value in values:
        clean = str(value or "").strip()
        key = clean.casefold()
        if clean and key not in known:
            result.append(clean)
            known.add(key)
    return result


def write_generated_json(path: Path, payload: dict) -> None:
    write_json(path, payload)
    path.with_name(f".{path.name}.lock").unlink(missing_ok=True)
    path.with_name(f"{path.name}.bak").unlink(missing_ok=True)


def god_pantheons(god: dict) -> list[str]:
    return unique(god.get("pantheons", []) or [god.get("pantheon", "")])


def display_pantheons(values) -> list[str]:
    return unique(PANTHEON_DISPLAY_NAMES.get(value, value) for value in values)


def stable_god(god: dict, pack_id: str) -> dict:
    clean = dict(god)
    pantheons = display_pantheons(god_pantheons(god))
    identity = "||".join(
        [
            pack_id,
            str(god.get("id", "")),
            str(god.get("name", "")),
            str(god.get("english_name", "")),
            *pantheons,
        ]
    )
    clean["id"] = f"catalog-{pack_id}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
    clean["pantheons"] = pantheons
    clean["pantheon"] = clean["pantheons"][0] if clean["pantheons"] else ""
    return clean


def labels_for(gods: list[dict]) -> dict:
    return {
        "alignments": unique(god.get("alignment", "") for god in gods),
        "domains": unique(domain for god in gods for domain in god.get("domains", [])),
        "ranks": unique(god.get("rank", "") for god in gods),
        "pantheons": unique(pantheon for god in gods for pantheon in god_pantheons(god)),
    }


def main() -> int:
    args = parse_args()
    source = json.loads(args.source.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(source, dict) or source.get("schema") != PACK_SCHEMA or not isinstance(source.get("gods"), list):
        raise SystemExit("Source file is not an ogma.gods.export.v1 document.")

    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    pantheon_to_pack = {
        pantheon.casefold(): pack["id"]
        for pack in PACKS
        for pantheon in pack["pantheons"]
    }
    grouped = {pack["id"]: [] for pack in PACKS}
    unknown_pantheons = set()
    for god in source["gods"]:
        if not isinstance(god, dict):
            continue
        pantheons = god_pantheons(god)
        pack_id = next((pantheon_to_pack.get(value.casefold()) for value in pantheons if pantheon_to_pack.get(value.casefold())), None)
        if pack_id is None:
            unknown_pantheons.update(pantheons or {"<empty>"})
            continue
        grouped[pack_id].append(stable_god(god, pack_id))
    if unknown_pantheons:
        raise SystemExit(f"Unmapped pantheons: {sorted(unknown_pantheons)}")

    manifest_packs = []
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for pack in PACKS:
        gods = grouped[pack["id"]]
        if not gods:
            raise SystemExit(f"Pack {pack['id']} is empty.")
        filename = f"{pack['id']}.json"
        payload = {
            "schema": PACK_SCHEMA,
            "exported_at": exported_at,
            "source_campaign": source.get("source_campaign", {}),
            "labels": labels_for(gods),
            "gods": gods,
        }
        path = output_root / filename
        write_generated_json(path, payload)
        raw = path.read_bytes()
        manifest_packs.append(
            {
                "id": pack["id"],
                "title": pack["title"],
                "description": pack["description"],
                "version": args.version,
                "language": "ru",
                "gods_count": len(gods),
                "pantheons": display_pantheons(pack["pantheons"]),
                "filename": filename,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        print(f"{pack['title']}: {len(gods)}")

    write_generated_json(
        output_root / "manifest.json",
        {"schema": CATALOG_SCHEMA, "packs": manifest_packs, "updated_at": exported_at},
    )
    print(f"Total: {sum(pack['gods_count'] for pack in manifest_packs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
