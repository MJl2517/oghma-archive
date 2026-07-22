import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError
from uuid import uuid4

from ogma.errors import ExternalOperationError
from ogma.glossary_catalog import (
    CATALOG_SCHEMA,
    GlossaryCatalogManager,
    PACK_SCHEMA,
    parse_glossary_catalog,
)
from ogma.services.rules import install_glossary_packs


def pack_payload(*, rule_id: str = "pack-rule", title: str = "Pack rule") -> dict:
    return {
        "schema": PACK_SCHEMA,
        "labels": {"tags": ["Combat"], "sources": ["PHB"]},
        "rules": [
            {
                "id": rule_id,
                "title": title,
                "tag": "Combat",
                "source": "PHB",
                "page": "10",
                "book_url": "",
                "content": "Pack content",
            }
        ],
    }


def catalog_payload(pack_bytes: bytes, **overrides) -> dict:
    entry = {
        "id": "dnd5e-ru",
        "title": "D&D 5e glossary",
        "description": "Ready-to-use rules glossary.",
        "version": "2026.07.22",
        "language": "ru",
        "rules_count": 1,
        "sources": ["PHB"],
        "filename": "dnd5e-ru.json",
        "size": len(pack_bytes),
        "sha256": hashlib.sha256(pack_bytes).hexdigest(),
    }
    entry.update(overrides)
    return {"schema": CATALOG_SCHEMA, "packs": [entry]}


class GlossaryCatalogTests(unittest.TestCase):
    def test_catalog_rejects_paths_and_duplicate_ids(self):
        pack_bytes = json.dumps(pack_payload()).encode()
        hostile = catalog_payload(pack_bytes, filename="../rules.json")
        with self.assertRaises(ValueError):
            parse_glossary_catalog(hostile)

        duplicate = catalog_payload(pack_bytes)
        duplicate["packs"].append(dict(duplicate["packs"][0], filename="other.json"))
        with self.assertRaises(ValueError):
            parse_glossary_catalog(duplicate)

    def test_manager_verifies_pack_and_tracks_installed_version(self):
        pack_bytes = json.dumps(pack_payload(), ensure_ascii=False).encode()
        manifest_bytes = json.dumps(catalog_payload(pack_bytes), ensure_ascii=False).encode()

        def fake_fetch(request, **_kwargs):
            if request.full_url.endswith("manifest.json"):
                return manifest_bytes
            if request.full_url.endswith("dnd5e-ru.json"):
                return pack_bytes
            raise AssertionError(request.full_url)

        with tempfile.TemporaryDirectory() as directory:
            manager = GlossaryCatalogManager(
                Path(directory) / "data",
                Path(directory) / "bundle",
                "1.0.0",
                fetch_bytes=fake_fetch,
                frozen=True,
            )
            catalog = manager.catalog()
            self.assertEqual(catalog["source"], "github")
            self.assertFalse(catalog["packs"][0]["installed"])

            downloads = manager.download_packs(["dnd5e-ru"])
            self.assertEqual(downloads[0]["payload"]["rules"][0]["id"], "pack-rule")
            manager.record_installed([downloads[0]["entry"]])
            refreshed = manager.catalog()
            self.assertTrue(refreshed["packs"][0]["installed"])

    def test_manager_rejects_changed_pack_bytes(self):
        expected = json.dumps(pack_payload()).encode()
        manifest_bytes = json.dumps(catalog_payload(expected)).encode()

        def fake_fetch(request, **_kwargs):
            if request.full_url.endswith("manifest.json"):
                return manifest_bytes
            return expected + b" "

        with tempfile.TemporaryDirectory() as directory:
            manager = GlossaryCatalogManager(
                Path(directory) / "data",
                Path(directory) / "bundle",
                "1.0.0",
                fetch_bytes=fake_fetch,
                frozen=True,
            )
            with self.assertRaises(ExternalOperationError):
                manager.download_packs(["dnd5e-ru"])

    def test_packaged_app_falls_back_to_bundled_catalog_when_github_is_offline(self):
        pack_bytes = json.dumps(pack_payload()).encode()
        manifest_bytes = json.dumps(catalog_payload(pack_bytes)).encode()

        def offline_fetch(_request, **_kwargs):
            raise URLError("offline")

        with tempfile.TemporaryDirectory() as directory:
            bundle_root = Path(directory) / "bundle"
            glossary_root = bundle_root / "materials" / "glossaries"
            glossary_root.mkdir(parents=True)
            (glossary_root / "manifest.json").write_bytes(manifest_bytes)
            (glossary_root / "dnd5e-ru.json").write_bytes(pack_bytes)
            manager = GlossaryCatalogManager(
                Path(directory) / "data",
                bundle_root,
                "1.0.0",
                fetch_bytes=offline_fetch,
                frozen=True,
            )

            catalog = manager.catalog()
            downloads = manager.download_packs(["dnd5e-ru"])

            self.assertEqual(catalog["source"], "bundled")
            self.assertEqual(downloads[0]["payload"]["rules"][0]["id"], "pack-rule")

    def test_install_can_merge_or_replace_existing_rules(self):
        local_rules = [
            {
                "id": "local-rule",
                "title": "My local rule",
                "tag": "Notes",
                "source": "Homebrew",
                "content": "Keep me",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            }
        ]
        tags = ["Notes"]
        sources = ["Homebrew"]
        recorded = []
        payload = pack_payload()
        entry = {
            "id": "dnd5e-ru",
            "title": "D&D 5e glossary",
            "version": "2026.07.22",
            "rules_count": 1,
        }
        manager = SimpleNamespace(
            download_packs=lambda _ids: [{"entry": entry, "payload": payload}],
            record_installed=lambda entries: recorded.extend(entries),
        )
        deps = {
            "glossary_catalog_manager": manager,
            "load_rules": lambda: [dict(rule) for rule in local_rules],
            "save_rules": lambda rules: local_rules.__setitem__(slice(None), rules),
            "load_rule_tags": lambda: list(tags),
            "save_rule_tags": lambda values: tags.__setitem__(slice(None), values),
            "load_rule_sources": lambda: list(sources),
            "save_rule_sources": lambda values: sources.__setitem__(slice(None), values),
            "SERVICE_RULE_TAG": "Unsorted",
            "datetime": datetime,
            "uuid4": uuid4,
        }

        result, status = install_glossary_packs(deps, {"packs": ["dnd5e-ru"]})

        self.assertEqual(status, 200)
        self.assertEqual(result["created"], 1)
        self.assertEqual({rule["id"] for rule in local_rules}, {"local-rule", "pack-rule"})
        self.assertIn("Combat", tags)
        self.assertIn("PHB", sources)
        self.assertEqual(recorded[0]["id"], "dnd5e-ru")

        replaced, replace_status = install_glossary_packs(
            deps,
            {"packs": ["dnd5e-ru"], "replace": True},
        )

        self.assertEqual(replace_status, 200)
        self.assertTrue(replaced["replaced"])
        self.assertEqual(replaced["removed"], 2)
        self.assertEqual([rule["id"] for rule in local_rules], ["pack-rule"])
        self.assertEqual(set(tags), {"Unsorted", "Combat"})
        self.assertEqual(sources, ["PHB"])


if __name__ == "__main__":
    unittest.main()
