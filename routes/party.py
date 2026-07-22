from flask import jsonify, redirect, render_template, request, send_file, url_for

from ogma.media import ALLOWED_IMAGE_EXTENSIONS
from ogma.safe_paths import PathBoundaryError, resolve_under
from ogma.services import party as party_service


def register_party_routes(bp, views: dict) -> None:
    def party_page():
        action, context = party_service.party_page_context(views, request.args)
        if action == "redirect_index":
            return redirect(url_for("index"))
        return render_template("party.html", **context)

    def upload_party_members():
        action, campaign_slug, _imported = party_service.upload_party_members(views, request.form, request.files)
        if action == "not_found":
            return render_template("404.html"), 404
        return redirect(url_for("party_page", campaign=campaign_slug))

    def delete_party_member(member_id: str):
        action, campaign_slug = party_service.delete_party_member(views, request.form, member_id)
        if action == "not_found":
            return render_template("404.html"), 404
        return redirect(url_for("party_page", campaign=campaign_slug))

    def sync_foundry_party_members():
        form = request.form.copy()

        def operation():
            action, campaign_slug, payload = party_service.sync_foundry_party_members(views, form)
            return {
                "ok": action != "not_found",
                "campaign_slug": campaign_slug,
                "notice": "foundry-synced",
                "imported": payload.get("imported", 0),
                "updated": payload.get("updated", 0),
                "errors": len(payload.get("errors", [])),
            }

        job_id = views["start_local_job"]("foundry_party_sync", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def open_foundry_party_folder():
        form = request.form.copy()

        def operation():
            action, campaign_slug, payload = party_service.open_foundry_party_folder(views, form)
            return {
                "ok": action != "not_found" and bool(payload.get("ok")),
                "campaign_slug": campaign_slug,
                "notice": (
                    "foundry-folder-opened"
                    if payload.get("ok")
                    else "foundry-folder-error"
                ),
            }

        job_id = views["start_local_job"]("foundry_party_folder", operation)
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("local_job_status", job_id=job_id),
            }
        ), 202

    def update_party_member_state(member_id: str):
        action, payload, status = party_service.update_party_member_state(views, request.form, member_id)
        return jsonify(payload), status

    def update_party_dm_notes(member_id: str):
        action, campaign_slug, open_member_id = party_service.update_party_dm_notes(views, request.form, member_id)
        if action == "not_found":
            return render_template("404.html"), 404
        return redirect(url_for("party_page", campaign=campaign_slug, member=open_member_id, notice="dm-notes-saved"))

    def favorite_party_summary():
        payload = party_service.favorite_party_summary_payload(views)
        return jsonify(payload), 200 if payload.get("ok") else 404

    def serve_foundry_party_asset(member_id: str):
        relative_path = party_service.party_member_asset_relative_path(views, member_id)
        if relative_path is None:
            return render_template("404.html"), 404
        try:
            target = resolve_under(views["foundry_data_dir"](), relative_path)
        except (OSError, PathBoundaryError):
            return render_template("404.html"), 404
        if target.suffix.casefold() not in ALLOWED_IMAGE_EXTENSIONS:
            return render_template("404.html"), 404
        return send_file(target, conditional=True)

    routes = [
        ("GET", "/party", "party_page", party_page),
        ("GET", "/party/favorite-summary", "favorite_party_summary", favorite_party_summary),
        ("GET", "/party/<member_id>/asset", "serve_foundry_party_asset", serve_foundry_party_asset),
        ("POST", "/party/upload", "upload_party_members", upload_party_members),
        ("POST", "/party/foundry-sync", "sync_foundry_party_members", sync_foundry_party_members),
        ("POST", "/party/foundry-folder/open", "open_foundry_party_folder", open_foundry_party_folder),
        ("POST", "/party/<member_id>/delete", "delete_party_member", delete_party_member),
        ("POST", "/party/<member_id>/state", "update_party_member_state", update_party_member_state),
        ("POST", "/party/<member_id>/dm-notes", "update_party_dm_notes", update_party_dm_notes),
    ]
    for method, rule, endpoint, view_func in routes:
        bp.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=[method])
