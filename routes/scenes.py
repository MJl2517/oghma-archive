from flask import jsonify, render_template, request, send_file

from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import scenes as scene_service


def register_scene_routes(bp, views: dict) -> None:
    def scenes_page():
        template, context = scene_service.scenes_page_context(
            views,
            request.args,
            request.headers.get("X-Requested-With") == "fetch",
        )
        return render_template(template, **context)

    def upload_scenes():
        scene_service.upload_scenes(views, request.form, request.files)
        return views["scenes_redirect"]()

    def delete_scenes():
        scene_service.delete_scenes(views, request.form)
        return views["scenes_redirect"]()

    def delete_all_scenes_route():
        views["delete_all_scenes"]()
        return views["scenes_redirect"]()

    def copy_scene_image(map_id: str):
        copy_data, error, status = scene_service.copy_scene_image_data(views, map_id)
        if copy_data is None:
            return jsonify({"ok": False, "error": error}), status
        image_path, image_url = copy_data
        return views["copy_image_file_response"](
            image_path,
            "\u0424\u0430\u0439\u043b \u0441\u0446\u0435\u043d\u044b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.",
            image_url,
        )

    def add_scene_tag():
        payload = scene_service.add_scene_tag(views, request.form)
        if request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json":
            return jsonify(payload)
        return views["scenes_redirect"]()

    def delete_scene_tag():
        payload, status = scene_service.delete_scene_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["scenes_redirect"]()

    def rename_scene_tag():
        payload, status = scene_service.rename_scene_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["scenes_redirect"]()

    def reorder_scene_tags():
        payload = scene_service.reorder_scene_tags(views, request.get_json(silent=True) or {})
        return jsonify(payload)

    def update_scene(map_id: str):
        payload, status = scene_service.update_scene(views, request.form, map_id)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if is_fetch:
            return jsonify(payload), status
        return views["scenes_redirect"]()

    def _scene_file(scene_id: str):
        item = next(
            (candidate for candidate in views["load_scenes"]() if candidate.get("id") == scene_id),
            None,
        )
        if item is None:
            return None
        try:
            return resolve_under(
                views["scenes_directory"](),
                str(item.get("filename", "")),
            )
        except (OSError, PathBoundaryError):
            return None

    def serve_scene_image(scene_id: str):
        target = _scene_file(scene_id)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    def serve_scene_thumbnail(scene_id: str):
        image_path = _scene_file(scene_id)
        if image_path is None:
            return render_template("404.html"), 404
        return views["thumbnail_response"](image_path)

    routes = [
        ("GET", "/scenes", "scenes_page", scenes_page),
        ("POST", "/scenes/upload", "upload_scenes", upload_scenes),
        ("POST", "/scenes/delete", "delete_scenes", delete_scenes),
        ("POST", "/scenes/delete-all", "delete_all_scenes_route", delete_all_scenes_route),
        ("POST", "/scenes/<map_id>/copy-image", "copy_scene_image", copy_scene_image),
        ("POST", "/scenes/tags/add", "add_scene_tag", add_scene_tag),
        ("POST", "/scenes/tags/delete", "delete_scene_tag", delete_scene_tag),
        ("POST", "/scenes/tags/rename", "rename_scene_tag", rename_scene_tag),
        ("POST", "/scenes/tags/reorder", "reorder_scene_tags", reorder_scene_tags),
        ("POST", "/scenes/<map_id>/update", "update_scene", update_scene),
        ("GET", "/media/scenes/<scene_id>/thumbnail", "serve_scene_thumbnail", serve_scene_thumbnail),
        ("GET", "/media/scenes/<scene_id>", "serve_scene_image", serve_scene_image),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
