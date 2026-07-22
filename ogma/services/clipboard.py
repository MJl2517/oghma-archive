import subprocess

from ogma.errors import ExternalOperationError


CLIPBOARD_IMAGE_MISSING = "\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u043d\u0435 \u043f\u0435\u0440\u0435\u0434\u0430\u043d\u043e."


def copy_prepared_image(deps: dict, uploaded_file) -> tuple[dict, int]:
    if not uploaded_file or not uploaded_file.filename:
        return {"ok": False, "error": CLIPBOARD_IMAGE_MISSING}, 400

    deps["CLIPBOARD_CACHE_DIR"].mkdir(parents=True, exist_ok=True)
    saved = deps["save_uploaded_media_file"](
        uploaded_file,
        deps["CLIPBOARD_CACHE_DIR"],
        deps["ALLOWED_IMAGE_EXTENSIONS"],
        "browser-clipboard",
    )
    if saved is None:
        return {"ok": False, "error": CLIPBOARD_IMAGE_MISSING}, 400
    prepared_path = saved["path"]

    def operation():
        try:
            clipboard_result = deps["copy_image_to_windows_clipboard"](prepared_path.resolve())
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise ExternalOperationError("Windows clipboard operation failed.") from exc
        finally:
            prepared_path.unlink(missing_ok=True)
        return {"ok": True, **clipboard_result}

    try:
        job_id = deps["start_local_job"]("copy_uploaded_image_to_clipboard", operation)
    except Exception:
        prepared_path.unlink(missing_ok=True)
        raise
    return {
        "ok": True,
        "job_id": job_id,
        "status_url": deps["url_for"]("local_job_status", job_id=job_id),
    }, 202
