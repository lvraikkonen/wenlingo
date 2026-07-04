import json
from dataclasses import dataclass
from typing import Any

from app.domain.models import new_uuid


@dataclass(frozen=True)
class WenLingoStreamFrame:
    event_name: str
    data: dict[str, Any]


class StreamEventBuilder:
    def __init__(self, *, stream_id: str, submission_id: str):
        self.stream_id = stream_id
        self.submission_id = submission_id
        self.seq = 0

    def event(self, event_name: str, data: dict) -> dict:
        self.seq += 1
        return {
            "schema_version": "v0.6e.1",
            "event_id": f"evt_{new_uuid()}",
            "seq": self.seq,
            "stream_id": self.stream_id,
            "submission_id": self.submission_id,
            **data,
        }

    def frame(self, event_name: str, data: dict) -> WenLingoStreamFrame:
        return WenLingoStreamFrame(
            event_name=event_name,
            data=self.event(event_name, data),
        )


def format_sse_event(event_name: str, data: dict) -> str:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {encoded}\n\n"
