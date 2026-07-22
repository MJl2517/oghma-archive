from flask import jsonify, redirect, render_template, request, url_for

from ogma.services import notes as note_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def register_note_routes(bp, views: dict) -> None:
    def notes_page():
        query = request.args.copy()
        if _is_fetch():
            query["_skip_reference_options"] = "1"
        action, context = note_service.notes_page_context(views, query)
        if action == "redirect_index":
            return redirect(url_for("index"))
        return render_template("notes.html", **context)

    def material_preview():
        payload, status = note_service.material_preview(views, request.args)
        return jsonify(payload), status

    def create_note():
        action, campaign_slug, payload, status = note_service.create_note(views, request.form)
        if action == "not_found":
            if _is_fetch():
                return jsonify(payload), status
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["notes_redirect"](campaign_slug, payload["note"]["id"])

    def update_note(note_id: str):
        action, campaign_slug, payload, status = note_service.update_note(views, request.form, note_id)
        if action == "not_found":
            if _is_fetch():
                return jsonify(payload), status
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["notes_redirect"](campaign_slug, note_id)

    def delete_notes():
        action, campaign_slug = note_service.delete_notes(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["notes_redirect"](campaign_slug)

    def delete_all_notes():
        action, campaign_slug = note_service.delete_all_notes(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        return views["notes_redirect"](campaign_slug)

    def add_note_tag():
        action, campaign_slug, payload = note_service.add_note_tag(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload)
        return views["notes_redirect"](campaign_slug)

    def delete_note_tag():
        action, campaign_slug, payload, status = note_service.delete_note_tag(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["notes_redirect"](campaign_slug)

    def rename_note_tag():
        action, campaign_slug, payload, status = note_service.rename_note_tag(views, request.form)
        if action == "not_found":
            return render_template("404.html"), 404
        if _is_fetch():
            return jsonify(payload), status
        return views["notes_redirect"](campaign_slug)

    def reorder_note_tags():
        payload, status = note_service.reorder_note_tags(views, request.form, request.get_json(silent=True) or {})
        return jsonify(payload), status

    routes = [
        ("GET", "/notes", "notes_page", notes_page),
        ("GET", "/materials/preview", "material_preview", material_preview),
        ("POST", "/notes/create", "create_note", create_note),
        ("POST", "/notes/<note_id>/update", "update_note", update_note),
        ("POST", "/notes/delete", "delete_notes", delete_notes),
        ("POST", "/notes/delete-all", "delete_all_notes", delete_all_notes),
        ("POST", "/notes/tags/add", "add_note_tag", add_note_tag),
        ("POST", "/notes/tags/delete", "delete_note_tag", delete_note_tag),
        ("POST", "/notes/tags/rename", "rename_note_tag", rename_note_tag),
        ("POST", "/notes/tags/reorder", "reorder_note_tags", reorder_note_tags),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
