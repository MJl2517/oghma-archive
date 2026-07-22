import unittest

from flask import Flask

from routes import register_domain_routes


class RouteUniquenessTests(unittest.TestCase):
    def _app(self) -> Flask:
        app = Flask(__name__)
        register_domain_routes(app, {})
        return app

    def test_domain_url_map_has_no_duplicate_path_method_pairs(self) -> None:
        app = self._app()
        seen = {}
        duplicates = []
        for rule in app.url_map.iter_rules():
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                key = (rule.rule, method)
                if key in seen:
                    duplicates.append((key, seen[key], rule.endpoint))
                else:
                    seen[key] = rule.endpoint
        self.assertEqual([], duplicates)

    def test_application_media_routes_do_not_accept_raw_filenames(self) -> None:
        for rule in self._app().url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            self.assertNotIn("filename", rule.arguments, rule.rule)
            self.assertNotIn("<path:", rule.rule, rule.rule)

    def test_side_effect_endpoints_are_not_get_routes(self) -> None:
        side_effect_verbs = {
            "add",
            "copy",
            "create",
            "delete",
            "import",
            "open",
            "pick",
            "rename",
            "save",
            "set",
            "sync",
            "toggle",
            "update",
            "upload",
        }
        unsafe_gets = []
        for rule in self._app().url_map.iter_rules():
            endpoint_words = set(rule.endpoint.lower().split("_"))
            if "GET" in rule.methods and endpoint_words & side_effect_verbs:
                unsafe_gets.append((rule.endpoint, rule.rule))
        self.assertEqual([], unsafe_gets)

    def test_global_map_routes_are_not_registered(self) -> None:
        rules = list(self._app().url_map.iter_rules())
        self.assertFalse(
            any("world-map" in rule.rule or "world_map" in rule.endpoint for rule in rules),
            [(rule.endpoint, rule.rule) for rule in rules],
        )


if __name__ == "__main__":
    unittest.main()
