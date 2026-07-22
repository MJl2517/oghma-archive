import tempfile
import unittest
from pathlib import Path

from ogma.runtime_paths import PRODUCT_DIRECTORY_NAME, default_data_dir


class RuntimePathTests(unittest.TestCase):
    def test_source_launch_keeps_workspace_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            self.assertEqual(
                default_data_dir(source_root, environ={}, frozen=False),
                (source_root / "data").resolve(),
            )

    def test_packaged_launch_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory) / "bundle"
            local_app_data = Path(directory) / "LocalAppData"
            self.assertEqual(
                default_data_dir(
                    source_root,
                    environ={"LOCALAPPDATA": str(local_app_data)},
                    frozen=True,
                ),
                (local_app_data / PRODUCT_DIRECTORY_NAME / "data").resolve(),
            )

    def test_explicit_data_directory_always_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "custom-data"
            self.assertEqual(
                default_data_dir(
                    Path(directory) / "bundle",
                    environ={"OGMA_DATA_DIR": str(configured)},
                    frozen=True,
                ),
                configured.resolve(),
            )


if __name__ == "__main__":
    unittest.main()
