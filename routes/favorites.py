from flask import jsonify, request

from ogma.services import favorites as favorite_service


def register_favorite_routes(bp, views: dict) -> None:
    def favorites_index():
        return jsonify(favorite_service.favorites_payload(views))

    def create_favorite_group():
        payload, status = favorite_service.create_group(views, request.form)
        return jsonify(payload), status

    def activate_favorite_group(group_id: str):
        payload, status = favorite_service.activate_group(views, group_id)
        return jsonify(payload), status

    def rename_favorite_group(group_id: str):
        payload, status = favorite_service.rename_group(views, request.form, group_id)
        return jsonify(payload), status

    def delete_favorite_group(group_id: str):
        payload, status = favorite_service.delete_group(views, group_id)
        return jsonify(payload), status

    def reorder_favorite_groups():
        payload, status = favorite_service.reorder_groups(views, request.get_json(silent=True) or request.form)
        return jsonify(payload), status

    def reorder_favorite_group_items(group_id: str):
        payload, status = favorite_service.reorder_items(views, group_id, request.get_json(silent=True) or request.form)
        return jsonify(payload), status

    def toggle_favorite_item():
        payload, status = favorite_service.toggle_item(views, request.form)
        return jsonify(payload), status

    routes = [
        ("GET", "/favorites", "favorites_index", favorites_index),
        ("POST", "/favorites/groups", "create_favorite_group", create_favorite_group),
        ("POST", "/favorites/groups/<group_id>/activate", "activate_favorite_group", activate_favorite_group),
        ("POST", "/favorites/groups/<group_id>/rename", "rename_favorite_group", rename_favorite_group),
        ("POST", "/favorites/groups/<group_id>/delete", "delete_favorite_group", delete_favorite_group),
        ("POST", "/favorites/groups/reorder", "reorder_favorite_groups", reorder_favorite_groups),
        ("POST", "/favorites/groups/<group_id>/items/reorder", "reorder_favorite_group_items", reorder_favorite_group_items),
        ("POST", "/favorites/items/toggle", "toggle_favorite_item", toggle_favorite_item),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
