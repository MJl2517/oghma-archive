from flask import redirect, render_template, request, url_for

from ogma.services import fallback as fallback_service


def register_fallback_routes(bp, views: dict) -> None:
    def section(slug):
        action, payload = fallback_service.section_target(views, slug, request.args.get("campaign", ""))
        if action == "not_found":
            return render_template("404.html"), 404
        if action == "redirect_endpoint":
            return redirect(url_for(payload["endpoint"], **payload["values"]))
        return render_template("section.html", **payload)

    bp.add_url_rule("/<slug>", endpoint="section", view_func=section, methods=["GET"])
