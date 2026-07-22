import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ogma.errors import ConflictError
from ogma.updater import (
    UpdateManager,
    normalize_version,
    parse_checksum,
    parse_latest_release,
    version_key,
)


def release_payload(installer: bytes, *, asset_url_host: str = "github.com") -> dict:
    version = "1.1.0"
    installer_name = f"Oghma-Archive-Setup-{version}.exe"
    checksum_name = f"{installer_name}.sha256"
    digest = hashlib.sha256(installer).hexdigest()
    base = f"https://{asset_url_host}/MJl2517/oghma-archive/releases/download/v{version}"
    checksum = f"{digest} *{installer_name}\n".encode()
    return {
        "tag_name": f"v{version}",
        "name": "Oghma 1.1.0",
        "body": "Update notes",
        "published_at": "2026-07-22T20:00:00Z",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": installer_name,
                "state": "uploaded",
                "size": len(installer),
                "digest": f"sha256:{digest}",
                "browser_download_url": f"{base}/{installer_name}",
            },
            {
                "name": checksum_name,
                "state": "uploaded",
                "size": len(checksum),
                "browser_download_url": f"{base}/{checksum_name}",
            },
        ],
    }


class UpdaterTests(unittest.TestCase):
    def test_versions_are_strict_stable_semver(self):
        self.assertEqual(normalize_version("v01.2.3"), "1.2.3")
        self.assertGreater(version_key("2.0.0"), version_key("1.99.99"))
        for invalid in ("1.2", "1.2.3-beta", "../1.2.3", "1.2.3.4"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_version(invalid)

    def test_release_requires_fixed_repository_assets(self):
        installer = b"MZ-safe-installer"
        parsed = parse_latest_release(release_payload(installer), "1.0.0")
        self.assertTrue(parsed["available"])
        self.assertEqual(parsed["latest_version"], "1.1.0")

        hostile = release_payload(installer, asset_url_host="attacker.example")
        with self.assertRaises(ValueError):
            parse_latest_release(hostile, "1.0.0")

    def test_checksum_is_bound_to_expected_filename(self):
        digest = "a" * 64
        self.assertEqual(
            parse_checksum(f"{digest} *Oghma-Archive-Setup-1.1.0.exe\n".encode(), "Oghma-Archive-Setup-1.1.0.exe"),
            digest,
        )
        with self.assertRaises(ValueError):
            parse_checksum(f"{digest} *another.exe\n".encode(), "Oghma-Archive-Setup-1.1.0.exe")

    def test_download_is_verified_and_does_not_touch_user_content(self):
        installer = b"MZ-safe-installer-payload"
        payload = release_payload(installer)
        installer_name = "Oghma-Archive-Setup-1.1.0.exe"
        digest = hashlib.sha256(installer).hexdigest()
        checksum = f"{digest} *{installer_name}\n".encode()

        def fake_fetch(request, **_kwargs):
            url = request.full_url
            if url.endswith("/releases/latest"):
                return json.dumps(payload).encode()
            if url.endswith(".sha256"):
                return checksum
            if url.endswith(".exe"):
                return installer
            raise AssertionError(url)

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "data"
            campaign_file = data_dir / "campaigns" / "world" / "campaign.json"
            campaign_file.parent.mkdir(parents=True)
            campaign_file.write_text('{"name":"Preserve me"}', encoding="utf-8")
            manager = UpdateManager(
                data_dir,
                Path(directory) / "bundle",
                "1.0.0",
                fetch_bytes=fake_fetch,
                frozen=False,
            )
            result = manager.download_latest()
            self.assertTrue(result["downloaded"])
            self.assertEqual(
                (data_dir / ".updates" / installer_name).read_bytes(),
                installer,
            )
            self.assertEqual(
                campaign_file.read_text(encoding="utf-8"),
                '{"name":"Preserve me"}',
            )
            self.assertTrue(manager.local_status()["downloaded"])
            with self.assertRaises(ConflictError):
                manager.launch_prepared_installer()


if __name__ == "__main__":
    unittest.main()
