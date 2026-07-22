from flask import jsonify, request

from ogma.services import clipboard as clipboard_service


def register_clipboard_routes(bp, views: dict) -> None:
    def copy_prepared_image_to_clipboard():
        payload, status = clipboard_service.copy_prepared_image(views, request.files.get("image"))
        return jsonify(payload), status

    bp.add_url_rule(
        "/clipboard/copy-image",
        endpoint="copy_prepared_image_to_clipboard",
        view_func=copy_prepared_image_to_clipboard,
        methods=["POST"],
    )
