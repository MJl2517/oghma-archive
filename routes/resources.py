from flask import abort, jsonify, render_template, request, send_file, url_for

from ogma.services import resources as resource_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def register_resource_routes(bp, views: dict) -> None:
    def resources_page():
        return render_template("resources.html", **resource_service.resources_page_context(views, request.args))

    def create_resource():
        resource_service.create_resource(views, request.form)
        return views["resources_redirect"]()

    def delete_resources():
        resource_service.delete_resources(views, request.form)
        return views["resources_redirect"]()

    def open_resource(resource_id: str):
        def operation():
            payload, _status = resource_service.open_resource(views, resource_id)
            return payload

        job_id = views["start_local_job"]("open_resource", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def serve_resource_file(resource_id: str):
        target, _error, status = resource_service.resource_file_path(views, resource_id)
        if target is None:
            abort(status)
        return send_file(target, as_attachment=True, download_name=target.name, conditional=True)

    def add_resource_tag():
        payload = resource_service.add_resource_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return views["resources_redirect"]()

    def delete_resource_tag():
        payload, status = resource_service.delete_resource_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["resources_redirect"]()

    def rename_resource_tag():
        payload, status = resource_service.rename_resource_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["resources_redirect"]()

    def add_resource_category():
        payload = resource_service.add_resource_category(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return views["resources_redirect"]()

    def delete_resource_category():
        payload, status = resource_service.delete_resource_category(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["resources_redirect"]()

    def rename_resource_category():
        payload, status = resource_service.rename_resource_category(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["resources_redirect"]()

    def pick_resource_file():
        form = request.form.copy()

        def operation():
            payload, _status = resource_service.pick_resource_file(views, form)
            return payload

        job_id = views["start_local_job"]("resource_file_picker", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def update_resource(resource_id: str):
        resource_service.update_resource(views, request.form, resource_id)
        return views["resources_redirect"]()

    routes = [
        ("GET", "/resources", "resources_page", resources_page),
        ("POST", "/resources/create", "create_resource", create_resource),
        ("POST", "/resources/delete", "delete_resources", delete_resources),
        ("POST", "/resources/<resource_id>/open", "open_resource", open_resource),
        ("GET", "/resources/<resource_id>/file", "serve_resource_file", serve_resource_file),
        ("POST", "/resources/tags/add", "add_resource_tag", add_resource_tag),
        ("POST", "/resources/tags/delete", "delete_resource_tag", delete_resource_tag),
        ("POST", "/resources/tags/rename", "rename_resource_tag", rename_resource_tag),
        ("POST", "/resources/categories/add", "add_resource_category", add_resource_category),
        ("POST", "/resources/categories/delete", "delete_resource_category", delete_resource_category),
        ("POST", "/resources/categories/rename", "rename_resource_category", rename_resource_category),
        ("POST", "/resources/pick-file", "pick_resource_file", pick_resource_file),
        ("POST", "/resources/<resource_id>/update", "update_resource", update_resource),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
