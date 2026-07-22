from flask import jsonify, render_template, request, send_file

from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import audio as audio_service


def register_audio_routes(bp, views: dict) -> None:
    def audio_page():
        return render_template("audio.html", **audio_service.audio_page_context(views, request.args))

    def upload_audio():
        audio_service.upload_audio(views, request.form, request.files)
        return views["audio_redirect"]()

    def create_audio_link():
        payload, status = audio_service.create_audio_link(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch and status != 200:
            return jsonify(payload), status
        return views["audio_redirect"]()

    def delete_audio():
        audio_service.delete_audio(views, request.form)
        return views["audio_redirect"]()

    def add_audio_tag():
        payload = audio_service.add_audio_tag(views, request.form)
        if request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json":
            return jsonify(payload)
        return views["audio_redirect"]()

    def delete_audio_tag():
        payload, status = audio_service.delete_audio_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["audio_redirect"]()

    def rename_audio_tag():
        payload, status = audio_service.rename_audio_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["audio_redirect"]()

    def add_audio_category():
        payload = audio_service.add_audio_category(views, request.form)
        if request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json":
            return jsonify(payload)
        return views["audio_redirect"]()

    def delete_audio_category():
        payload, status = audio_service.delete_audio_category(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["audio_redirect"]()

    def rename_audio_category():
        payload, status = audio_service.rename_audio_category(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["audio_redirect"]()

    def reorder_audio_categories():
        payload = audio_service.reorder_audio_categories(views, request.get_json(silent=True) or {})
        return jsonify(payload)

    def update_audio(track_id: str):
        audio_service.update_audio(views, request.form, track_id)
        return views["audio_redirect"]()

    def _audio_file(track_id: str, *, thumbnail: bool = False):
        item = next(
            (candidate for candidate in views["load_audio_tracks"]() if candidate.get("id") == track_id),
            None,
        )
        if item is None:
            return None
        filename = (
            item.get("thumbnail_filename", "")
            if thumbnail
            else item.get("filename", "")
        )
        if not filename:
            return None
        try:
            return resolve_under(views["audio_directory"](), str(filename))
        except (OSError, PathBoundaryError):
            return None

    def serve_audio_file(track_id: str):
        target = _audio_file(track_id)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    def serve_audio_thumbnail(track_id: str):
        target = _audio_file(track_id, thumbnail=True)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    routes = [
        ("GET", "/audio", "audio_page", audio_page),
        ("POST", "/audio/upload", "upload_audio", upload_audio),
        ("POST", "/audio/create-link", "create_audio_link", create_audio_link),
        ("POST", "/audio/delete", "delete_audio", delete_audio),
        ("POST", "/audio/tags/add", "add_audio_tag", add_audio_tag),
        ("POST", "/audio/tags/delete", "delete_audio_tag", delete_audio_tag),
        ("POST", "/audio/tags/rename", "rename_audio_tag", rename_audio_tag),
        ("POST", "/audio/categories/add", "add_audio_category", add_audio_category),
        ("POST", "/audio/categories/delete", "delete_audio_category", delete_audio_category),
        ("POST", "/audio/categories/rename", "rename_audio_category", rename_audio_category),
        ("POST", "/audio/categories/reorder", "reorder_audio_categories", reorder_audio_categories),
        ("POST", "/audio/<track_id>/update", "update_audio", update_audio),
        ("GET", "/media/audio/<track_id>", "serve_audio_file", serve_audio_file),
        ("GET", "/media/audio/<track_id>/thumbnail", "serve_audio_thumbnail", serve_audio_thumbnail),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
