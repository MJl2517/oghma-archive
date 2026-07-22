import unittest

from app import CAMPAIGN_FOLDERS, SECTIONS, SHARED_FOLDERS, app


class GlobalMapsRemovalTests(unittest.TestCase):
    def test_global_maps_are_absent_from_sections_and_new_storage_layout(self) -> None:
        self.assertNotIn("world-maps", {section.get("slug") for section in SECTIONS})
        self.assertNotIn("world-maps", CAMPAIGN_FOLDERS)
        self.assertNotIn("world-markers", SHARED_FOLDERS)

    def test_global_map_routes_are_absent_from_application(self) -> None:
        rules = list(app.url_map.iter_rules())
        self.assertFalse(
            any("world-map" in rule.rule or "world_map" in rule.endpoint for rule in rules),
            [(rule.endpoint, rule.rule) for rule in rules],
        )


if __name__ == "__main__":
    unittest.main()
