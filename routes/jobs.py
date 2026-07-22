from flask import jsonify


def register_job_routes(bp, views: dict) -> None:
    def health_check():
        return jsonify(
            {
                "ok": True,
                "service": "ogma",
                "status": "ready",
            }
        )

    def local_job_status(job_id: str):
        return jsonify({"ok": True, "job": views["local_job_status"](job_id)})

    bp.add_url_rule(
        "/health",
        endpoint="health_check",
        view_func=health_check,
        methods=["GET"],
    )
    bp.add_url_rule(
        "/jobs/<job_id>",
        endpoint="local_job_status",
        view_func=local_job_status,
        methods=["GET"],
    )
