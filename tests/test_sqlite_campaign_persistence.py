import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import sqlite3

from ogma.sqlite_store import DataIntegrityError, SqliteStore


class CampaignPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteStore(Path(self.temp_dir.name) / "ogma.db")
        self.first_campaign = {
            "slug": "first-world",
            "name": "First World",
            "description": "",
            "system": "",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        self.store.save_metadata_list("campaigns", [self.first_campaign])
        self.store.save_metadata_list(
            "characters",
            [{"id": "npc-1", "name": "Keeper", "filename": "keeper.webp"}],
            scope="campaign",
            campaign_slug="first-world",
        )
        self.store.save_metadata_list(
            "notes",
            [{"id": "note-1", "title": "Session"}],
            scope="campaign",
            campaign_slug="first-world",
        )
        self.store.save_metadata_list(
            "gods",
            [{"id": "god-1", "name": "Watcher"}],
            scope="campaign",
            campaign_slug="first-world",
        )
        self.store.save_metadata_list(
            "world_maps",
            [{"id": "world-map-1", "title": "Atlas"}],
            scope="campaign",
            campaign_slug="first-world",
        )
        self.store.save_metadata_list(
            "maps",
            [{"id": "map-1", "title": "Local Map", "filename": "map.webp"}],
            scope="campaign",
            campaign_slug="first-world",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def assert_first_campaign_content_exists(self) -> None:
        for entity in ("characters", "notes", "gods", "world_maps", "maps"):
            items = self.store.load_metadata_list(
                entity,
                scope="campaign",
                campaign_slug="first-world",
            )
            self.assertEqual(1, len(items), entity)

    def test_adding_campaign_does_not_delete_existing_campaign_content(self) -> None:
        second_campaign = {
            "slug": "second-world",
            "name": "Second World",
            "description": "",
            "system": "",
            "created_at": "2026-01-02T00:00:00",
            "updated_at": "2026-01-02T00:00:00",
        }

        self.store.save_metadata_list(
            "campaigns",
            [second_campaign, self.first_campaign],
        )

        self.assert_first_campaign_content_exists()

    def test_updating_campaign_does_not_delete_its_content(self) -> None:
        updated_campaign = {
            **self.first_campaign,
            "name": "First World Renamed",
            "updated_at": "2026-01-03T00:00:00",
        }

        self.store.save_metadata_list("campaigns", [updated_campaign])

        self.assert_first_campaign_content_exists()
        self.assertEqual(
            "First World Renamed",
            self.store.load_metadata_list("campaigns")[0]["name"],
        )

    def test_single_campaign_upsert_does_not_delete_its_content(self) -> None:
        updated_campaign = {
            **self.first_campaign,
            "name": "First World Updated",
        }

        self.store.save_entity_item("campaigns", updated_campaign)

        self.assert_first_campaign_content_exists()

    def test_stale_campaign_list_does_not_remove_new_campaign(self) -> None:
        second_campaign = {
            **self.first_campaign,
            "slug": "second-world",
            "name": "Second World",
        }
        self.store.save_metadata_list(
            "campaigns",
            [self.first_campaign, second_campaign],
        )
        self.store.save_metadata_list(
            "characters",
            [{"id": "npc-2", "name": "Survivor", "filename": "survivor.webp"}],
            scope="campaign",
            campaign_slug="second-world",
        )

        self.store.save_metadata_list("campaigns", [second_campaign])

        preserved_items = self.store.load_metadata_list(
            "characters",
            scope="campaign",
            campaign_slug="first-world",
        )
        kept_items = self.store.load_metadata_list(
            "characters",
            scope="campaign",
            campaign_slug="second-world",
        )
        self.assertEqual(["npc-1"], [item["id"] for item in preserved_items])
        self.assertEqual(["npc-2"], [item["id"] for item in kept_items])
        self.assertEqual(
            {"first-world", "second-world"},
            {item["slug"] for item in self.store.load_metadata_list("campaigns")},
        )

    def test_empty_campaign_bulk_save_does_not_delete_anything(self) -> None:
        self.store.save_metadata_list("campaigns", [])

        self.assertEqual(
            ["first-world"],
            [item["slug"] for item in self.store.load_metadata_list("campaigns")],
        )
        self.assert_first_campaign_content_exists()

    def test_campaign_bulk_upsert_rejects_missing_slug_before_writing(self) -> None:
        with self.assertRaises(ValueError):
            self.store.save_metadata_list(
                "campaigns",
                [{"name": "Unsafe payload"}],
            )

        self.assertEqual(
            ["first-world"],
            [item["slug"] for item in self.store.load_metadata_list("campaigns")],
        )

    def test_corrupt_json_payload_is_reported_and_preserved(self) -> None:
        with closing(sqlite3.connect(self.store.db_path)) as connection:
            connection.execute(
                "UPDATE characters SET json_payload = ? WHERE id = ?",
                ("{broken-json", "npc-1"),
            )
            connection.commit()

        with self.assertRaises(DataIntegrityError):
            self.store.load_metadata_list(
                "characters",
                scope="campaign",
                campaign_slug="first-world",
            )

        with closing(sqlite3.connect(self.store.db_path)) as connection:
            row = connection.execute(
                "SELECT json_payload FROM characters WHERE id = ?",
                ("npc-1",),
            ).fetchone()
        self.assertEqual("{broken-json", row[0])

    def test_reads_are_fresh_across_store_instances(self) -> None:
        self.assertEqual(
            "First World",
            self.store.load_metadata_list("campaigns")[0]["name"],
        )
        second_store = SqliteStore(self.store.db_path)
        second_store.save_entity_item(
            "campaigns",
            {**self.first_campaign, "name": "Fresh Name"},
        )

        self.assertEqual(
            "Fresh Name",
            self.store.load_metadata_list("campaigns")[0]["name"],
        )


if __name__ == "__main__":
    unittest.main()
