from flask import Blueprint, Flask


routes_bp = Blueprint("routes", __name__)


def register_routes(flask_app: Flask) -> None:
    flask_app.register_blueprint(routes_bp)
    legacy_prefix = f"{routes_bp.name}."
    for rule in list(flask_app.url_map.iter_rules()):
        if not rule.endpoint.startswith(legacy_prefix):
            continue
        legacy_endpoint = rule.endpoint.removeprefix(legacy_prefix)
        if legacy_endpoint in flask_app.view_functions:
            continue
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        flask_app.add_url_rule(
            rule.rule,
            endpoint=legacy_endpoint,
            view_func=flask_app.view_functions[rule.endpoint],
            methods=methods,
            defaults=rule.defaults,
            strict_slashes=rule.strict_slashes,
        )
