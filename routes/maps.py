from flask import jsonify, redirect, render_template, request, send_file, url_for

from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import maps as map_service


def register_map_routes(bp, views: dict) -> None:
    def maps_page():
        template, context = map_service.maps_page_context(
            views,
            request.args,
            request.headers.get("X-Requested-With") == "fetch",
        )
        if template == "redirect_without_campaign":
            args = request.args.to_dict(flat=False)
            args.pop("campaign", None)
            return redirect(url_for("maps_page", **args))
        return render_template(template, **context)

    def upload_maps():
        scope, campaign_slug = map_service.upload_maps(views, request.form, request.files)
        if scope == "not_found":
            return render_template("404.html"), 404
        return views["maps_redirect"](scope, campaign_slug)

    def delete_maps():
        scope, campaign_slug = map_service.delete_maps(views, request.form)
        if scope == "not_found":
            return render_template("404.html"), 404
        return views["maps_redirect"](scope, campaign_slug)

    def delete_all_maps_route():
        scope, campaign_slug = map_service.delete_all_maps(views, request.form)
        if scope == "not_found":
            return render_template("404.html"), 404
        return views["maps_redirect"](scope, campaign_slug)

    def copy_map_image(map_id: str):
        copy_data, error, status = map_service.copy_map_image_data(views, request.form, map_id)
        if copy_data is None:
            return jsonify({"ok": False, "error": error}), status
        image_path, image_url = copy_data
        return views["copy_image_file_response"](image_path, "\u0424\u0430\u0439\u043b \u043a\u0430\u0440\u0442\u044b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.", image_url)

    def add_map_tag():
        scope, campaign_slug, payload = map_service.add_map_tag(views, request.form)
        if scope == "not_found":
            return render_template("404.html"), 404
        if request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json":
            return jsonify(payload)
        return views["maps_redirect"](scope, campaign_slug)

    def delete_map_tag():
        scope, campaign_slug, payload, status = map_service.delete_map_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if scope == "not_found":
            return render_template("404.html"), 404
        if is_fetch:
            return jsonify(payload), status
        return views["maps_redirect"](scope, campaign_slug)

    def rename_map_tag():
        scope, campaign_slug, payload, status = map_service.rename_map_tag(views, request.form)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if scope == "not_found":
            return render_template("404.html"), 404
        if is_fetch:
            return jsonify(payload), status
        return views["maps_redirect"](scope, campaign_slug)

    def update_map(map_id: str):
        scope, campaign_slug, payload, status = map_service.update_map(views, request.form, map_id)
        is_fetch = request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"
        if status == 404 and not is_fetch:
            return render_template("404.html"), 404
        if is_fetch:
            return jsonify(payload), status
        return views["maps_redirect"](scope, campaign_slug)

    def _map_file(scope: str, campaign_slug: str, map_id: str):
        item = next(
            (candidate for candidate in views["load_maps"](scope, campaign_slug) if candidate.get("id") == map_id),
            None,
        )
        if item is None:
            return None
        try:
            return resolve_under(
                views["maps_directory"](scope, campaign_slug),
                str(item.get("filename", "")),
            )
        except (OSError, PathBoundaryError):
            return None

    def serve_shared_map(map_id: str):
        target = _map_file("shared", "", map_id)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    def serve_shared_map_thumbnail(map_id: str):
        image_path = _map_file("shared", "", map_id)
        if image_path is None:
            return render_template("404.html"), 404
        return views["thumbnail_response"](image_path)

    def serve_campaign_map(campaign_slug: str, map_id: str):
        campaign = views["get_campaign"](campaign_slug)
        if campaign is None:
            return render_template("404.html"), 404
        target = _map_file("campaign", campaign_slug, map_id)
        if target is None:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    def serve_campaign_map_thumbnail(campaign_slug: str, map_id: str):
        campaign = views["get_campaign"](campaign_slug)
        if campaign is None:
            return render_template("404.html"), 404
        image_path = _map_file("campaign", campaign_slug, map_id)
        if image_path is None:
            return render_template("404.html"), 404
        return views["thumbnail_response"](image_path)

    routes = [
        ("GET", "/maps", "maps_page", maps_page),
        ("POST", "/maps/upload", "upload_maps", upload_maps),
        ("POST", "/maps/delete", "delete_maps", delete_maps),
        ("POST", "/maps/delete-all", "delete_all_maps_route", delete_all_maps_route),
        ("POST", "/maps/<map_id>/copy-image", "copy_map_image", copy_map_image),
        ("POST", "/maps/tags/add", "add_map_tag", add_map_tag),
        ("POST", "/maps/tags/delete", "delete_map_tag", delete_map_tag),
        ("POST", "/maps/tags/rename", "rename_map_tag", rename_map_tag),
        ("POST", "/maps/<map_id>/update", "update_map", update_map),
        ("GET", "/media/maps/shared/<map_id>/thumbnail", "serve_shared_map_thumbnail", serve_shared_map_thumbnail),
        ("GET", "/media/maps/shared/<map_id>", "serve_shared_map", serve_shared_map),
        ("GET", "/media/maps/campaign/<campaign_slug>/<map_id>/thumbnail", "serve_campaign_map_thumbnail", serve_campaign_map_thumbnail),
        ("GET", "/media/maps/campaign/<campaign_slug>/<map_id>", "serve_campaign_map", serve_campaign_map),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
