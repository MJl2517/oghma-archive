import tempfile
import unittest
from pathlib import Path

from flask import Flask

from ogma.security import configure_local_security, csrf_token


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        configure_local_security(self.app, Path(self.temp_dir.name), 5000)
        self.mutations = 0

        @self.app.get("/")
        def index():
            return csrf_token()

        @self.app.post("/mutate")
        def mutate():
            self.mutations += 1
            return {"ok": True}

        @self.app.post("/json")
        def json_mutate():
            self.mutations += 1
            return {"ok": True}

        self.client = self.app.test_client()
        self.host = "oghma.local"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def token(self) -> str:
        response = self.client.get("/", headers={"Host": self.host})
        self.assertEqual(200, response.status_code)
        return response.get_data(as_text=True)

    def test_untrusted_host_is_rejected_before_view(self) -> None:
        response = self.client.get("/", headers={"Host": "localhost.evil.example"})
        self.assertEqual(400, response.status_code)
        self.assertEqual("invalid_host", response.get_json()["error"]["code"])

    def test_missing_and_invalid_csrf_are_rejected(self) -> None:
        self.token()
        for headers in (
            {"Host": self.host, "Origin": f"http://{self.host}"},
            {
                "Host": self.host,
                "Origin": f"http://{self.host}",
                "X-CSRF-Token": "invalid",
            },
        ):
            with self.subTest(headers=headers):
                response = self.client.post("/mutate", headers=headers)
                self.assertEqual(403, response.status_code)
        self.assertEqual(0, self.mutations)

    def test_cross_site_request_is_rejected_even_with_valid_csrf(self) -> None:
        token = self.token()
        response = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "https://attacker.example",
                "Sec-Fetch-Site": "cross-site",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual(0, self.mutations)

    def test_same_origin_request_with_csrf_is_allowed(self) -> None:
        token = self.token()
        response = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": f"http://{self.host}",
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, self.mutations)

    def test_only_canonical_public_host_and_origin_are_allowed(self) -> None:
        token = self.token()
        for host in (
            "127.0.0.1:5000",
            "localhost:5000",
            "ogma.local",
            "oghma.local:5000",
        ):
            with self.subTest(host=host):
                response = self.client.get("/", headers={"Host": host})
                self.assertEqual(400, response.status_code)

        wrong_origin = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "http://127.0.0.1:5000",
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(403, wrong_origin.status_code)
        self.assertEqual("invalid_origin", wrong_origin.get_json()["error"]["code"])
        self.assertEqual(0, self.mutations)

    def test_external_origin_is_rejected_without_fetch_metadata(self) -> None:
        token = self.token()
        response = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "http://attacker.example",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual("invalid_origin", response.get_json()["error"]["code"])
        self.assertEqual(0, self.mutations)

    def test_opaque_origin_requires_valid_csrf_even_without_fetch_metadata(self) -> None:
        token = self.token()
        allowed_with_metadata = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "null",
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(200, allowed_with_metadata.status_code)
        self.assertEqual(1, self.mutations)

        allowed_without_metadata = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "null",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(200, allowed_without_metadata.status_code)
        self.assertEqual(2, self.mutations)

        invalid_csrf = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "null",
                "Sec-Fetch-Site": "same-site",
                "X-CSRF-Token": "invalid",
            },
        )
        self.assertEqual(403, invalid_csrf.status_code)
        self.assertEqual("invalid_csrf", invalid_csrf.get_json()["error"]["code"])
        self.assertEqual(2, self.mutations)

        explicit_cross_site = self.client.post(
            "/mutate",
            headers={
                "Host": self.host,
                "Origin": "null",
                "Sec-Fetch-Site": "cross-site",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(403, explicit_cross_site.status_code)
        self.assertEqual(
            "cross_site_request",
            explicit_cross_site.get_json()["error"]["code"],
        )
        self.assertEqual(2, self.mutations)

    def test_security_headers_are_applied(self) -> None:
        response = self.client.get("/", headers={"Host": self.host})
        self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
        self.assertEqual("DENY", response.headers["X-Frame-Options"])
        self.assertEqual("no-referrer", response.headers["Referrer-Policy"])
        self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual("no-store", response.headers["Cache-Control"])

    def test_deep_json_is_rejected_without_side_effect(self) -> None:
        token = self.token()
        payload = {}
        cursor = payload
        for _ in range(35):
            cursor["child"] = {}
            cursor = cursor["child"]
        response = self.client.post(
            "/json",
            json=payload,
            headers={
                "Host": self.host,
                "Origin": f"http://{self.host}",
                "X-CSRF-Token": token,
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual(0, self.mutations)


if __name__ == "__main__":
    unittest.main()
