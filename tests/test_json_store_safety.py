import tempfile
import unittest
from pathlib import Path

from ogma.json_store import JsonIntegrityError, read_json, write_json


class JsonStoreSafetyTests(unittest.TestCase):
    def test_write_is_atomic_and_keeps_previous_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            write_json(path, {"version": 1})
            write_json(path, {"version": 2})

            self.assertEqual({"version": 2}, read_json(path))
            self.assertEqual(
                {"version": 1},
                read_json(path.with_name("settings.json.bak")),
            )
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_serialization_failure_preserves_current_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "party.json"
            write_json(path, {"members": ["keeper"]})

            with self.assertRaises(TypeError):
                write_json(path, {"members": {"not", "json"}})

            self.assertEqual({"members": ["keeper"]}, read_json(path))
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_corrupt_json_reports_recovery_path_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(JsonIntegrityError, "settings.json.bak"):
                read_json(path)

            self.assertEqual("{broken", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
