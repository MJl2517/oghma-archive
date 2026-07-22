import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from ogma.errors import ExternalOperationError
from ogma.god_catalog import CATALOG_SCHEMA, PACK_SCHEMA, GodCatalogManager, parse_god_catalog
from ogma.services.gods import install_god_packs


def pack_payload(pack_id: str, pantheon: str) -> dict:
    return {
        "schema": PACK_SCHEMA,
        "labels": {
            "alignments": ["Нейтральный"],
            "domains": ["Знание"],
            "ranks": ["Высшее божество"],
            "pantheons": [pantheon],
        },
        "gods": [
            {
                "id": f"catalog-{pack_id}-aurora",
                "name": "Аврора",
                "english_name": "Aurora",
                "alignment": "Нейтральный",
                "domains": ["Знание"],
                "rank": "Высшее божество",
                "pantheon": pantheon,
                "pantheons": [pantheon],
            }
        ],
    }


def manifest_payload(pack_specs: list[tuple[str, str, bytes]]) -> dict:
    packs = []
    for pack_id, pantheon, raw in pack_specs:
        packs.append(
            {
                "id": pack_id,
                "title": pantheon,
                "description": f"Боги пантеона {pantheon}.",
                "version": "2026.07.22",
                "language": "ru",
                "gods_count": 1,
                "pantheons": [pantheon],
                "filename": f"{pack_id}.json",
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {"schema": CATALOG_SCHEMA, "packs": packs}


class GodCatalogTests(unittest.TestCase):
    def test_catalog_rejects_paths_and_duplicate_ids(self):
        raw = json.dumps(pack_payload("faerun", "Фаэрун"), ensure_ascii=False).encode()
        hostile = manifest_payload([("faerun", "Фаэрун", raw)])
        hostile["packs"][0]["filename"] = "../faerun.json"
        with self.assertRaises(ValueError):
            parse_god_catalog(hostile)

        duplicate = manifest_payload([("faerun", "Фаэрун", raw)])
        duplicate["packs"].append(dict(duplicate["packs"][0], filename="other.json"))
        with self.assertRaises(ValueError):
            parse_god_catalog(duplicate)

    def test_manager_downloads_several_packs_and_tracks_each_campaign(self):
        faerun = json.dumps(pack_payload("faerun", "Фаэрун"), ensure_ascii=False).encode()
        eberron = json.dumps(pack_payload("eberron", "Эберрон"), ensure_ascii=False).encode()
        manifest = json.dumps(
            manifest_payload(
                [("faerun", "Фаэрун", faerun), ("eberron", "Эберрон", eberron)]
            ),
            ensure_ascii=False,
        ).encode()

        def fake_fetch(request, **_kwargs):
            if request.full_url.endswith("manifest.json"):
                return manifest
            if request.full_url.endswith("faerun.json"):
                return faerun
            if request.full_url.endswith("eberron.json"):
                return eberron
            raise AssertionError(request.full_url)

        with tempfile.TemporaryDirectory() as directory:
            manager = GodCatalogManager(
                Path(directory) / "data",
                Path(directory) / "bundle",
                "1.0.0",
                fetch_bytes=fake_fetch,
                frozen=True,
            )
            downloads = manager.download_packs(["faerun", "eberron"])
            self.assertEqual([item["entry"]["id"] for item in downloads], ["faerun", "eberron"])

            manager.record_installed("campaign-a", [item["entry"] for item in downloads])
            installed_a = manager.catalog("campaign-a")
            installed_b = manager.catalog("campaign-b")
            self.assertTrue(all(pack["installed"] for pack in installed_a["packs"]))
            self.assertTrue(all(not pack["installed"] for pack in installed_b["packs"]))

    def test_manager_rejects_tampered_pack(self):
        expected = json.dumps(pack_payload("faerun", "Фаэрун"), ensure_ascii=False).encode()
        manifest = json.dumps(
            manifest_payload([("faerun", "Фаэрун", expected)]),
            ensure_ascii=False,
        ).encode()

        def fake_fetch(request, **_kwargs):
            return manifest if request.full_url.endswith("manifest.json") else expected + b" "

        with tempfile.TemporaryDirectory() as directory:
            manager = GodCatalogManager(
                Path(directory) / "data",
                Path(directory) / "bundle",
                "1.0.0",
                fetch_bytes=fake_fetch,
                frozen=True,
            )
            with self.assertRaises(ExternalOperationError):
                manager.download_packs(["faerun"])

    def test_install_can_merge_or_replace_multiple_packs_in_one_save(self):
        local_gods = [
            {
                "id": "local-god",
                "name": "Домашнее божество",
                "english_name": "",
                "alignment": "Нейтральный",
                "domains": ["Дом"],
                "rank": "",
                "pantheon": "Авторский",
                "pantheons": ["Авторский"],
            }
        ]
        labels = {
            "alignments": ["Нейтральный"],
            "domains": ["Дом"],
            "ranks": [],
            "pantheons": ["Авторский"],
        }
        save_calls = []
        recorded = []
        downloads = []
        for pack_id, pantheon in (("faerun", "Фаэрун"), ("eberron", "Эберрон")):
            downloads.append(
                {
                    "entry": {
                        "id": pack_id,
                        "title": pantheon,
                        "version": "2026.07.22",
                        "gods_count": 1,
                    },
                    "payload": pack_payload(pack_id, pantheon),
                }
            )

        def normalize_tags(values):
            if isinstance(values, str):
                values = [part.strip() for part in values.split(",")]
            result = []
            known = set()
            for value in values or []:
                clean = str(value or "").strip()
                if clean and clean.casefold() not in known:
                    result.append(clean)
                    known.add(clean.casefold())
            return result

        def normalize_god(god, _campaign_slug):
            pantheons = normalize_tags(god.get("pantheons") or [god.get("pantheon", "")])
            return {
                **god,
                "id": str(god.get("id", "")),
                "name": str(god.get("name", "")),
                "english_name": str(god.get("english_name", "")),
                "alignment": str(god.get("alignment", "")),
                "domains": normalize_tags(god.get("domains", [])),
                "rank": str(god.get("rank", "")),
                "pantheon": pantheons[0] if pantheons else "",
                "pantheons": pantheons,
            }

        def save_gods(_campaign_slug, gods):
            save_calls.append([dict(god) for god in gods])
            local_gods[:] = gods

        manager = SimpleNamespace(
            download_packs=lambda _ids: downloads,
            record_installed=lambda slug, entries: recorded.append((slug, entries)),
        )
        deps = {
            "god_catalog_manager": manager,
            "get_campaign": lambda slug: {"slug": slug} if slug == "campaign-a" else None,
            "normalize_god": normalize_god,
            "normalize_tags": normalize_tags,
            "load_gods": lambda _slug: [dict(god) for god in local_gods],
            "save_gods": save_gods,
            "datetime": datetime,
            "FALLBACK_GOD_ALIGNMENT": "Не указано",
        }
        for key in ("alignments", "domains", "ranks", "pantheons"):
            deps[f"load_god_{key}"] = lambda _slug, key=key: list(labels[key])
            deps[f"save_god_{key}"] = lambda _slug, values, key=key: labels[key].__setitem__(slice(None), values)

        action, slug, result, status = install_god_packs(
            deps,
            {"campaign_slug": "campaign-a", "packs": ["faerun", "eberron"]},
        )

        self.assertEqual((action, slug, status), ("ok", "campaign-a", 200))
        self.assertEqual(result["created"], 2)
        self.assertEqual(len(save_calls), 1)
        self.assertEqual({god["id"] for god in local_gods}, {"local-god", "catalog-faerun-aurora", "catalog-eberron-aurora"})
        self.assertEqual({god["pantheon"] for god in local_gods if god["name"] == "Аврора"}, {"Фаэрун", "Эберрон"})
        self.assertEqual(set(labels["pantheons"]), {"Авторский", "Фаэрун", "Эберрон"})
        self.assertEqual(recorded[0][0], "campaign-a")
        self.assertEqual([entry["id"] for entry in recorded[0][1]], ["faerun", "eberron"])

        replace_action, replace_slug, replaced, replace_status = install_god_packs(
            deps,
            {
                "campaign_slug": "campaign-a",
                "packs": ["faerun", "eberron"],
                "replace": True,
            },
        )

        self.assertEqual((replace_action, replace_slug, replace_status), ("ok", "campaign-a", 200))
        self.assertTrue(replaced["replaced"])
        self.assertEqual(replaced["removed"], 3)
        self.assertEqual(len(save_calls), 2)
        self.assertEqual({god["id"] for god in local_gods}, {"catalog-faerun-aurora", "catalog-eberron-aurora"})
        self.assertNotIn("Дом", labels["domains"])
        self.assertNotIn("Авторский", labels["pantheons"])
        self.assertEqual(set(labels["pantheons"]), {"Фаэрун", "Эберрон"})
        self.assertIn("Не указано", labels["alignments"])


if __name__ == "__main__":
    unittest.main()
