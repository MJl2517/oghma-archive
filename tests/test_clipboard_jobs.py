import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ogma.services.clipboard import copy_prepared_image


class ClipboardJobTests(unittest.TestCase):
    def test_native_clipboard_subprocess_is_deferred_to_local_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            prepared_path = cache_dir / "prepared.webp"
            prepared_path.write_bytes(b"safe-test-image")
            operations = []
            clipboard_calls = []

            def start_local_job(kind, operation):
                self.assertEqual("copy_uploaded_image_to_clipboard", kind)
                operations.append(operation)
                return "opaque-job"

            deps = {
                "ALLOWED_IMAGE_EXTENSIONS": {".png"},
                "CLIPBOARD_CACHE_DIR": cache_dir,
                "copy_image_to_windows_clipboard": lambda path: clipboard_calls.append(path)
                or {"prepared": True},
                "save_uploaded_media_file": lambda *_args: {"path": prepared_path},
                "start_local_job": start_local_job,
                "url_for": lambda _endpoint, **_values: "/jobs/opaque-job",
            }

            payload, status = copy_prepared_image(
                deps,
                SimpleNamespace(filename="clipboard.png"),
            )

            self.assertEqual(202, status)
            self.assertEqual("opaque-job", payload["job_id"])
            self.assertEqual([], clipboard_calls)
            self.assertTrue(prepared_path.exists())

            result = operations[0]()
            self.assertEqual({"ok": True, "prepared": True}, result)
            self.assertEqual([prepared_path.resolve()], clipboard_calls)
            self.assertFalse(prepared_path.exists())


if __name__ == "__main__":
    unittest.main()
