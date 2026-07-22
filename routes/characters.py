from flask import jsonify, redirect, render_template, request, send_file, url_for

from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import characters as character_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def register_character_routes(bp, views: dict) -> None:
    def characters_page():
        action, context = character_service.characters_page_context(views, request.args)
        if action == "redirect_index":
            return redirect(url_for("index"))
        return render_template("characters.html", **context)

    def upload_characters():
        action, campaign_slug = character_service.upload_characters(views, request.form, request.files)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["characters_redirect"](campaign_slug)

    def delete_characters():
        action, campaign_slug = character_service.delete_characters(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["characters_redirect"](campaign_slug)

    def delete_all_characters_route():
        action, campaign_slug = character_service.delete_all_characters(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["characters_redirect"](campaign_slug)

    def add_character_group():
        action, campaign_slug, payload = character_service.add_character_group(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["characters_redirect"](campaign_slug)

    def delete_character_group():
        action, campaign_slug, payload, status = character_service.delete_character_group(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["characters_redirect"](campaign_slug)

    def rename_character_group():
        action, campaign_slug, payload, status = character_service.rename_character_group(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["characters_redirect"](campaign_slug)

    def reorder_character_groups():
        payload, status = character_service.reorder_character_groups(views, request.form, request.get_json(silent=True) or {})
        return jsonify(payload), status

    def copy_character_image(character_id: str):
        action, payload, status = character_service.copy_character_image_data(views, request.form, character_id)
        if action == "error":
            return jsonify(payload), status
        return views["copy_image_file_response"](
            payload["image_path"],
            payload["missing_message"],
            payload["clipboard_image_url"],
        )

    def update_character(character_id: str):
        action, campaign_slug, payload, status = character_service.update_character(views, request.form, character_id)
        if action == "not_found":
            if _is_fetch():
                return jsonify(payload), status
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["characters_redirect"](campaign_slug)

    def _character_file(campaign_slug: str, character_id: str):
        directory = character_service.character_image_directory(views, campaign_slug)
        if directory is None:
            return None
        item = next(
            (
                candidate
                for candidate in views["load_characters"](campaign_slug)
                if candidate.get("id") == character_id
            ),
            None,
        )
        if item is None:
            return None
        try:
            return resolve_under(directory, str(item.get("filename", "")))
        except (OSError, PathBoundaryError):
            return None

    def serve_character_image(campaign_slug: str, character_id: str):
        target = _character_file(campaign_slug, character_id)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    def serve_character_thumbnail(campaign_slug: str, character_id: str):
        image_path = _character_file(campaign_slug, character_id)
        if image_path is None:
            return render_template("404.html"), 404
        return views["thumbnail_response"](image_path)

    routes = [
        ("GET", "/characters", "characters_page", characters_page),
        ("POST", "/characters/upload", "upload_characters", upload_characters),
        ("POST", "/characters/delete", "delete_characters", delete_characters),
        ("POST", "/characters/delete-all", "delete_all_characters_route", delete_all_characters_route),
        ("POST", "/characters/groups/add", "add_character_group", add_character_group),
        ("POST", "/characters/groups/delete", "delete_character_group", delete_character_group),
        ("POST", "/characters/groups/rename", "rename_character_group", rename_character_group),
        ("POST", "/characters/groups/reorder", "reorder_character_groups", reorder_character_groups),
        ("POST", "/characters/<character_id>/copy-image", "copy_character_image", copy_character_image),
        ("POST", "/characters/<character_id>/update", "update_character", update_character),
        ("GET", "/media/characters/<campaign_slug>/<character_id>/thumbnail", "serve_character_thumbnail", serve_character_thumbnail),
        ("GET", "/media/characters/<campaign_slug>/<character_id>", "serve_character_image", serve_character_image),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
