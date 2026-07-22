from __future__ import annotations

import json
from typing import BinaryIO, Any

from ogma.errors import PayloadTooLargeError, ValidationError
from ogma.security import MAX_JSON_BYTES, json_within_limits


def load_limited_json_stream(
    stream: BinaryIO,
    *,
    maximum_bytes: int = MAX_JSON_BYTES,
) -> Any:
    raw = stream.read(maximum_bytes + 1)
    if len(raw) > maximum_bytes:
        raise PayloadTooLargeError("JSON input exceeds the configured size limit.")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("JSON input is malformed.") from exc
    if not json_within_limits(payload):
        raise ValidationError("JSON input exceeds nesting or item limits.")
    return payload
