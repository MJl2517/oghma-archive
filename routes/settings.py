from flask import jsonify, redirect, render_template, request, url_for

from ogma.services import settings as setting_service


def _is_fetch() -> bool:
    return request.headers.get("X-Requested-With") == "fetch" or "application/json" in request.headers.get("Accept", "")


def register_setting_routes(bp, views: dict) -> None:
    def start_job(kind: str, operation):
        job_id = views["start_local_job"](kind, operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def open_folder_route():
        form = request.form.copy()
        job_id = views["start_local_job"](
            "open_folder",
            lambda: {"ok": setting_service.open_folder(views, form)},
        )
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def settings_page():
        return render_template("settings.html", **setting_service.settings_page_context(views))

    def check_for_updates_route():
        return start_job(
            "update_check",
            lambda: setting_service.check_for_updates(views),
        )

    def download_update_route():
        return start_job(
            "update_download",
            lambda: setting_service.download_update(views),
        )

    def install_update_route():
        return start_job(
            "update_install",
            lambda: setting_service.install_update(views),
        )

    def update_foundry_settings():
        setting_service.update_foundry_settings(views, request.form)
        return redirect(url_for("settings_page", notice="settings-saved"))

    def update_spotlight_settings():
        setting_service.update_spotlight_settings(views, request.form)
        return redirect(url_for("settings_page", notice="settings-saved"))

    def update_demo_settings():
        setting_service.update_demo_settings(views, request.form)
        return redirect(url_for("settings_page", notice="settings-saved"))

    def update_notification_settings():
        setting_service.update_notification_settings(views, request.form)
        return redirect(url_for("settings_page", notice="settings-saved"))

    def update_appearance_settings():
        setting_service.update_appearance_settings(views, request.form)
        return redirect(request.referrer or url_for("settings_page", notice="settings-saved"))

    def update_favorite_campaign_settings():
        setting_service.update_favorite_campaign_settings(views, request.form)
        return redirect(request.referrer or url_for("index"))

    def sync_foundry_links_route():
        def operation():
            rows, summary = setting_service.sync_foundry_links(views)
            safe_rows = [
                {
                    key: row.get(key)
                    for key in ("label", "state", "ok", "message", "foundry_path")
                }
                for row in rows
            ]
            return {"ok": True, "summary": summary, "links": safe_rows}

        job_id = views["start_local_job"]("foundry_link_sync", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def pick_foundry_folder_route():
        form = request.form.copy()

        def operation():
            payload, _status = setting_service.pick_foundry_folder(views, form)
            return payload

        job_id = views["start_local_job"]("foundry_folder_picker", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    routes = [
        ("POST", "/folders/open", "open_folder_route", open_folder_route),
        ("GET", "/settings", "settings_page", settings_page),
        ("POST", "/settings/updates/check", "check_for_updates_route", check_for_updates_route),
        ("POST", "/settings/updates/download", "download_update_route", download_update_route),
        ("POST", "/settings/updates/install", "install_update_route", install_update_route),
        ("POST", "/settings/foundry", "update_foundry_settings", update_foundry_settings),
        ("POST", "/settings/spotlight", "update_spotlight_settings", update_spotlight_settings),
        ("POST", "/settings/demo", "update_demo_settings", update_demo_settings),
        ("POST", "/settings/notifications", "update_notification_settings", update_notification_settings),
        ("POST", "/settings/appearance", "update_appearance_settings", update_appearance_settings),
        ("POST", "/settings/favorite-campaign", "update_favorite_campaign_settings", update_favorite_campaign_settings),
        ("POST", "/settings/foundry/sync", "sync_foundry_links_route", sync_foundry_links_route),
        ("POST", "/settings/foundry/pick-folder", "pick_foundry_folder_route", pick_foundry_folder_route),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
