from app.services.streaming_events import StreamEventBuilder, WenLingoStreamFrame, format_sse_event


def test_stream_event_builder_assigns_increasing_sequence_numbers():
    builder = StreamEventBuilder(stream_id="stream-1", submission_id="submission-1")

    first = builder.event("start", {"phase": "reserved"})
    second = builder.event("feedback_section_preview", {"section": "strengths"})

    assert first["seq"] == 1
    assert second["seq"] == 2
    assert first["schema_version"] == "v0.6e.1"


def test_stream_event_builder_can_wrap_queue_frames():
    builder = StreamEventBuilder(stream_id="stream-1", submission_id="submission-1")

    frame = builder.frame("feedback_section_preview", {"section": "strengths"})

    assert isinstance(frame, WenLingoStreamFrame)
    assert frame.event_name == "feedback_section_preview"
    assert frame.data["seq"] == 1
    assert frame.data["section"] == "strengths"


def test_stream_event_builder_envelope_values_cannot_be_overridden():
    builder = StreamEventBuilder(stream_id="stream-1", submission_id="submission-1")

    event = builder.event(
        "start",
        {
            "schema_version": "bad-version",
            "event_id": "evt_bad",
            "seq": 99,
            "stream_id": "bad-stream",
            "submission_id": "bad-submission",
            "phase": "reserved",
        },
    )

    assert event["schema_version"] == "v0.6e.1"
    assert event["event_id"] != "evt_bad"
    assert event["seq"] == 1
    assert event["stream_id"] == "stream-1"
    assert event["submission_id"] == "submission-1"
    assert event["phase"] == "reserved"


def test_format_sse_event_uses_event_name_and_json_data():
    payload = {
        "schema_version": "v0.6e.1",
        "event_id": "evt_1",
        "seq": 1,
        "stream_id": "stream-1",
    }

    body = format_sse_event("start", payload)

    assert body.startswith("event: start\n")
    assert '"stream_id":"stream-1"' in body
    assert body.endswith("\n\n")
