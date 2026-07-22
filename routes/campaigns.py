from flask import jsonify, redirect, render_template, request, send_file, url_for

from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import campaigns as campaign_service


def register_campaign_routes(bp, views: dict) -> None:
    def index():
        return render_template("index.html", **campaign_service.index_context(views))

    def create_campaign_route():
        action, campaign = campaign_service.create_campaign(views, request.form)
        if action == "redirect_index":
            return redirect(url_for("index"))
        return redirect(url_for("campaign_detail", slug=campaign["slug"]))

    def update_campaign_route(slug: str):
        action, payload = campaign_service.update_campaign(views, request.form, request.files, slug)
        if action == "not_found":
            return render_template("404.html"), 404
        return redirect(url_for("campaign_detail", slug=payload["slug"]))

    def campaign_detail(slug: str):
        action, context = campaign_service.campaign_detail_context(views, slug)
        if action == "not_found":
            return render_template("404.html"), 404
        return render_template("campaign.html", **context)

    def open_campaign_folder(slug: str):
        job_id = views["start_local_job"](
            "open_campaign_folder",
            lambda: {
                "ok": campaign_service.open_campaign_folder(views, slug)
                != "not_found"
            },
        )
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def open_campaign_section_folder(slug: str, folder: str):
        job_id = views["start_local_job"](
            "open_campaign_section_folder",
            lambda: {
                "ok": campaign_service.open_campaign_section_folder(
                    views,
                    slug,
                    folder,
                )
                != "not_found"
            },
        )
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def delete_campaign(slug: str):
        result = campaign_service.delete_campaign(views, slug)
        if result == "not_found":
            return render_template("404.html"), 404
        if result == "disabled":
            return (
                "Удаление миров временно отключено до появления проверенного "
                "резервного копирования и восстановления.",
                409,
            )
        return redirect(url_for("index"))

    def serve_campaign_cover(campaign_slug: str):
        directory = campaign_service.campaign_cover_directory(views, campaign_slug)
        campaign = views["get_campaign"](campaign_slug)
        filename = str((campaign or {}).get("cover_image", ""))
        if directory is None or not filename:
            return render_template("404.html"), 404
        try:
            target = resolve_under(directory, filename)
        except (OSError, PathBoundaryError):
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    routes = [
        ("GET", "/", "index", index),
        ("POST", "/campaigns", "create_campaign_route", create_campaign_route),
        ("POST", "/campaigns/<slug>/update", "update_campaign_route", update_campaign_route),
        ("GET", "/campaigns/<slug>", "campaign_detail", campaign_detail),
        ("POST", "/campaigns/<slug>/open-folder", "open_campaign_folder", open_campaign_folder),
        ("POST", "/campaigns/<slug>/folders/<folder>/open", "open_campaign_section_folder", open_campaign_section_folder),
        ("POST", "/campaigns/<slug>/delete", "delete_campaign", delete_campaign),
        ("GET", "/media/campaigns/<campaign_slug>/cover", "serve_campaign_cover", serve_campaign_cover),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
