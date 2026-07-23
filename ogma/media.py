import base64
import hashlib
import os
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path
from uuid import uuid4

from ogma.errors import (
    PayloadTooLargeError,
    StorageUnavailableError,
    UnsupportedMediaError,
)
from werkzeug.utils import secure_filename

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - Pillow is optional for local installs.
    Image = None
    ImageOps = None

try:
    from mutagen import File as MutagenFile
except ImportError:  # pragma: no cover - dependency validation handles this.
    MutagenFile = None


ALLOWED_IMAGE_EXTENSIONS = {".apng", ".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
ALLOWED_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".webm"}
MAX_CLIPBOARD_IMAGE_SIDE = 2200
DEFAULT_THUMBNAIL_MAX_SIDE = 720
UPLOADED_IMAGE_WEBP_QUALITY = 82
MAX_IMAGE_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MAP_IMAGE_UPLOAD_BYTES = 128 * 1024 * 1024
MAX_AUDIO_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_IMAGE_SIDE = 8192
MAX_IMAGE_PIXELS = 40_000_000
MIN_FREE_SPACE_BYTES = 256 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


def media_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def is_allowed_media(filename: str, allowed_extensions: set[str]) -> bool:
    return media_extension(filename) in allowed_extensions


def unique_media_filename(original_filename: str, fallback_stem: str, suffix_length: int = 8, extension: str | None = None) -> str:
    extension = extension if extension is not None else media_extension(original_filename)
    safe_stem = Path(secure_filename(Path(original_filename).stem)).stem or fallback_stem
    return f"{safe_stem}-{uuid4().hex[:suffix_length]}{extension}"


def should_convert_upload_to_webp(allowed_extensions: set[str]) -> bool:
    return bool(allowed_extensions) and allowed_extensions.issubset(ALLOWED_IMAGE_EXTENSIONS) and Image is not None and ImageOps is not None


def save_image_as_webp(source, target_path: Path, quality: int = UPLOADED_IMAGE_WEBP_QUALITY) -> None:
    if Image is None or ImageOps is None:
        raise StorageUnavailableError("Image processing support is unavailable.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            dir=target_path.parent,
            delete=False,
        ) as output:
            temp_path = Path(output.name)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as opened:
                    _validate_image_dimensions(opened)
                    opened.load()
                    image = ImageOps.exif_transpose(opened)
                    _validate_image_dimensions(image)
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    image.save(output, format="WEBP", quality=quality, method=6)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, target_path)
        temp_path = None
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise UnsupportedMediaError("Image exceeds safe decompression limits.") from exc
    except (OSError, ValueError) as exc:
        raise UnsupportedMediaError("Image cannot be safely decoded.") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def save_uploaded_media_file(
    uploaded_file,
    target_dir: Path,
    allowed_extensions: set[str],
    fallback_stem: str,
    suffix_length: int = 8,
    *,
    preserve_image_original: bool = False,
    max_upload_bytes: int | None = None,
) -> dict | None:
    if not uploaded_file or not uploaded_file.filename:
        return None

    original = uploaded_file.filename
    if not is_allowed_media(original, allowed_extensions):
        raise UnsupportedMediaError("Uploaded file extension is not allowed.")

    target_dir.mkdir(parents=True, exist_ok=True)
    is_image = allowed_extensions.issubset(ALLOWED_IMAGE_EXTENSIONS)
    convert_to_webp = should_convert_upload_to_webp(allowed_extensions) and not preserve_image_original
    filename = unique_media_filename(original, fallback_stem, suffix_length=suffix_length, extension=".webp" if convert_to_webp else None)
    target_path = target_dir / filename
    staged_path: Path | None = None
    try:
        default_limit = MAX_IMAGE_UPLOAD_BYTES if is_image else MAX_AUDIO_UPLOAD_BYTES
        limit = max_upload_bytes if max_upload_bytes is not None else default_limit
        staged_path, upload_size = _stage_upload(uploaded_file, target_dir, limit)
        _ensure_free_space(target_dir, upload_size)
        if convert_to_webp:
            save_image_as_webp(staged_path, target_path)
        elif is_image:
            _validate_image_file(staged_path)
            os.replace(staged_path, target_path)
            staged_path = None
        else:
            _validate_audio_magic(staged_path, media_extension(original))
            os.replace(staged_path, target_path)
            staged_path = None
    except (PayloadTooLargeError, StorageUnavailableError, UnsupportedMediaError):
        target_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target_path.unlink(missing_ok=True)
        raise StorageUnavailableError("Uploaded file could not be stored.") from exc
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
    return {
        "filename": filename,
        "original_filename": original,
        "title": Path(original).stem,
        "path": target_path,
    }


def _stage_upload(uploaded_file, target_dir: Path, limit: int) -> tuple[Path, int]:
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".upload-",
            suffix=".staging",
            dir=target_dir,
            delete=False,
        ) as staged:
            staged_path = Path(staged.name)
            try:
                uploaded_file.stream.seek(0)
            except (AttributeError, OSError):
                pass
            size = 0
            while True:
                chunk = uploaded_file.stream.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise PayloadTooLargeError("Uploaded media exceeds its size limit.")
                staged.write(chunk)
            staged.flush()
            os.fsync(staged.fileno())
        return staged_path, size
    except Exception:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        raise


def _ensure_free_space(target_dir: Path, upload_size: int) -> None:
    free = shutil.disk_usage(target_dir).free
    required = 2 * upload_size + MIN_FREE_SPACE_BYTES
    if free < required:
        raise StorageUnavailableError("Not enough free space for a recoverable upload.")


def _validate_image_dimensions(image) -> None:
    width, height = image.size
    if (
        width <= 0
        or height <= 0
        or width > MAX_IMAGE_SIDE
        or height > MAX_IMAGE_SIDE
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise UnsupportedMediaError("Image dimensions exceed safe limits.")


def _validate_image_file(path: Path) -> None:
    if Image is None:
        raise StorageUnavailableError("Image processing support is unavailable.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                _validate_image_dimensions(image)
                image.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise UnsupportedMediaError("Image exceeds safe decompression limits.") from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise UnsupportedMediaError("Image cannot be safely decoded.") from exc


def _validate_audio_magic(path: Path, extension: str) -> None:
    with path.open("rb") as handle:
        header = handle.read(4096)
    checks = {
        ".aac": lambda value: len(value) >= 2 and value[0] == 0xFF and value[1] & 0xF0 == 0xF0,
        ".flac": lambda value: value.startswith(b"fLaC"),
        ".m4a": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        ".mp3": lambda value: value.startswith(b"ID3") or (len(value) >= 2 and value[0] == 0xFF and value[1] & 0xE0 == 0xE0),
        ".oga": lambda value: value.startswith(b"OggS"),
        ".ogg": lambda value: value.startswith(b"OggS"),
        ".opus": lambda value: value.startswith(b"OggS"),
        ".wav": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WAVE",
        ".webm": lambda value: value.startswith(b"\x1a\x45\xdf\xa3"),
    }
    validator = checks.get(extension)
    if validator is None or not validator(header):
        raise UnsupportedMediaError("Audio content does not match its declared format.")
    if extension == ".webm":
        if b"webm" not in header.casefold():
            raise UnsupportedMediaError("WEBM container metadata is invalid.")
        return
    if MutagenFile is None:
        raise StorageUnavailableError("Audio validation support is unavailable.")
    try:
        parsed = MutagenFile(path)
    except Exception as exc:
        raise UnsupportedMediaError("Audio container could not be parsed.") from exc
    if parsed is None or getattr(parsed, "info", None) is None:
        raise UnsupportedMediaError("Audio container could not be parsed.")


def thumbnail_cache_path(image_path: Path, cache_dir: Path, max_side: int = DEFAULT_THUMBNAIL_MAX_SIDE) -> Path | None:
    if Image is None or ImageOps is None:
        return None

    try:
        stat = image_path.stat()
    except OSError:
        return None

    cache_key = hashlib.sha1(f"{image_path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}:{max_side}".encode("utf-8")).hexdigest()
    return cache_dir / f"{cache_key}.webp"


def ensure_thumbnail(image_path: Path, cache_dir: Path, max_side: int = DEFAULT_THUMBNAIL_MAX_SIDE) -> Path | None:
    thumbnail_path = thumbnail_cache_path(image_path, cache_dir, max_side)
    if thumbnail_path is None:
        return None
    if thumbnail_path.exists():
        return thumbnail_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{thumbnail_path.name}.",
            suffix=".tmp",
            dir=cache_dir,
            delete=False,
        ) as output:
            temp_path = Path(output.name)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(image_path) as opened:
                    _validate_image_dimensions(opened)
                    opened.load()
                    image = ImageOps.exif_transpose(opened)
                    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
                    image.thumbnail((max_side, max_side), resampling)
                    if image.mode not in {"RGB", "RGBA"}:
                        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    image.save(output, format="WEBP", quality=78, method=6)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, thumbnail_path)
        temp_path = None
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise UnsupportedMediaError("Image exceeds safe decompression limits.") from exc
    except (OSError, ValueError) as exc:
        raise UnsupportedMediaError("Image cannot be safely decoded.") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return thumbnail_path


def prepare_clipboard_image(image_path: Path, cache_dir: Path, max_side: int = MAX_CLIPBOARD_IMAGE_SIDE) -> tuple[Path, bool]:
    if Image is None or ImageOps is None:
        return image_path, False

    cache_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = cache_dir / f"clipboard-{uuid4().hex}.png"
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image)
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        image.thumbnail((max_side, max_side), resampling)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(prepared_path, format="PNG", optimize=True)
    return prepared_path, True


def copy_image_to_windows_clipboard(
    image_path: Path,
    cache_dir: Path,
    max_side: int = MAX_CLIPBOARD_IMAGE_SIDE,
) -> dict:
    clipboard_path, should_delete = prepare_clipboard_image(image_path, cache_dir, max_side)
    escaped_path = str(clipboard_path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms\n"
        "Add-Type -AssemblyName System.Drawing\n"
        "$ErrorActionPreference = 'Stop'\n"
        f"$sourceImage = [System.Drawing.Image]::FromFile('{escaped_path}')\n"
        f"$maxSide = {max_side}\n"
        "$clipboardImage = $null\n"
        "try {\n"
        "  $width = [int]$sourceImage.Width\n"
        "  $height = [int]$sourceImage.Height\n"
        "  if ($width -gt $maxSide -or $height -gt $maxSide) {\n"
        "    $scale = [Math]::Min($maxSide / $width, $maxSide / $height)\n"
        "    $newWidth = [Math]::Max(1, [int][Math]::Round($width * $scale))\n"
        "    $newHeight = [Math]::Max(1, [int][Math]::Round($height * $scale))\n"
        "    $clipboardImage = New-Object System.Drawing.Bitmap($newWidth, $newHeight)\n"
        "    $graphics = [System.Drawing.Graphics]::FromImage($clipboardImage)\n"
        "    try {\n"
        "      $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic\n"
        "      $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality\n"
        "      $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality\n"
        "      $graphics.DrawImage($sourceImage, 0, 0, $newWidth, $newHeight)\n"
        "    } finally {\n"
        "      $graphics.Dispose()\n"
        "    }\n"
        "  } else {\n"
        "    $clipboardImage = New-Object System.Drawing.Bitmap($sourceImage)\n"
        "  }\n"
        "  [System.Windows.Forms.Clipboard]::Clear()\n"
        "  [System.Windows.Forms.Clipboard]::SetDataObject($clipboardImage, $true, 5, 200)\n"
        "  Start-Sleep -Milliseconds 120\n"
        "  if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) {\n"
        "    throw 'Windows clipboard did not accept the image.'\n"
        "  }\n"
        "} finally {\n"
        "  if ($clipboardImage -ne $null) { $clipboardImage.Dispose() }\n"
        "  $sourceImage.Dispose()\n"
        "}\n"
    )
    encoded_command = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-EncodedCommand", encoded_command],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    finally:
        if should_delete:
            clipboard_path.unlink(missing_ok=True)
    return {
        "prepared": should_delete,
        "max_side": max_side,
    }
