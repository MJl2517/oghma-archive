from urllib.parse import quote

from flask import Response, jsonify, redirect, render_template, request, url_for

from ogma.services import rules as rule_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def register_rule_routes(bp, views: dict) -> None:
    def rules_page():
        return render_template("glossary.html", **rule_service.rules_page_context(views))

    def rule_preview(rule_id: str):
        payload, status = rule_service.rule_preview(views, rule_id)
        return jsonify(payload), status

    def add_rule():
        payload = rule_service.add_rule(views, request.form)
        if _is_fetch():
            return jsonify(payload), 201
        return redirect(url_for("rules_page"))

    def export_rules():
        filename, payload, status = rule_service.export_rules(views)
        return Response(
            payload,
            status=status,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"ogma-rules-glossary.json\"; filename*=UTF-8''{quote(filename)}"},
        )

    def import_rules():
        payload, status = rule_service.import_rules(views, request.files)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def glossary_catalog():
        force = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        return jsonify(rule_service.glossary_catalog(views, force=force))

    def install_glossary_packs():
        payload, status = rule_service.install_glossary_packs(
            views,
            request.get_json(silent=True) or {},
        )
        return jsonify(payload), status

    def update_rule(rule_id: str):
        payload, status = rule_service.update_rule(views, request.form, rule_id)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def delete_rule(rule_id: str):
        payload, status = rule_service.delete_rule(views, rule_id)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def add_rule_tag():
        payload = rule_service.add_rule_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return redirect(url_for("rules_page"))

    def delete_rule_tag():
        payload, status = rule_service.delete_rule_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def rename_rule_tag():
        payload, status = rule_service.rename_rule_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def reorder_rule_tags():
        return jsonify(rule_service.reorder_rule_tags(views, request.get_json(silent=True) or {}))

    def add_rule_source():
        payload = rule_service.add_rule_source(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return redirect(url_for("rules_page"))

    def delete_rule_source():
        payload = rule_service.delete_rule_source(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return redirect(url_for("rules_page"))

    def rename_rule_source():
        payload, status = rule_service.rename_rule_source(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return redirect(url_for("rules_page"))

    def reorder_rule_sources():
        return jsonify(rule_service.reorder_rule_sources(views, request.get_json(silent=True) or {}))

    routes = [
        ("GET", "/rules", "rules_page", rules_page),
        ("GET", "/rules/<rule_id>/preview", "rule_preview", rule_preview),
        ("POST", "/rules/add", "add_rule", add_rule),
        ("GET", "/rules/export", "export_rules", export_rules),
        ("POST", "/rules/import", "import_rules", import_rules),
        ("GET", "/rules/glossaries/catalog", "glossary_catalog", glossary_catalog),
        ("POST", "/rules/glossaries/install", "install_glossary_packs", install_glossary_packs),
        ("POST", "/rules/<rule_id>/update", "update_rule", update_rule),
        ("POST", "/rules/<rule_id>/delete", "delete_rule", delete_rule),
        ("POST", "/rules/tags/add", "add_rule_tag", add_rule_tag),
        ("POST", "/rules/tags/delete", "delete_rule_tag", delete_rule_tag),
        ("POST", "/rules/tags/rename", "rename_rule_tag", rename_rule_tag),
        ("POST", "/rules/tags/reorder", "reorder_rule_tags", reorder_rule_tags),
        ("POST", "/rules/sources/add", "add_rule_source", add_rule_source),
        ("POST", "/rules/sources/delete", "delete_rule_source", delete_rule_source),
        ("POST", "/rules/sources/rename", "rename_rule_source", rename_rule_source),
        ("POST", "/rules/sources/reorder", "reorder_rule_sources", reorder_rule_sources),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
