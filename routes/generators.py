from urllib.parse import quote

from flask import Response, jsonify, render_template, request

from ogma.services import generators as generator_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json"


def _validation_response(error: generator_service.GeneratorValidationError):
    payload = {"ok": False, "errors": error.errors}
    if _is_fetch():
        return jsonify(payload), 400
    return jsonify(payload), 400


def register_generator_routes(bp, views: dict) -> None:
    def generators_page():
        return render_template("generators.html", **generator_service.generators_page_context(views, request.args))

    def create_generator():
        try:
            payload = generator_service.create_generator(views, request.form)
        except generator_service.GeneratorValidationError as error:
            return _validation_response(error)
        if _is_fetch():
            return jsonify(payload)
        return views["generators_redirect"]()

    def update_generator(generator_id: str):
        try:
            payload, status = generator_service.update_generator(views, request.form, generator_id)
        except generator_service.GeneratorValidationError as error:
            return _validation_response(error)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    def delete_generators():
        payload = generator_service.delete_generators(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return views["generators_redirect"]()

    def export_generators():
        filename, payload, status = generator_service.export_generators(views, request.args)
        return Response(
            payload,
            status=status,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"ogma-generators.json\"; filename*=UTF-8''{quote(filename)}"},
        )

    def import_generators():
        payload, status = generator_service.import_generators(views, request.files)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    def roll_generator(generator_id: str):
        payload, status = generator_service.roll_generator(views, generator_id)
        return jsonify(payload), status

    def edit_generator_fragment(generator_id: str):
        context, status = generator_service.generator_edit_modal_context(views, request.args, generator_id)
        if status != 200:
            return jsonify(context), status
        return render_template("_generator_edit_modal.html", **context)

    def add_generator_tag():
        payload = generator_service.add_generator_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return views["generators_redirect"]()

    def delete_generator_tag():
        payload, status = generator_service.delete_generator_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    def rename_generator_tag():
        payload, status = generator_service.rename_generator_tag(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    def add_generator_category():
        payload = generator_service.add_generator_category(views, request.form)
        if _is_fetch():
            return jsonify(payload)
        return views["generators_redirect"]()

    def delete_generator_category():
        payload, status = generator_service.delete_generator_category(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    def rename_generator_category():
        payload, status = generator_service.rename_generator_category(views, request.form)
        if _is_fetch():
            return jsonify(payload), status
        return views["generators_redirect"]()

    routes = [
        ("GET", "/generators", "generators_page", generators_page),
        ("POST", "/generators/create", "create_generator", create_generator),
        ("POST", "/generators/delete", "delete_generators", delete_generators),
        ("GET", "/generators/export", "export_generators", export_generators),
        ("POST", "/generators/import", "import_generators", import_generators),
        ("GET", "/generators/<generator_id>/edit", "edit_generator_fragment", edit_generator_fragment),
        ("POST", "/generators/<generator_id>/update", "update_generator", update_generator),
        ("POST", "/generators/<generator_id>/roll", "roll_generator", roll_generator),
        ("POST", "/generators/tags/add", "add_generator_tag", add_generator_tag),
        ("POST", "/generators/tags/delete", "delete_generator_tag", delete_generator_tag),
        ("POST", "/generators/tags/rename", "rename_generator_tag", rename_generator_tag),
        ("POST", "/generators/categories/add", "add_generator_category", add_generator_category),
        ("POST", "/generators/categories/delete", "delete_generator_category", delete_generator_category),
        ("POST", "/generators/categories/rename", "rename_generator_category", rename_generator_category),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
