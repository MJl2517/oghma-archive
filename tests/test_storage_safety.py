import json
import tempfile
import unittest
from pathlib import Path

from ogma.storage import ArchiveStorage


class StorageSafetyTests(unittest.TestCase):
    def test_ensure_does_not_auto_import_legacy_json_into_populated_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            legacy_dir = data_dir / "campaigns" / "legacy-world"
            legacy_dir.mkdir(parents=True)
            legacy_path = legacy_dir / "campaign.json"
            legacy_path.write_text(
                json.dumps({"name": "Legacy World"}, ensure_ascii=False),
                encoding="utf-8",
            )
            storage = ArchiveStorage(
                data_dir=data_dir,
                shared_folders=["maps", "rules"],
                campaign_folders=["maps", "characters", "notes"],
                backend="sqlite",
            )
            storage.sqlite.save_entity_item(
                "campaigns",
                {
                    "slug": "database-world",
                    "name": "Database World",
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                },
            )

            storage.ensure()

            self.assertTrue(legacy_path.exists())
            self.assertEqual(
                ["database-world"],
                [
                    item["slug"]
                    for item in storage.sqlite.load_metadata_list("campaigns")
                ],
            )
            self.assertEqual("", storage.sqlite.get_meta("content_migrated"))


if __name__ == "__main__":
    unittest.main()
