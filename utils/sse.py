from __future__ import annotations

import json
import uuid
from typing import Any

__all__ = ["format_sse", "json_event"]


def _line(field: str, value: str) -> str:
    """Return one correctly formatted *single* SSE line."""

    return f"{field}: {value}\n"


def format_sse(event: str, data: str, *, event_id: str | None = None) -> str:
    lines: list[str] = []
    if event_id is None:
        event_id = str(uuid.uuid4())
    lines.append(_line("id", event_id))
    lines.append(_line("event", event))
    lines.append(_line("data", data))

    lines.append("\n")

    return "".join(lines)


def json_event(event: str, payload: Any, *, event_id: str | None = None) -> str:
    """Convenience wrapper that JSON-encodes *payload* for the *data* line."""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    elif hasattr(payload, "dict"):
        payload = payload.dict()

    json_payload = json.dumps(payload, ensure_ascii=False, default=str)
    return format_sse(event, json_payload, event_id=event_id)