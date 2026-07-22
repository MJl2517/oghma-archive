import os
import tempfile
import unittest
from pathlib import Path

from ogma.safe_paths import PathBoundaryError, resolve_under


class SafePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "media"
        self.root.mkdir()
        (self.root / "nested").mkdir()
        (self.root / "nested" / "image.webp").write_bytes(b"image")
        self.sibling = Path(self.temp_dir.name) / "media-secret"
        self.sibling.mkdir()
        (self.sibling / "secret.txt").write_text("secret", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_nested_file_resolves(self) -> None:
        self.assertEqual(
            (self.root / "nested" / "image.webp").resolve(),
            resolve_under(self.root, "nested/image.webp"),
        )

    def test_traversal_absolute_unc_device_ads_and_repeated_encoding_are_rejected(self) -> None:
        attacks = (
            "../media-secret/secret.txt",
            "%2e%2e%2fmedia-secret%2fsecret.txt",
            "%252e%252e%255cmedia-secret%255csecret.txt",
            "..\\media-secret\\secret.txt",
            "C:\\Windows\\win.ini",
            "\\\\server\\share\\file.txt",
            "\\\\?\\C:\\Windows\\win.ini",
            "nested/image.webp:stream",
            "/etc/passwd",
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises((OSError, PathBoundaryError)):
                    resolve_under(self.root, attack)

    def test_symlink_escape_is_rejected_when_supported(self) -> None:
        link = self.root / "escape"
        try:
            os.symlink(self.sibling, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are not available for this test account.")
        with self.assertRaises(PathBoundaryError):
            resolve_under(self.root, "escape/secret.txt")


if __name__ == "__main__":
    unittest.main()
