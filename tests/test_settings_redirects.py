import unittest
from pathlib import Path

from routes.settings import _safe_return_path


class SettingsRedirectTests(unittest.TestCase):
    def test_theme_return_path_preserves_internal_page_query_and_fragment(self):
        target = "/maps?campaign=world#map-library"
        self.assertEqual(target, _safe_return_path(target, "/settings"))

    def test_theme_return_path_rejects_external_and_ambiguous_targets(self):
        for target in (
            "https://attacker.example/",
            "//attacker.example/",
            r"\attacker.example\share",
            "",
        ):
            with self.subTest(target=target):
                self.assertEqual("/settings", _safe_return_path(target, "/settings"))

    def test_theme_form_tracks_the_current_page(self):
        template = (
            Path(__file__).resolve().parents[1] / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        security_js = (
            Path(__file__).resolve().parents[1] / "static" / "js" / "security.js"
        ).read_text(encoding="utf-8")
        self.assertIn('name="return_to"', template)
        self.assertIn("data-return-to-current-page", template)
        self.assertIn("window.location.hash", security_js)


if __name__ == "__main__":
    unittest.main()
