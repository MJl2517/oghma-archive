import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ogma.capabilities import DirectoryCapabilityStore, FileCapabilityStore
from ogma.errors import ValidationError
from ogma.media_catalog import prepare_resources
from ogma.services import resources as resource_service


class CapabilityAndResourceTests(unittest.TestCase):
    def test_file_and_directory_capabilities_are_opaque_and_one_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / "private-name.pdf"
            selected.write_bytes(b"%PDF")

            file_store = FileCapabilityStore()
            token, display = file_store.issue(selected)
            self.assertNotIn(str(root), token)
            self.assertEqual(display, selected.name)
            self.assertEqual(file_store.consume(token), selected.resolve())
            with self.assertRaises(ValidationError):
                file_store.consume(token)

            directory_store = DirectoryCapabilityStore()
            directory_token, directory_display = directory_store.issue(root)
            self.assertNotIn(str(root), directory_token)
            self.assertEqual(directory_display, root.name)
            self.assertEqual(directory_store.consume(directory_token), root.resolve())

    def test_prepared_local_resource_never_exposes_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory) / "manual.pdf"
            selected.write_bytes(b"%PDF")
            prepared = prepare_resources(
                lambda: [{"id": "r1", "source_type": "local", "path": str(selected)}],
                lambda value: "local" if value == "local" else "web",
                lambda value: [],
            )
            self.assertEqual(prepared[0]["target"], "manual.pdf")
            self.assertEqual(prepared[0]["path_display"], "manual.pdf")
            self.assertNotIn("path", prepared[0])
            self.assertTrue(prepared[0]["exists"])

    def test_resource_create_uses_capability_not_submitted_raw_path(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory) / "approved.pdf"
            selected.write_bytes(b"%PDF")
            store = FileCapabilityStore()
            token, _display = store.issue(selected)
            saved = []
            deps = {
                "load_resources": lambda: [],
                "normalize_resource_type": lambda value: value,
                "resolve_file_capability": store.consume,
                "normalize_resource_category": lambda value: value,
                "normalize_resource_item_tags": lambda value: [],
                "datetime": datetime,
                "uuid4": uuid4,
                "load_resource_tags": lambda: [],
                "load_resource_categories": lambda: ["Books"],
                "save_resource_tags": lambda value: None,
                "save_resource_categories": lambda value: None,
                "save_resources": lambda value: saved.extend(value),
                "DEFAULT_RESOURCE_CATEGORIES": ["Books"],
            }
            form = {
                "source_type": "local",
                "path": r"C:\Windows\System32\cmd.exe",
                "file_capability": token,
                "title": "",
                "category": "Books",
                "tags": "",
                "description": "",
            }
            resource_service.create_resource(deps, form)
            self.assertEqual(saved[0]["path"], str(selected.resolve()))
            self.assertNotIn("cmd.exe", saved[0]["path"])


if __name__ == "__main__":
    unittest.main()
