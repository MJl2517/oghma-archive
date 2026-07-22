from urllib.parse import quote

from flask import Response, jsonify, redirect, render_template, request, url_for

from ogma.services import gods as god_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def register_god_routes(bp, views: dict) -> None:
    def gods_page():
        action, context = god_service.gods_page_context(views, request.args)
        if action == "redirect_index":
            return redirect(url_for("index"))
        return render_template("gods.html", **context)

    def create_god():
        action, campaign_slug, payload, status = god_service.create_god(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["gods_redirect"](campaign_slug, payload["god"]["id"])

    def update_god(god_id: str):
        action, campaign_slug, payload, status = god_service.update_god(views, request.form, god_id)
        if action == "not_found":
            if _is_fetch():
                return jsonify(payload), status
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["gods_redirect"](campaign_slug, god_id)

    def delete_gods():
        action, campaign_slug = god_service.delete_gods(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["gods_redirect"](campaign_slug)

    def delete_all_gods():
        action, campaign_slug = god_service.delete_all_gods(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["gods_redirect"](campaign_slug)

    def export_gods():
        action, campaign_slug, filename, payload, status = god_service.export_gods(views, request.args)
        if action == "not_found":
            return render_template("404.html"), 404
        return Response(
            payload,
            status=status,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"ogma-gods.json\"; filename*=UTF-8''{quote(filename)}"},
        )

    def import_gods():
        action, campaign_slug, payload, status = god_service.import_gods(views, request.form, request.files)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["gods_redirect"](campaign_slug)

    def god_catalog():
        campaign_slug = request.args.get("campaign", "").strip()
        force = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        action, payload, status = god_service.god_catalog(views, campaign_slug, force=force)
        if action == "not_found":
            return jsonify(payload), status
        return jsonify(payload), status

    def install_god_packs():
        action, _campaign_slug, payload, status = god_service.install_god_packs(
            views,
            request.get_json(silent=True) or {},
        )
        if action == "not_found":
            return jsonify(payload), status
        return jsonify(payload), status

    def add_god_domain():
        action, campaign_slug, payload = god_service.add_god_domain(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["gods_redirect"](campaign_slug)

    def delete_god_domain():
        action, campaign_slug = god_service.delete_god_domain(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["gods_redirect"](campaign_slug)

    def add_god_filter_value():
        action, campaign_slug, payload, status = god_service.add_god_filter_value(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["gods_redirect"](campaign_slug)

    def delete_god_filter_value():
        action, campaign_slug, payload, status = god_service.delete_god_filter_value(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["gods_redirect"](campaign_slug)

    def reorder_god_filter_values():
        payload, status = god_service.reorder_god_filter_values(views, request.get_json(silent=True) or {}, request.form)
        return jsonify(payload), status

    routes = [
        ("GET", "/gods", "gods_page", gods_page),
        ("POST", "/gods/create", "create_god", create_god),
        ("POST", "/gods/<god_id>/update", "update_god", update_god),
        ("POST", "/gods/delete", "delete_gods", delete_gods),
        ("POST", "/gods/delete-all", "delete_all_gods", delete_all_gods),
        ("GET", "/gods/export", "export_gods", export_gods),
        ("POST", "/gods/import", "import_gods", import_gods),
        ("GET", "/gods/catalog", "god_catalog", god_catalog),
        ("POST", "/gods/catalog/install", "install_god_packs", install_god_packs),
        ("POST", "/gods/domains/add", "add_god_domain", add_god_domain),
        ("POST", "/gods/domains/delete", "delete_god_domain", delete_god_domain),
        ("POST", "/gods/filters/add", "add_god_filter_value", add_god_filter_value),
        ("POST", "/gods/filters/delete", "delete_god_filter_value", delete_god_filter_value),
        ("POST", "/gods/filters/reorder", "reorder_god_filter_values", reorder_god_filter_values),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
