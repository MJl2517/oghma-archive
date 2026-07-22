import tempfile
import unittest
from pathlib import Path

from ogma.errors import ValidationError
from ogma.safe_paths import PathBoundaryError, normalize_relative_path, resolve_destination_under
from ogma.services.party import resolve_foundry_export_dir, save_party_sync_config


class FoundryBoundaryTests(unittest.TestCase):
    def test_relative_paths_reject_absolute_drive_ads_and_traversal(self):
        for value in (
            r"C:\Foundry\Data",
            r"\\server\share",
            "../outside",
            "assets/../../outside",
            "assets/file.txt:stream",
            "%252e%252e/outside",
        ):
            with self.subTest(value=value):
                with self.assertRaises(PathBoundaryError):
                    normalize_relative_path(value)

    def test_destination_stays_below_approved_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = resolve_destination_under(root, "assets/ogma/new")
            destination.relative_to(root.resolve())

    def test_party_export_rejects_absolute_or_traversal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deps = {
                "foundry_data_dir": lambda: root,
                "DATA_DIR": root / "app-data",
            }
            for value in (r"C:\exports", "../exports", "//server/export"):
                with self.subTest(value=value):
                    with self.assertRaises(ValidationError):
                        resolve_foundry_export_dir(deps, value)

            resolved = resolve_foundry_export_dir(deps, "ogma-party-export/campaign")
            resolved.relative_to(root.resolve())

    def test_sync_config_stores_only_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            deps = {"DATA_DIR": Path(directory)}
            with self.assertRaises(ValidationError):
                save_party_sync_config(
                    deps,
                    "campaign",
                    {"foundry_export_dir": r"C:\outside"},
                )


if __name__ == "__main__":
    unittest.main()
