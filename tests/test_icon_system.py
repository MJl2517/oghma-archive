import unittest

from app import app


class IconSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        self.headers = {"Host": "oghma.local"}

    def test_base_template_loads_local_icon_assets(self) -> None:
        response = self.client.get("/", headers=self.headers)
        self.addCleanup(response.close)
        self.assertEqual(200, response.status_code)
        self.assertIn(b"/static/css/icons.css", response.data)
        self.assertIn(b"/static/js/icons.js", response.data)

    def test_icon_assets_are_served_and_cover_common_actions(self) -> None:
        stylesheet = self.client.get("/static/css/icons.css", headers=self.headers)
        script = self.client.get("/static/js/icons.js", headers=self.headers)
        self.addCleanup(stylesheet.close)
        self.addCleanup(script.close)
        self.assertEqual(200, stylesheet.status_code)
        self.assertEqual(200, script.status_code)
        for icon_name in (b"settings", b"x", b"pencil", b"folder", b"star", b"search"):
            self.assertIn(b"ui-icon-" + icon_name, stylesheet.data)
        self.assertIn("MutationObserver".encode(), script.data)


if __name__ == "__main__":
    unittest.main()
