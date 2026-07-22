import unittest

from ogma.services.campaigns import delete_campaign


class CampaignDeleteSafetyTests(unittest.TestCase):
    def test_campaign_delete_is_blocked_before_any_destructive_action(self) -> None:
        calls = []
        deps = {
            "get_campaign": lambda slug: {"slug": slug},
            "remove_campaign_foundry_junctions": lambda slug: calls.append(("junction", slug)),
            "delete_campaign_record": lambda slug: calls.append(("database", slug)),
        }

        self.assertEqual("disabled", delete_campaign(deps, "protected-world"))
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
