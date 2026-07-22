from flask import jsonify, render_template, request


def _payload() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form


def register_demo_routes(bp, views: dict) -> None:
    def demo_page():
        demo_enabled = bool(views["load_settings"]().get("demo", {}).get("enabled"))
        return render_template("demo.html", demo_enabled=demo_enabled)

    def demo_state():
        if not views["load_settings"]().get("demo", {}).get("enabled"):
            return jsonify({"content": None, "enabled": False, "updated_at": ""})
        return jsonify({"enabled": True, **views["load_demo_state"]()})

    def demo_show():
        payload = _payload()
        response, status = views["build_demo_content"](
            payload.get("kind", ""),
            payload.get("id", ""),
            payload.get("scope", "shared"),
            payload.get("campaign_slug", ""),
        )
        return jsonify(response), status

    def demo_clear():
        return jsonify({"ok": True, "state": views["clear_demo_state"]()})

    routes = [
        ("GET", "/demo", "demo_page", demo_page),
        ("GET", "/demo/state", "demo_state", demo_state),
        ("POST", "/demo/show", "demo_show", demo_show),
        ("POST", "/demo/clear", "demo_clear", demo_clear),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
