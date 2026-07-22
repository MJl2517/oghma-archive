def bind_routes(bp, views: dict, routes: list[tuple[str, str, str]]) -> None:
    for method, rule, endpoint in routes:
        view_func = views[endpoint]
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method.upper()])
