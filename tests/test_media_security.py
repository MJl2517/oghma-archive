import io
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from ogma.errors import PayloadTooLargeError, UnsupportedMediaError
from ogma.media import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_MAP_IMAGE_UPLOAD_BYTES,
    ensure_thumbnail,
    save_uploaded_media_file,
)


class MediaSecurityTests(unittest.TestCase):
    def test_invalid_audio_magic_does_not_create_final_or_staging_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=io.BytesIO(b"not an mp3"), filename="track.mp3")
            with self.assertRaises(UnsupportedMediaError):
                save_uploaded_media_file(upload, target, ALLOWED_AUDIO_EXTENSIONS, "audio")
            self.assertEqual([], list(target.iterdir()))

    def test_oversized_audio_is_rejected_without_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=io.BytesIO(b"ID3-too-large"), filename="track.mp3")
            with patch("ogma.media.MAX_AUDIO_UPLOAD_BYTES", 4):
                with self.assertRaises(PayloadTooLargeError):
                    save_uploaded_media_file(upload, target, ALLOWED_AUDIO_EXTENSIONS, "audio")
            self.assertEqual([], list(target.iterdir()))

    def test_valid_audio_must_pass_magic_and_container_parser(self) -> None:
        source = io.BytesIO()
        with wave.open(source, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\x00\x00" * 800)
        source.seek(0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=source, filename="silence.wav")
            result = save_uploaded_media_file(
                upload,
                target,
                ALLOWED_AUDIO_EXTENSIONS,
                "audio",
            )
            self.assertTrue(result["path"].is_file())
            self.assertEqual(".wav", result["path"].suffix)

    def test_valid_image_is_fully_decoded_and_reencoded(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(source, format="PNG")
        source.seek(0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=source, filename="portrait.png")
            result = save_uploaded_media_file(
                upload,
                target,
                ALLOWED_IMAGE_EXTENSIONS,
                "image",
            )
            self.assertEqual(".webp", Path(result["filename"]).suffix)
            with Image.open(result["path"]) as image:
                self.assertEqual((8, 8), image.size)
            self.assertFalse(any(path.suffix in {".tmp", ".staging"} for path in target.iterdir()))

    def test_unsafe_image_dimensions_leave_no_final_file(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(source, format="PNG")
        source.seek(0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=source, filename="portrait.png")
            with patch("ogma.media.MAX_IMAGE_SIDE", 1):
                with self.assertRaises(UnsupportedMediaError):
                    save_uploaded_media_file(
                        upload,
                        target,
                        ALLOWED_IMAGE_EXTENSIONS,
                        "image",
                    )
            self.assertEqual([], list(target.iterdir()))

    def test_map_upload_preserves_original_and_uses_cached_thumbnail(self) -> None:
        self.assertGreaterEqual(MAX_MAP_IMAGE_UPLOAD_BYTES, 61 * 1024 * 1024)
        source = io.BytesIO()
        Image.new("RGB", (1600, 900), "navy").save(source, format="PNG")
        original_bytes = source.getvalue()
        source.seek(0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "maps"
            cache = Path(temp_dir) / "thumbnails"
            upload = FileStorage(stream=source, filename="battle-map.png")
            result = save_uploaded_media_file(
                upload,
                target,
                ALLOWED_IMAGE_EXTENSIONS,
                "map",
                preserve_image_original=True,
                max_upload_bytes=len(original_bytes) + 1,
            )

            self.assertEqual(".png", Path(result["filename"]).suffix)
            self.assertEqual(original_bytes, result["path"].read_bytes())

            thumbnail = ensure_thumbnail(result["path"], cache, max_side=720)
            self.assertIsNotNone(thumbnail)
            self.assertNotEqual(result["path"], thumbnail)
            with Image.open(thumbnail) as image:
                self.assertLessEqual(max(image.size), 720)

    def test_preserved_map_upload_still_enforces_its_explicit_limit(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(source, format="PNG")
        source.seek(0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            upload = FileStorage(stream=source, filename="large-map.png")
            with self.assertRaises(PayloadTooLargeError):
                save_uploaded_media_file(
                    upload,
                    target,
                    ALLOWED_IMAGE_EXTENSIONS,
                    "map",
                    preserve_image_original=True,
                    max_upload_bytes=4,
                )
            self.assertEqual([], list(target.iterdir()))

    def test_map_grid_uses_thumbnail_and_defers_full_image_to_modal_open(self) -> None:
        root = Path(__file__).resolve().parents[1]
        template = (root / "templates" / "_maps_dynamic.html").read_text(encoding="utf-8")
        script = (root / "static" / "js" / "maps.js").read_text(encoding="utf-8")
        self.assertIn('<img src="{{ map.thumbnail_url }}"', template)
        self.assertIn('data-full-src="{{ map.url }}"', template)
        self.assertIn('preview.src = preview.dataset.fullSrc', script)
        self.assertIn('preview.src = preview.dataset.thumbnailSrc', script)


if __name__ == "__main__":
    unittest.main()
